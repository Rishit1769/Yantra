"""Shared JSON-compatible identifiers and model capability declarations."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

type JsonObject = dict[str, object]


class ModelCapability(StrEnum):
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    TOKEN_USAGE = "token_usage"
    CANCELLATION = "cancellation"


class CapabilityStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class ProviderCapabilities(BaseModel):
    """Explicit capabilities for one configured provider/model deployment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_calling: bool | None = None
    structured_output: bool | None = None
    streaming: bool | None = None
    token_usage: bool | None = None
    cancellation: bool | None = None
    context_window_tokens: int | None = Field(default=None, ge=1)

    def supports(self, capability: ModelCapability) -> bool:
        """Return whether this deployment declares `capability`."""
        return getattr(self, capability.value) is True

    def status(self, capability: ModelCapability) -> CapabilityStatus:
        value = getattr(self, capability.value)
        if value is None:
            return CapabilityStatus.UNKNOWN
        return CapabilityStatus.SUPPORTED if value else CapabilityStatus.UNSUPPORTED


def merge_capabilities(
    baseline: ProviderCapabilities,
    specific: ProviderCapabilities | None,
) -> ProviderCapabilities:
    """Overlay known model-specific values without turning unknown into supported."""
    if specific is None:
        return baseline
    return ProviderCapabilities(
        tool_calling=(
            baseline.tool_calling if specific.tool_calling is None else specific.tool_calling
        ),
        structured_output=(
            baseline.structured_output
            if specific.structured_output is None
            else specific.structured_output
        ),
        streaming=baseline.streaming if specific.streaming is None else specific.streaming,
        token_usage=baseline.token_usage if specific.token_usage is None else specific.token_usage,
        cancellation=(
            baseline.cancellation if specific.cancellation is None else specific.cancellation
        ),
        context_window_tokens=(
            specific.context_window_tokens
            if specific.context_window_tokens is not None
            else baseline.context_window_tokens
        ),
    )


class TokenUsage(BaseModel):
    """Provider-reported token counts; absent counts remain unknown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    provider_reported_cost_usd: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def total_matches_components(self) -> TokenUsage:
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        if self.cached_input_tokens is not None and self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached_input_tokens cannot exceed input_tokens")
        if self.reasoning_tokens is not None and self.reasoning_tokens > self.output_tokens:
            raise ValueError("reasoning_tokens cannot exceed output_tokens")
        return self
