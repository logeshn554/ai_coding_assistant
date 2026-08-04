import logging
import json
from app.config import settings
from app.logging_config import JSONFormatter, setup_logging

def test_json_formatter_outputs_valid_json():
    # Setup test record
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test_path.py",
        lineno=42,
        msg="Hello %s!",
        args=("World",),
        exc_info=None
    )
    
    formatter = JSONFormatter()
    output = formatter.format(record)
    
    # Assert output is valid json
    log_data = json.loads(output)
    assert log_data["level"] == "INFO"
    assert log_data["logger"] == "test_logger"
    assert log_data["message"] == "Hello World!"
    assert log_data["module"] == "test_path"
    assert log_data["lineno"] == 42
    assert "timestamp" in log_data


def test_setup_logging_toggles_formatters():
    # Save original settings
    orig_log_json = settings.LOG_JSON
    try:
        # Enable JSON logging
        settings.LOG_JSON = True
        setup_logging()
        
        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)
        
        # Disable JSON logging
        settings.LOG_JSON = False
        setup_logging()
        
        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        assert not isinstance(handler.formatter, JSONFormatter)
        
    finally:
        # Restore original settings
        settings.LOG_JSON = orig_log_json
        setup_logging()
