import os
import sys
import logging
import asyncio

# Add agent subdirectory to path to support consolidated imports
current_dir = os.path.dirname(os.path.abspath(__file__))
agent_dir = os.path.join(current_dir, "agent")
if agent_dir not in sys.path:
    sys.path.insert(0, agent_dir)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .logging_config import setup_logging
setup_logging()

from .config import settings
from .state import SESSION_TOKEN, verify_token, limiter, logger
from .middleware.error_handler import global_error_middleware
from .routes import all_routers

@asynccontextmanager
async def lifespan(app: FastAPI):
    import shutil as _shutil
    from .db import init_db
    from .state import check_redis_at_startup
    from .rag import _evict_old_chroma_indexes
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    try:
        await check_redis_at_startup()
    except Exception as e:
        logger.warning(f"Redis startup check raised unexpectedly: {e}")
    # Evict old ChromaDB indexes to keep disk usage bounded
    try:
        _evict_old_chroma_indexes()
    except Exception as e:
        logger.warning(f"ChromaDB eviction at startup raised unexpectedly: {e}")
    # Log ripgrep availability so operators notice early if it is missing
    rg_path = _shutil.which("rg")
    if rg_path:
        logger.info("ripgrep found at %s — fast codebase search enabled.", rg_path)
    else:
        logger.warning(
            "ripgrep (rg) not found in PATH. Codebase search will use the slow Python "
            "fallback. Install ripgrep: https://github.com/BurntSushi/ripgrep#installation"
        )
    
    # Start AgentWorker background task unless run as a dedicated external worker cluster
    run_embedded_worker = os.getenv("RUN_EMBEDDED_WORKER", "true").lower() == "true"
    if run_embedded_worker or settings.ENVIRONMENT != "production":
        from .infrastructure.worker import AgentWorker
        worker = AgentWorker()
        app.state.worker_task = asyncio.create_task(worker.start())
        logger.info("Background AgentWorker started.")
        
    yield
    # Shutdown: stop any processes we spawned (Live Server, dev servers started
    # from the Run panel, etc.) so they don't leak as orphans after the backend exits.
    if settings.ENVIRONMENT != "production":
        if hasattr(app.state, "worker_task"):
            app.state.worker_task.cancel()
            logger.info("Background AgentWorker stopped.")
            
    try:
        from .processes import global_process_manager
        for proc in list(global_process_manager.get_running_processes()):
            try:
                await proc.stop()
            except Exception as e:
                logger.warning(f"Failed to stop process {proc.id} during shutdown: {e}")
    except Exception as e:
        logger.warning(f"Process cleanup during shutdown raised unexpectedly: {e}")

# Instantiate FastAPI app with OpenAPI docs and global auth verification
app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-agent production-grade AI IDE Backend API",
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    dependencies=[Depends(verify_token)],
    lifespan=lifespan,
)

# Register Global Error Middleware & Observability Middleware
from .middleware.observability_middleware import observability_middleware
app.middleware("http")(observability_middleware)
app.middleware("http")(global_error_middleware)

from slowapi.middleware import SlowAPIMiddleware
app.add_middleware(SlowAPIMiddleware)

@app.middleware("http")
async def session_middleware(request: Request, call_next):
    session_id = (
        request.headers.get("X-Session-ID")
        or request.query_params.get("session_id")
        or request.headers.get("x-session-id")
    )
    from .state import session_id_var
    token = session_id_var.set(session_id)
    try:
        response = await call_next(request)
        return response
    finally:
        session_id_var.reset(token)

from .gateway.auth import auth_gateway
from .gateway.rate_limiter import rate_limiter, RateLimitResult

@app.middleware("http")
async def gateway_middleware(request: Request, call_next):
    path = request.url.path
    # Skip static files, fallback, docs, health check
    if path == "/" or path.startswith("/assets/") or path.endswith((".js", ".css", ".png", ".jpg", ".svg", ".ico", ".ttf", ".woff", ".woff2", ".html")) or path in ("/auth/token", "/api/auth/token", "/api/docs", "/api/openapi.json", "/redoc", "/api/health"):
        return await call_next(request)

    # 1. Authenticate request via Gateway Auth
    headers = dict(request.headers)
    query_params = dict(request.query_params)
    identity = auth_gateway.authenticate(headers, query_params)
    
    # Expose identity in request state
    request.state.identity = identity

    # 2. Enforce Rate Limiting
    if settings.ENVIRONMENT != "production":
        return await call_next(request)

    rate_limit_resp = rate_limiter.check(
        tenant_id=identity.tenant.tenant_id,
        user_id=identity.user_id,
        endpoint=path,
        tier=identity.tenant.tier,
        multiplier=identity.tenant.rate_limit_multiplier,
    )

    if rate_limit_resp.result in (RateLimitResult.THROTTLED, RateLimitResult.BLOCKED):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Rate limit exceeded."},
            headers={"Retry-After": str(int(rate_limit_resp.retry_after))},
        )

    # 3. Request execution
    response = await call_next(request)
    return response

# Add limiter state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Permission error handler
@app.exception_handler(PermissionError)
def permission_error_handler(request: Request, exc: PermissionError):
    return JSONResponse(
        status_code=403,
        content={"detail": str(exc)}
    )

# Setup CORS
cors_origins = settings.CORS_ORIGINS
allow_all = "*" in cors_origins

if allow_all:
    logger.warning(
        "CORS_ORIGINS includes '*' — serving true wildcard CORS. "
        "allow_credentials is forced to False in this mode (per CORS spec) "
        "since combining a reflected wildcard origin with credentials=True "
        "would let any website make authenticated requests. Auth in this app "
        "is header/query-token based, not cookie based, so this does not "
        "affect normal API usage."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else cors_origins,
    allow_credentials=not allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

import time
from .state import request_latencies

@app.middleware("http")
async def record_request_latency(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        duration = (time.perf_counter() - start) * 1000.0
        request_latencies.append(duration)
    return response

# Include all modular routers
for router in all_routers:
    app.include_router(router)

# Serve Compiled Static Frontend
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    FRONTEND_DIST = os.path.join(sys._MEIPASS, "frontend", "dist")
else:
    FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.isdir(FRONTEND_DIST):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    from fastapi.responses import HTMLResponse
    @app.get("/", response_class=HTMLResponse)
    def frontend_fallback():
        return "<html><body style='background:#0b0c14;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;'><h2>DevPilot Frontend Build Missing. Please run 'npm run build' in frontend directory.</h2></body></html>"