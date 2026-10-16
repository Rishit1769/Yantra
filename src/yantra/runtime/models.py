"""Typed contracts for the YANTRA-003 agent loop."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from yantra.core.contracts import TokenUsage
from yantra.core.messages import Message, ToolResult
from yantra.core.states import RunState


class AgentTerminationReason(StrEnum):
    FINAL_RESPONSE = "final_response"
    MAX_STEPS = "max_steps"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    TOKEN_BUDGET = "token_budget"
    COST_BUDGET = "cost_budget"
    PROVIDER_FAILURE = "provider_failure"
    TOOL_FAILURE = "tool_failure"
    INVALID_RESPONSE = "invalid_response"


class AgentRunConfig(BaseModel):
    """Validated, finite configuration for one in-process agent run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = Field(min_length=1, max_length=512)
    messages: tuple[Message, ...] = Field(min_length=1)
    max_steps: int = Field(default=8, ge=1)
    max_tool_calls: int = Field(default=16, ge=0)
    timeout_seconds: float = Field(default=300.0, gt=0, allow_inf_nan=False)
    token_budget: int | None = Field(default=None, gt=0)
    cost_budget_usd: Decimal | None = Field(default=None, gt=0)
    tool_names: tuple[str, ...] = ()
    run_id: UUID = Field(default_factory=uuid4)
    session_id: UUID = Field(default_factory=uuid4)

    @field_validator("tool_names")
    @classmethod
    def tool_names_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("tool_names must be unique")
        return values


class AgentStep(BaseModel):
    """A compact record of one model invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=1)
    request_id: UUID
    response_message: Message
    usage: TokenUsage | None = None
    estimated_cost_usd: Decimal | None = None
    provider_reported_cost_usd: Decimal | None = None


class ExecutionTraceEntry(BaseModel):
    """Sanitized metadata for debugging; payloads and secrets are excluded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    step_index: int = Field(ge=0)
    event: str = Field(min_length=1, max_length=64)
    state: RunState
    tool_name: str | None = None
    call_id: str | None = None
    outcome: str | None = None
    usage: TokenUsage | None = None
    error_code: str | None = None


class AgentRunResult(BaseModel):
    """Final bounded outcome and sanitized execution trace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: UUID
    session_id: UUID
    state: RunState
    termination_reason: AgentTerminationReason
    final_message: Message | None = None
    steps: tuple[AgentStep, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()
    usage: TokenUsage | None = None
    usage_complete: bool = False
    total_cost_usd: Decimal | None = None
    cost_budget_enforced: bool = Field(
        default=False,
        description=(
            "Known post-response cost was checked to prevent further work; "
            "this is not a billing cap."
        ),
    )
    error_code: str | None = None
    error_message: str | None = None
    trace: tuple[ExecutionTraceEntry, ...] = ()

    @property
    def output(self) -> str | None:
        """Return visible final text without exposing provider reasoning metadata."""
        if self.final_message is None:
            return None
        return "".join(block.text for block in self.final_message.content)
