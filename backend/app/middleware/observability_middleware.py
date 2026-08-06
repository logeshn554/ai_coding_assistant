import time
import logging
from fastapi import Request
from agent_os.infrastructure.observability import observability
from agent_os.infrastructure.metrics import metrics_collector

logger = logging.getLogger("devpilot.observability_middleware")

async def observability_middleware(request: Request, call_next):
    """Middleware that wraps the request in an observability span and collects metrics."""
    path = request.url.path
    # Only trace /api/ paths to avoid noise from static assets
    if not path.startswith("/api/"):
        return await call_next(request)

    method = request.method
    attrs = {
        "method": method,
        "path": path,
    }
    
    # Ensure trace_id is set on request state
    trace_id = getattr(request.state, "trace_id", None)
    if not trace_id:
        import uuid
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
    attrs["trace_id"] = trace_id


    # Record request counter metric
    metrics_collector.increment(
        name="http_requests_total",
        labels={"method": method, "path": path}
    )

    start_time = time.perf_counter()
    
    with observability.span(f"HTTP {method} {path}", attributes=attrs):
        try:
            response = await call_next(request)
            status_code = response.status_code
            metrics_collector.increment(
                name="http_responses_total",
                labels={"method": method, "path": path, "status": str(status_code)}
            )
            
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            metrics_collector.set_gauge(
                name="http_request_duration_ms",
                value=duration_ms,
                labels={"method": method, "path": path}
            )
            return response
        except Exception as exc:
            metrics_collector.increment(
                name="http_errors_total",
                labels={"method": method, "path": path, "error": type(exc).__name__}
            )
            raise exc
