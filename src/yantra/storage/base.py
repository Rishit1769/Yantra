"""Small async storage contract for sessions, messages, and execution events."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from yantra.core.events import ExecutionEvent
from yantra.core.messages import Message


class SessionRecord(BaseModel):
    """Session metadata stored independently from mutable message history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class Storage(Protocol):
    """Async boundary implemented by in-memory and future persistence adapters."""

    async def create_session(self, session: SessionRecord) -> None:
        """Create a new session or raise a storage conflict."""
        ...

    async def get_session(self, session_id: UUID) -> SessionRecord:
        """Return a session or raise RecordNotFoundError."""
        ...

    async def append_message(self, session_id: UUID, message: Message) -> None:
        """Append one immutable message to a session."""
        ...

    async def list_messages(self, session_id: UUID) -> tuple[Message, ...]:
        """Return messages in append order."""
        ...

    async def append_event(self, event: ExecutionEvent) -> None:
        """Append the next per-run event sequence for an existing session."""
        ...

    async def list_events(
        self,
        session_id: UUID,
        *,
        run_id: UUID | None = None,
        after_sequence: int = 0,
    ) -> tuple[ExecutionEvent, ...]:
        """List session events in append order, optionally filtered by run/cursor."""
        ...
