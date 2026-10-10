"""Run state enum and pure state-transition validation."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from yantra.core.errors import InvalidStateTransitionError


class RunState(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_MODEL = "waiting_for_model"
    WAITING_FOR_TOOL = "waiting_for_tool"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES: Final[frozenset[RunState]] = frozenset(
    {RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED}
)

_ALLOWED_TRANSITIONS: Final[dict[RunState, frozenset[RunState]]] = {
    RunState.CREATED: frozenset({RunState.QUEUED, RunState.CANCELLED, RunState.FAILED}),
    RunState.QUEUED: frozenset({RunState.RUNNING, RunState.CANCELLED, RunState.FAILED}),
    RunState.RUNNING: frozenset(
        {
            RunState.WAITING_FOR_MODEL,
            RunState.WAITING_FOR_TOOL,
            RunState.WAITING_FOR_APPROVAL,
            RunState.SUSPENDED,
            RunState.COMPLETED,
            RunState.FAILED,
            RunState.CANCELLED,
        }
    ),
    RunState.WAITING_FOR_MODEL: frozenset({RunState.RUNNING, RunState.FAILED, RunState.CANCELLED}),
    RunState.WAITING_FOR_TOOL: frozenset({RunState.RUNNING, RunState.FAILED, RunState.CANCELLED}),
    RunState.WAITING_FOR_APPROVAL: frozenset(
        {RunState.QUEUED, RunState.CANCELLED, RunState.FAILED}
    ),
    RunState.SUSPENDED: frozenset({RunState.QUEUED, RunState.CANCELLED, RunState.FAILED}),
    RunState.COMPLETED: frozenset(),
    RunState.FAILED: frozenset(),
    RunState.CANCELLED: frozenset(),
}


def is_terminal_state(state: RunState) -> bool:
    """Return whether the state is terminal."""
    return state in TERMINAL_STATES


def validate_transition(current: RunState, target: RunState) -> None:
    """Raise if `current -> target` is not a documented state transition."""
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidStateTransitionError(
            f"transition from {current.value} to {target.value} is invalid"
        )


class RunStateRecord(BaseModel):
    """Immutable run-state snapshot; transitions return a new snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: UUID
    session_id: UUID
    agent_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
    state: RunState = RunState.CREATED
    version: int = Field(default=0, ge=0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("updated_at")
    @classmethod
    def timestamp_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updated_at must be timezone-aware")
        return value


def transition_state(record: RunStateRecord, target: RunState) -> RunStateRecord:
    """Return a new state snapshot after validating and incrementing its version."""
    validate_transition(record.state, target)
    return RunStateRecord(
        run_id=record.run_id,
        session_id=record.session_id,
        agent_id=record.agent_id,
        state=target,
        version=record.version + 1,
    )
