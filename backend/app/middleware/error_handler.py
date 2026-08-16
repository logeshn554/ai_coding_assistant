import logging
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

from ..errors import DevPilotError

logger = logging.getLogger("devpilot.error_middleware")

async def global_error_middleware(request: Request, call_next):
    """Middleware catching DevPilotError and uncaught exceptions with structured error responses."""
    trace_id = getattr(request.state, "trace_id", None)
    if not trace_id:
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id

    try:
        response = await call_next(request)
        return response
    except DevPilotError as exc:
        logger.warning(f"[{trace_id}] DevPilotError ({exc.code}): {exc.message} - Path: {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "trace_id": trace_id,
                }
            },
        )
    except Exception as exc:
        logger.error(f"[{trace_id}] Uncaught exception on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred.",
                    "trace_id": trace_id,
                }
            },
        )
