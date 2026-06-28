import logging
from symphony.log import get_logger, setup_logging


def test_get_logger_returns_bound_logger():
    setup_logging()
    log = get_logger("test")
    # Should not raise
    log.info("test message", key="value")


def test_logger_with_context():
    setup_logging()
    log = get_logger().bind(issue_id="abc", identifier="PRJ-1")
    log.info("dispatch", attempt=1)  # Should not raise


def test_logging_error_does_not_raise():
    """Sink failures must never propagate."""
    setup_logging()
    log = get_logger()
    log.error("something failed", exc_info=ValueError("test"))
