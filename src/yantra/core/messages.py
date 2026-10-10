"""Provider-neutral, typed conversation and tool-call messages."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator


class MessageRole(StrEnum):
    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class TextContent(BaseModel):
    """A textual content block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str = Field(default="text", pattern="^text$")
    text: str


class ToolCall(BaseModel):
    """Untrusted model-proposed tool name and JSON arguments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    arguments: dict[str, JsonValue]


class ToolResult(BaseModel):
    """Normalized observation returned by a tool invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    result: JsonValue
    is_error: bool = False


class Message(BaseModel):
    """A versioned provider-neutral message with explicit extensions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1"
    message_id: UUID = Field(default_factory=uuid4)
    role: MessageRole
    content: tuple[TextContent, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    tool_result: ToolResult | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    provider_extensions: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def timestamp_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @field_validator("provider_extensions")
    @classmethod
    def extension_namespaces_are_explicit(
        cls, values: dict[str, dict[str, JsonValue]]
    ) -> dict[str, dict[str, JsonValue]]:
        for namespace in values:
            if not namespace or "." not in namespace:
                raise ValueError("provider extension namespaces must be qualified, e.g. vendor.api")
        return values

    @model_validator(mode="after")
    def validate_role_payload(self) -> Message:
        if self.role == MessageRole.TOOL and self.tool_result is None:
            raise ValueError("tool messages require a tool_result")
        if self.role != MessageRole.TOOL and self.tool_result is not None:
            raise ValueError("tool_result is only valid on tool messages")
        if self.tool_calls and self.role != MessageRole.ASSISTANT:
            raise ValueError("tool_calls are only valid on assistant messages")
        if self.role in (MessageRole.SYSTEM, MessageRole.DEVELOPER, MessageRole.USER):
            if not self.content:
                raise ValueError(f"{self.role.value} messages require text content")
        elif self.role == MessageRole.ASSISTANT and not self.content and not self.tool_calls:
            raise ValueError("assistant messages require content or tool calls")
        elif self.role == MessageRole.TOOL and not self.content and self.tool_result is None:
            raise ValueError("tool messages require content or a tool result")
        return self

    @classmethod
    def from_json(cls, value: str | bytes) -> Message:
        """Parse a serialized message, rejecting unknown fields and invalid roles."""
        return cls.model_validate_json(value)

    def to_json(self) -> str:
        """Serialize using the stable Pydantic JSON representation."""
        return self.model_dump_json()


def text_message(role: MessageRole, text: str) -> Message:
    """Construct a message containing exactly one text block."""
    return Message(role=role, content=(TextContent(text=text),))
