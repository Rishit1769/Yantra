"""Structured standard-library logging without configuring global handlers."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any, cast

_SENSITIVE_FIELD = re.compile(
    r"(?i)(?:^|[_-])(?:secret|password|api[_-]?key|access[_-]?token|authorization|credential)"
    r"(?:$|[_-])|(?:^|[_-])token$"
)
_SENSITIVE_TEXT = re.compile(
    r"(?i)(\b(?:api[_-]?key|access[_-]?token|password|secret|authorization)\b\s*[:=]\s*)"
    r"([^\s,;]+)"
)
_BEARER_TEXT = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_LEVEL_NAMES = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}
_RESERVED_LOG_FIELDS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _BEARER_TEXT.sub("Bearer [REDACTED]", _SENSITIVE_TEXT.sub(r"\1[REDACTED]", value))
    if isinstance(value, Mapping):
        mapping = cast(Mapping[Any, Any], value)
        return {
            str(key): "[REDACTED]" if _SENSITIVE_FIELD.search(str(key)) else _redact_value(item)
            for key, item in mapping.items()
        }
    if isinstance(value, (tuple, list)):
        sequence = cast(tuple[Any, ...] | list[Any], value)
        return tuple(_redact_value(item) for item in sequence)
    return value


class StructuredLogger:
    """Logger facade accepting named structured fields and context identifiers."""

    def __init__(self, logger: logging.Logger, context: Mapping[str, Any]) -> None:
        self._logger = logger
        self._context = dict(context)

    def debug(self, message: str, **fields: Any) -> None:
        self._log(logging.DEBUG, message, fields)

    def info(self, message: str, **fields: Any) -> None:
        self._log(logging.INFO, message, fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._log(logging.WARNING, message, fields)

    def error(self, message: str, **fields: Any) -> None:
        self._log(logging.ERROR, message, fields)

    def exception(self, message: str, **fields: Any) -> None:
        self._log(logging.ERROR, message, fields)

    def _log(
        self,
        level: int,
        message: str,
        fields: Mapping[str, Any],
    ) -> None:
        safe_fields = {
            key: "[REDACTED]" if _SENSITIVE_FIELD.search(key) else _redact_value(value)
            for key, value in (self._context | dict(fields)).items()
            if key not in _RESERVED_LOG_FIELDS
        }
        safe_message = _redact_value(message)
        self._logger.log(level, safe_message, extra=safe_fields)


def get_logger(name: str, *, level: int | str | None = None, **context: Any) -> StructuredLogger:
    """Get a namespaced logger; only the named logger is configured when level is set."""
    if not name or not name.strip():
        raise ValueError("logger name must be non-empty")
    logger = logging.getLogger(f"yantra.{name}")
    if level is not None:
        normalized_level = _LEVEL_NAMES.get(level.upper()) if isinstance(level, str) else level
        if not isinstance(normalized_level, int):
            raise ValueError(f"unknown logging level: {level}")
        logger.setLevel(normalized_level)
    return StructuredLogger(logger, context)
