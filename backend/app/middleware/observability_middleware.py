import time
import logging
import uuid
from fastapi import Request
from backend.app.infrastructure.observability.telemetry import (
    correlation_id_var,
    run_id_var,
    organization_id_var,
    user_id_var,
    workspace_id_var,
    TelemetryManager,
)

logger = logging.getLogger("devpilot.observability_middleware")

async def observability_middleware(request: Request, call_next):
    """Middleware that injects correlation context, records request latencies, and tracks status distributions."""
    # Track correlation IDs across HTTP layer (Section 2 requirement)
    corr_id = (
        request.headers.get("x-correlation-id")
        or request.headers.get("X-Correlation-ID")
        or request.headers.get("x-request-id")
        or request.headers.get("X-Request-ID")
        or str(uuid.uuid4())
    )
    correlation_id_var.set(corr_id)
    
    organization_id_var.set(request.headers.get("x-organization-id"))
    user_id_var.set(request.headers.get("x-user-id"))
    workspace_id_var.set(request.headers.get("x-workspace-id"))
    
    path = request.url.path
    # Only trace /api/ paths to avoid noise from static assets
    if not path.startswith("/api/"):
        return await call_next(request)

    method = request.method
    attrs = {
        "method": method,
        "path": path,
        "correlation_id": corr_id,
    }

    # Record request counter metric (Section 13 requirement)
    TelemetryManager.increment_counter(
        name="http_requests_total",
        attributes={"method": method, "path": path}
    )

    start_time = time.perf_counter()
    tracer = TelemetryManager.get_tracer()
    
    with tracer.start_as_current_span(f"HTTP {method} {path}", attributes=attrs):
        try:
            response = await call_next(request)
            status_code = response.status_code
            status_group = f"{status_code // 100}xx"
            
            # Record response counter & duration metric (Section 13 requirement)
            TelemetryManager.increment_counter(
                name="http_responses_total",
                attributes={"method": method, "path": path, "status": str(status_code), "status_group": status_group}
            )
            
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            TelemetryManager.record_histogram(
                name="http_request_duration_ms",
                value=duration_ms,
                attributes={"method": method, "path": path}
            )
            
            response.headers["X-Correlation-ID"] = corr_id
            response.headers["X-Request-ID"] = corr_id
            return response
        except Exception as exc:
            TelemetryManager.increment_counter(
                name="http_errors_total",
                attributes={"method": method, "path": path, "error": type(exc).__name__}
            )
            raise exc
