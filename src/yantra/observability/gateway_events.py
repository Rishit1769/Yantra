"""Redacted gateway audit events suitable for logs and later event integration."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class GatewayEventType(StrEnum):
    CREDENTIAL_VALIDATION = "gateway.credential_validation"
    MODEL_SELECTED = "gateway.model_selected"
    REQUEST_STARTED = "gateway.request_started"
    REQUEST_COMPLETED = "gateway.request_completed"
    REQUEST_FAILED = "gateway.request_failed"
    RETRY = "gateway.retry"
    FALLBACK = "gateway.fallback"


class GatewayEvent(BaseModel):
    """Metadata-only event; prompt, response, and credential content is excluded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: GatewayEventType
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_id: UUID | None = None
    provider_id: str | None = None
    model_id: str | None = None
    error_code: str | None = None
    reason: str | None = Field(default=None, max_length=512)
    attempt: int | None = Field(default=None, ge=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
