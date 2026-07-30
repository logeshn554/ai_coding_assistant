import logging
from agent_os.core.logging import StandardLogger

def test_standard_logger_methods():
    logger = StandardLogger("TestLogger")
    # Verify no exceptions raised during standard logging streams
    logger.debug("Debug log message")
    logger.info("Info log message")
    logger.warning("Warning log message")
    logger.error("Error log message")
    logger.critical("Critical log message")
