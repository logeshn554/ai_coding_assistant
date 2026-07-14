import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .state import SESSION_TOKEN, verify_token, limiter, logger
from .routes import all_routers

@asynccontextmanager
async def lifespan(app: FastAPI):
    from .db import init_db
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    yield

# Instantiate FastAPI app with lifespan context manager and global authentication check
app = FastAPI(title="DevPilot Backend", dependencies=[Depends(verify_token)], lifespan=lifespan)

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
cors_origins = ["http://localhost:5173"]
cors_env = os.environ.get("CORS_ORIGINS")
if cors_env:
    cors_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
elif os.environ.get("ALLOW_REMOTE", "false").lower() == "true" or os.environ.get("DOCKER_MODE", "false").lower() == "true":
    cors_origins = [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5173"
    ]

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