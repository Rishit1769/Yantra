"""Versioned execution event models and JSON serialization helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, field_validator

from yantra.core.contracts import TokenUsage
from yantra.core.messages import ToolResult


class EventEnvelope(BaseModel):
    """Fields shared by immutable execution observations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1"
    event_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    run_id: UUID
    sequence: int = Field(ge=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def timestamp_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value


class RunCreatedEvent(EventEnvelope):
    event_type: Literal["run.created"] = "run.created"
    agent_id: str = Field(min_length=1, max_length=128)


class RunStartedEvent(EventEnvelope):
    event_type: Literal["run.started"] = "run.started"


class ModelRequestCreatedEvent(EventEnvelope):
    event_type: Literal["model.request_created"] = "model.request_created"
    request_id: UUID
    provider_id: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=256)


class ModelResponseReceivedEvent(EventEnvelope):
    event_type: Literal["model.response_received"] = "model.response_received"
    request_id: UUID
    provider_id: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=256)
    usage: TokenUsage | None = None


class ToolCallRequestedEvent(EventEnvelope):
    event_type: Literal["tool.call_requested"] = "tool.call_requested"
    call_id: str = Field(min_length=1, max_length=128)
    tool_name: str = Field(min_length=1, max_length=128)


class ToolExecutionStartedEvent(EventEnvelope):
    event_type: Literal["tool.execution_started"] = "tool.execution_started"
    execution_id: UUID
    call_id: str = Field(min_length=1, max_length=128)
    tool_name: str = Field(min_length=1, max_length=128)


class ToolExecutionCompletedEvent(EventEnvelope):
    event_type: Literal["tool.execution_completed"] = "tool.execution_completed"
    execution_id: UUID
    result: ToolResult


class ToolExecutionFailedEvent(EventEnvelope):
    event_type: Literal["tool.execution_failed"] = "tool.execution_failed"
    execution_id: UUID
    error_code: str = Field(min_length=1, max_length=128)
    message: str = Field(max_length=2000)


class RunCompletedEvent(EventEnvelope):
    event_type: Literal["run.completed"] = "run.completed"
    output: str = Field(max_length=100_000)


class RunFailedEvent(EventEnvelope):
    event_type: Literal["run.failed"] = "run.failed"
    error_code: str = Field(min_length=1, max_length=128)
    message: str = Field(max_length=2000)


class RunCancelledEvent(EventEnvelope):
    event_type: Literal["run.cancelled"] = "run.cancelled"
    reason: str = Field(default="cancelled", max_length=512)


type ExecutionEvent = Annotated[
    RunCreatedEvent
    | RunStartedEvent
    | ModelRequestCreatedEvent
    | ModelResponseReceivedEvent
    | ToolCallRequestedEvent
    | ToolExecutionStartedEvent
    | ToolExecutionCompletedEvent
    | ToolExecutionFailedEvent
    | RunCompletedEvent
    | RunFailedEvent
    | RunCancelledEvent,
    Field(discriminator="event_type"),
]

_EVENT_ADAPTER = TypeAdapter(ExecutionEvent)


def serialize_event(event: ExecutionEvent) -> str:
    """Serialize an event as a JSON envelope with its stable event type."""
    return event.model_dump_json()


def deserialize_event(value: str | bytes) -> ExecutionEvent:
    """Deserialize a versioned event and reject unknown event types/fields."""
    return _EVENT_ADAPTER.validate_json(value)
