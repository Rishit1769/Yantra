"""Provider-neutral asynchronous completion protocol and request models."""

from __future__ import annotations

from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from yantra.core.contracts import ModelCapability, ProviderCapabilities, TokenUsage
from yantra.core.messages import Message, MessageRole
from yantra.core.tools_schema import ProviderToolSchema


class FinishReason(StrEnum):
    STOP = "stop"
    TOOL_CALLS = "tool_calls"
    LENGTH = "length"
    REFUSAL = "refusal"
    UNKNOWN = "unknown"


class ModelProtocol(StrEnum):
    OPENAI_RESPONSES = "openai_responses"
    OPENAI_CHAT = "openai_chat_completions"
    ANTHROPIC_MESSAGES = "anthropic_messages"
    GEMINI_CONTENT = "gemini_generate_content"
    OLLAMA_CHAT = "ollama_chat"
    SYSTEM_ONE = "system_one"


class GenerationSettings(BaseModel):
    """Common generation settings with provider-specific options kept separate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    temperature: float | None = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    top_p: float | None = Field(default=None, gt=0, le=1, allow_inf_nan=False)
    max_output_tokens: int | None = Field(default=None, ge=1)
    stop_sequences: tuple[str, ...] = ()


class ModelStreamEventType(StrEnum):
    RESPONSE_STARTED = "response_started"
    TEXT_DELTA = "text_delta"
    REASONING_DELTA = "reasoning_delta"
    TOOL_CALL_DELTA = "tool_call_delta"
    USAGE = "usage"
    RESPONSE_COMPLETED = "response_completed"
    RESPONSE_FAILED = "response_failed"


class ToolCallDelta(BaseModel):
    """A tool-call fragment with stable call index and provider ID when sent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    call_id: str | None = None
    name_delta: str | None = None
    arguments_delta: str = ""


class ModelStreamEvent(BaseModel):
    """Normalized streaming event; absent data remains unknown, never synthesized."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: ModelStreamEventType
    request_id: UUID
    provider_id: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=256)
    text_delta: str | None = None
    tool_call_delta: ToolCallDelta | None = None
    usage: TokenUsage | None = None
    finish_reason: FinishReason | None = None
    error_code: str | None = None
    error_message: str | None = None


class ModelRequest(BaseModel):
    """Normalized request passed to a provider adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID = Field(default_factory=uuid4)
    model_id: str = Field(min_length=1, max_length=256)
    messages: tuple[Message, ...] = Field(min_length=1)
    tools: tuple[ProviderToolSchema, ...] = ()
    required_capabilities: frozenset[ModelCapability] = frozenset()
    response_schema: dict[str, JsonValue] | None = None
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    provider_options: dict[str, JsonValue] = Field(default_factory=dict)
    estimated_input_tokens: int | None = Field(default=None, ge=0)
    timeout_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("tools")
    @classmethod
    def request_tool_names_are_unique(
        cls, values: tuple[ProviderToolSchema, ...]
    ) -> tuple[ProviderToolSchema, ...]:
        names = tuple(tool.name for tool in values)
        if len(names) != len(set(names)):
            raise ValueError("request tool names must be unique")
        return values

    @model_validator(mode="after")
    def required_capabilities_match_request(self) -> ModelRequest:
        if self.tools and ModelCapability.TOOL_CALLING not in self.required_capabilities:
            raise ValueError("requests containing tools must require tool_calling capability")
        if (
            self.response_schema
            and ModelCapability.STRUCTURED_OUTPUT not in self.required_capabilities
        ):
            raise ValueError("requests containing a response schema must require structured_output")
        return self


class ModelResponse(BaseModel):
    """Normalized assistant response from a provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    provider_id: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=256)
    message: Message
    finish_reason: FinishReason = FinishReason.UNKNOWN
    usage: TokenUsage | None = None
    provider_request_id: str | None = Field(default=None, max_length=256)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def response_message_is_assistant(cls, value: Message) -> Message:
        if value.role != MessageRole.ASSISTANT:
            raise ValueError("model responses must contain an assistant message")
        return value


class ModelResponseChunk(BaseModel):
    """YANTRA-001 simple chunk contract, retained for compatibility."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    index: int = Field(ge=0)
    text_delta: str = ""
    tool_call_delta: JsonValue | None = None
    is_final: bool = False


class ModelProvider(Protocol):
    """Minimal async provider contract; capability support varies by adapter."""

    @property
    def provider_id(self) -> str:
        """Stable provider adapter identifier."""
        ...

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Capabilities of the selected provider/model deployment."""
        ...

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Complete a normalized request or raise a sanitized ProviderError.

        Adapters must honor `timeout_seconds` and must not swallow task cancellation.
        Remote cancellation support is declared separately in provider capabilities.
        """
        ...


@runtime_checkable
class StreamingModelProvider(ModelProvider, Protocol):
    """Optional streaming protocol separate from the minimum provider contract."""

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        """Stream normalized response deltas; consumer cancellation is propagated."""
        ...


def missing_capabilities(
    capabilities: ProviderCapabilities, required: frozenset[ModelCapability]
) -> frozenset[ModelCapability]:
    """Return required capabilities not declared by an adapter."""
    return frozenset(capability for capability in required if not capabilities.supports(capability))
