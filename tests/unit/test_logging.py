import logging

from yantra.observability.logging import get_logger


def test_logger_is_namespaced_and_redacts_sensitive_values(caplog) -> None:
    logger = get_logger("test", level="INFO", run_id="run-1", api_key="do-not-log")
    with caplog.at_level(logging.INFO, logger="yantra.test"):
        logger.info(
            "provider request password=hidden",
            session_id="session-1",
            token_count=12,
            authorization="Bearer should-not-log",
        )

    record = caplog.records[-1]
    assert record.name == "yantra.test"
    assert record.run_id == "run-1"
    assert record.api_key == "[REDACTED]"
    assert record.session_id == "session-1"
    assert record.authorization == "[REDACTED]"
    assert record.token_count == 12
    assert "hidden" not in record.getMessage()
    assert "should-not-log" not in record.getMessage()


def test_exception_logging_does_not_emit_unsanitized_traceback(caplog) -> None:
    logger = get_logger("exception", level="ERROR")
    with caplog.at_level(logging.ERROR, logger="yantra.exception"):
        try:
            raise RuntimeError("password=exception-secret")
        except RuntimeError:
            logger.exception("operation failed")

    record = caplog.records[-1]
    assert record.exc_info is None
    assert "exception-secret" not in caplog.text
