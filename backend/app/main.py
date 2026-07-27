import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import settings
from .state import SESSION_TOKEN, verify_token, limiter, logger
from .middleware.error_handler import global_error_middleware
from .routes import all_routers

@asynccontextmanager
async def lifespan(app: FastAPI):
    from .db import init_db
    from .state import check_redis_at_startup
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    try:
        await check_redis_at_startup()
    except Exception as e:
        logger.warning(f"Redis startup check raised unexpectedly: {e}")
    yield

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

# Register Global Error Middleware
app.middleware("http")(global_error_middleware)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[] if allow_all else cors_origins,
    allow_origin_regex=".*" if allow_all else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all modular routers
for router in all_routers:
    app.include_router(router)

# Serve Compiled Static Frontend
FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.isdir(FRONTEND_DIST):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    from fastapi.responses import HTMLResponse
    @app.get("/", response_class=HTMLResponse)
    def frontend_fallback():
        return "<html><body style='background:#0b0c14;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;'><h2>DevPilot Frontend Build Missing. Please run 'npm run build' in frontend directory.</h2></body></html>"