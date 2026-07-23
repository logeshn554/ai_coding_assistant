"""Health and metrics endpoints for DevPilot."""

from __future__ import annotations

import datetime
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..state import workspace_state, redis_client, SESSION_TOKEN, verify_token

logger = logging.getLogger("devpilot.health")

router = APIRouter()

# Process start time for uptime calculation
_START_TIME: float = time.monotonic()


class HealthResponse(BaseModel):
    """Response model for GET /api/health."""

    status: str
    version: str
    uptime_seconds: int
    workspace_root: str
    redis_connected: bool
    db_connected: bool
    timestamp: str


class MetricsSummary(BaseModel):
    """Response model for GET /api/metrics."""

    total_sessions: int
    total_messages: int
    avg_response_ms: float | None
    db_size_bytes: int


@router.get("/api/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Return service health without requiring auth.

    Note: auth is bypassed at the router level for this endpoint via
    ``include_in_schema`` — the token Depends is still useful for logging.
    """
    uptime = int(time.monotonic() - _START_TIME)

    # Check Redis
    redis_ok = False
    try:
        if hasattr(redis_client, "use_fallback"):
            redis_ok = not redis_client.use_fallback
        else:
            await redis_client.ping()
            redis_ok = True
    except Exception:
        redis_ok = False

    # Check SQLite
    db_ok = False
    try:
        from ..db import async_session
        from sqlalchemy import text

        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        logger.warning("DB health check failed: %s", exc)

    return HealthResponse(
        status="ok",
        version=os.environ.get("DEVPILOT_VERSION", "0.1.0"),
        uptime_seconds=uptime,
        workspace_root=workspace_state.root or "",
        redis_connected=redis_ok,
        db_connected=db_ok,
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
    )


@router.get("/api/metrics", response_model=MetricsSummary, tags=["health"])
async def get_metrics() -> MetricsSummary:
    """Return aggregate usage metrics from the database."""
    try:
        from ..db import async_session, SessionModel, MessageModel
        from sqlalchemy import select, func

        async with async_session() as db:
            sess_count_res = await db.execute(select(func.count()).select_from(SessionModel))
            total_sessions: int = sess_count_res.scalar() or 0

            msg_count_res = await db.execute(select(func.count()).select_from(MessageModel))
            total_messages: int = msg_count_res.scalar() or 0

        # DB file size
        from ..db import DB_FILE
        db_size = DB_FILE.stat().st_size if DB_FILE.exists() else 0

        return MetricsSummary(
            total_sessions=total_sessions,
            total_messages=total_messages,
            avg_response_ms=None,  # TODO: instrument per-turn latency
            db_size_bytes=db_size,
        )
    except Exception as exc:
        logger.error("Metrics query failed: %s", exc)
        return MetricsSummary(
            total_sessions=0,
            total_messages=0,
            avg_response_ms=None,
            db_size_bytes=0,
        )
