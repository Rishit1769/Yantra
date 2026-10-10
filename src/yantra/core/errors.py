"""Stable, sanitized errors shared by runtime contracts and adapters."""

from __future__ import annotations

import re

_SECRET_PATTERN = re.compile(
    r"(?i)(\b(?:api[_-]?key|access[_-]?token|password|secret|authorization)\b\s*[:=]\s*)"
    r"([^\s,;]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")


def _safe_message(message: str) -> str:
    redacted = _SECRET_PATTERN.sub(r"\1[REDACTED]", message)
    return _BEARER_PATTERN.sub("Bearer [REDACTED]", redacted)[:2000]


class YantraError(Exception):
    """Base class for public YANTRA errors."""

    code = "yantra_error"

    def __init__(self, message: str) -> None:
        self.message = _safe_message(message)
        super().__init__(self.message)


class ConfigurationError(YantraError):
    """Invalid agent or runtime configuration."""

    code = "configuration_error"


class ProviderError(YantraError):
    """Normalized provider failure without raw credential-bearing payloads."""

    code = "provider_error"

    def __init__(
        self,
        message: str,
        *,
        provider_id: str | None = None,
        retryable: bool = False,
    ) -> None:
        self.provider_id = provider_id
        self.retryable = retryable
        super().__init__(message)

    def clone(self) -> ProviderError:
        """Return a fresh exception preserving normalized provider metadata."""
        return type(self)(
            self.message,
            provider_id=self.provider_id,
            retryable=self.retryable,
        )


class ProviderTimeoutError(ProviderError):
    """Provider request exceeded its deadline."""

    code = "provider_timeout"


class UnsupportedCapabilityError(ProviderError):
    """A provider does not support a required capability."""

    code = "unsupported_capability"


class MockResponseSequenceExhaustedError(ProviderError):
    """The deterministic mock has no remaining configured responses."""

    code = "mock_response_sequence_exhausted"


class ToolError(YantraError):
    """Base class for tool contract and validation errors."""

    code = "tool_error"


class ToolValidationError(ToolError):
    """Tool input or output did not match its declared schema."""

    code = "tool_validation_error"


class ToolNotFoundError(ToolError):
    """A named tool is not present in the registry."""

    code = "tool_not_found"


class ToolRegistrationError(ToolError):
    """A tool could not be registered."""

    code = "tool_registration_error"


class DuplicateToolError(ToolRegistrationError):
    """A tool name is already registered."""

    code = "duplicate_tool"


class InvalidToolDefinitionError(ToolRegistrationError):
    """A tool definition or its JSON Schema is invalid."""

    code = "invalid_tool_definition"


class InvalidStateTransitionError(YantraError):
    """A run state transition is not allowed by the state machine."""

    code = "invalid_state_transition"


class StorageError(YantraError):
    """Base class for storage adapter failures."""

    code = "storage_error"


class StorageConflictError(StorageError):
    """A storage uniqueness or optimistic ordering invariant was violated."""

    code = "storage_conflict"


class RecordNotFoundError(StorageError):
    """A requested in-memory record does not exist."""

    code = "record_not_found"


class ExecutionBudgetError(YantraError):
    """An execution budget configuration or accounting value is invalid."""

    code = "execution_budget_error"
