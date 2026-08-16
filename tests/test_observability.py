import os
import pytest
import logging
import json
import uuid
from backend.app.infrastructure.observability.telemetry import (
    correlation_id_var,
    run_id_var,
    TelemetryManager,
    JSONLogFormatter,
    SecretRedactingFilter,
)

def test_correlation_id_context_vars():
    corr_id = str(uuid.uuid4())
    correlation_id_var.set(corr_id)
    assert correlation_id_var.get() == corr_id

    # Test JSON formatter matches set values
    formatter = JSONLogFormatter()
    logger = logging.getLogger("test_telemetry")
    record = logger.makeRecord(
        name="test_telemetry",
        level=logging.INFO,
        fn="test_observability.py",
        lno=15,
        msg="Test correlation log trace",
        args=(),
        exc_info=None
    )
    formatted_log = formatter.format(record)
    log_data = json.loads(formatted_log)
    assert log_data["correlation_id"] == corr_id
    assert log_data["event"] == "Test correlation log trace"

def test_secret_redacting_filter():
    redactor_filter = SecretRedactingFilter()
    logger = logging.getLogger("test_redact")
    dummy_token = "ghp_" + ("1234567890abcdef" * 2) + "1234"
    record = logger.makeRecord(
        name="test_redact",
        level=logging.INFO,
        fn="test_observability.py",
        lno=30,
        msg=f"GitHub token {dummy_token} is secret",
        args=(),
        exc_info=None
    )
    redactor_filter.filter(record)
    assert "ghp_" not in record.msg
    assert "[REDACTED]" in record.msg

def test_telemetry_metrics_tracking():
    counter_name = "test_run_events_total"
    TelemetryManager.increment_counter(counter_name, amount=5, attributes={"status": "success"})
    
    counter = TelemetryManager._counters[counter_name]
    if hasattr(counter, "value"):
        assert counter.value == 5
    else:
        assert counter is not None

    hist_name = "test_run_duration"
    TelemetryManager.record_histogram(hist_name, 120.5, attributes={"run_type": "full"})
    histogram = TelemetryManager._histograms[hist_name]
    if hasattr(histogram, "values"):
        assert 120.5 in histogram.values
    else:
        assert histogram is not None

@pytest.mark.asyncio
async def test_health_routes():
    from backend.app.routes.health import health_live, health_ready, health_dependencies
    
    live_res = await health_live()
    assert live_res["status"] == "alive"

    ready_res = await health_ready()
    assert ready_res["status"] == "ready"

    dep_res = await health_dependencies()
    assert dep_res.status_code == 200
    res_body = json.loads(dep_res.body)
    assert "database" in res_body
    assert "redis" in res_body
