import logging
import sys
import time
import json
from .config import settings

class JSONFormatter(logging.Formatter):
    """Formatter that outputs structured JSON log entries for production aggregators."""
    
    def __init__(self) -> None:
        super().__init__()
        self.converter = time.gmtime  # Timestamps in UTC timezone

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "lineno": record.lineno,
        }

        # Inject X-Request-ID correlation ID when available (set by correlation_middleware)
        try:
            from .main import _correlation_id_var  # lazy import — avoids circular dep
            req_id = _correlation_id_var.get("")
            if req_id:
                log_data["request_id"] = req_id
        except Exception:
            pass

        # Include session/context info if added via extra keys
        # We can extract any dynamic fields attached to the LogRecord dict
        for key, val in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
                "created", "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process", "message"
            }:
                log_data[key] = val

        # Append traceback details if exception info is available
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        ct = self.converter(record.created)
        t = time.strftime("%Y-%m-%dT%H:%M:%S", ct)
        return f"{t}.{int(record.msecs):03d}Z"


def setup_logging() -> None:
    """Initializes and configures the logging subsystem."""
    if settings.LOG_JSON:
        formatter = JSONFormatter()
    else:
        # Standard human-readable development output format
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Configure root logger
    root_logger = logging.getLogger()
    
    # Empty existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Add console output handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Resolve log level dynamically from configuration
    level_name = settings.LOG_LEVEL.upper()
    level = getattr(logging, level_name, logging.INFO)
    root_logger.setLevel(level)

    # Re-route uvicorn loggers to root handler by enabling propagation
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        # Empty specialized uvicorn handlers to avoid duplicate output
        uv_logger.handlers = []
        uv_logger.propagate = True
