"""Execution result contracts; the execution loop is implemented in a later milestone."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from yantra.core.messages import Message
from yantra.core.states import RunState


class ErrorSummary(BaseModel):
    """Safe, structured error details suitable for a result payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(max_length=2000)


class ExecutionResult(BaseModel):
    """Contract for a future runtime result, not produced by an execution loop yet."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: UUID
    session_id: UUID
    state: RunState
    output: Message | None = None
    error: ErrorSummary | None = None
