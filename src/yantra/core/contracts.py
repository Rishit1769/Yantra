"""Shared JSON-compatible identifiers and model capability declarations."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

type JsonObject = dict[str, object]


class ModelCapability(StrEnum):
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    TOKEN_USAGE = "token_usage"
    CANCELLATION = "cancellation"


class ProviderCapabilities(BaseModel):
    """Explicit capabilities for one configured provider/model deployment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_calling: bool = False
    structured_output: bool = False
    streaming: bool = False
    token_usage: bool = False
    cancellation: bool = False
    context_window_tokens: int | None = Field(default=None, ge=1)

    def supports(self, capability: ModelCapability) -> bool:
        """Return whether this deployment declares `capability`."""
        return bool(getattr(self, capability.value))


class TokenUsage(BaseModel):
    """Provider-reported token counts; absent counts remain unknown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def total_matches_components(self) -> TokenUsage:
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        return self
