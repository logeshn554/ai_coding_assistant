import contextvars
import json
import logging
from typing import Any

# --- Correlation ID Propagation Context Variables ---
correlation_id_var = contextvars.ContextVar("correlation_id", default=None)
run_id_var = contextvars.ContextVar("run_id", default=None)
organization_id_var = contextvars.ContextVar("organization_id", default=None)
user_id_var = contextvars.ContextVar("user_id", default=None)
workspace_id_var = contextvars.ContextVar("workspace_id", default=None)

# --- Secret Redaction Filter for Logger ---
class SecretRedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            from backend.app.agent.security import SecretRedactor
            try:
                record.msg = SecretRedactor.redact_secrets(record.msg)
            except Exception:
                pass
        return True

# --- Structured JSON Log Formatter ---
class JSONLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        log_payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "service": "devpilot",
            "component": record.name,
            "event": msg,
            "correlation_id": correlation_id_var.get(),
            "run_id": run_id_var.get(),
            "organization_id": organization_id_var.get(),
            "user_id": user_id_var.get(),
            "workspace_id": workspace_id_var.get(),
        }
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_payload)

# --- OpenTelemetry Wrapper Interface / Fallback Mock Telemetry ---
try:
    from opentelemetry import metrics, trace
    from opentelemetry.metrics import Meter  # noqa: F401
    from opentelemetry.trace import Tracer  # noqa: F401
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

class MockSpan:
    def __init__(self, name: str, attributes: dict[str, Any] | None = None):
        self.name = name
        self.attributes = attributes or {}
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

class MockTracer:
    def start_as_current_span(self, name: str, attributes: dict[str, Any] | None = None):
        return MockSpan(name, attributes)

class MockCounter:
    def __init__(self, name: str):
        self.name = name
        self.value = 0
    def add(self, amount: int, attributes: dict[str, Any] | None = None):
        self.value += amount

class MockHistogram:
    def __init__(self, name: str):
        self.name = name
        self.values = []
    def record(self, amount: float, attributes: dict[str, Any] | None = None):
        self.values.append(amount)

class MockMeter:
    def create_counter(self, name: str, *args, **kwargs):
        return MockCounter(name)
    def create_histogram(self, name: str, *args, **kwargs):
        return MockHistogram(name)

class TelemetryManager:
    _tracer = None
    _meter = None
    _counters: dict[str, Any] = {}
    _histograms: dict[str, Any] = {}

    @classmethod
    def get_tracer(cls):
        if cls._tracer is None:
            if _OTEL_AVAILABLE:
                cls._tracer = trace.get_tracer("devpilot")
            else:
                cls._tracer = MockTracer()
        return cls._tracer

    @classmethod
    def get_meter(cls):
        if cls._meter is None:
            if _OTEL_AVAILABLE:
                cls._meter = metrics.get_meter("devpilot")
            else:
                cls._meter = MockMeter()
        return cls._meter

    @classmethod
    def increment_counter(cls, name: str, amount: int = 1, attributes: dict[str, Any] | None = None):
        meter = cls.get_meter()
        if name not in cls._counters:
            cls._counters[name] = meter.create_counter(name)
        cls._counters[name].add(amount, attributes)

    @classmethod
    def record_histogram(cls, name: str, value: float, attributes: dict[str, Any] | None = None):
        meter = cls.get_meter()
        if name not in cls._histograms:
            cls._histograms[name] = meter.create_histogram(name)
        cls._histograms[name].record(value, attributes)

# Setup JSON production logger config helper
def configure_production_logging():
    root_logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JSONLogFormatter())
    handler.addFilter(SecretRedactingFilter())
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)
