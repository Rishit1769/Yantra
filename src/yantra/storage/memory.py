"""Async in-memory storage adapter with isolated state and event ordering checks."""

from __future__ import annotations

import asyncio
from uuid import UUID

from yantra.core.errors import RecordNotFoundError, StorageConflictError
from yantra.core.events import ExecutionEvent
from yantra.core.messages import Message
from yantra.storage.base import SessionRecord


class InMemoryStorage:
    """Non-durable storage implementation for local use and deterministic tests."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[UUID, SessionRecord] = {}
        self._messages: dict[UUID, list[Message]] = {}
        self._events: dict[UUID, list[ExecutionEvent]] = {}
        self._run_sessions: dict[UUID, UUID] = {}
        self._run_sequences: dict[UUID, list[ExecutionEvent]] = {}
        self._event_ids: set[UUID] = set()

    async def create_session(self, session: SessionRecord) -> None:
        async with self._lock:
            if session.session_id in self._sessions:
                raise StorageConflictError(f"session {session.session_id} already exists")
            self._sessions[session.session_id] = session.model_copy(deep=True)
            self._messages[session.session_id] = []
            self._events[session.session_id] = []

    async def get_session(self, session_id: UUID) -> SessionRecord:
        async with self._lock:
            try:
                return self._sessions[session_id].model_copy(deep=True)
            except KeyError as exc:
                raise RecordNotFoundError(f"session {session_id} was not found") from exc

    async def append_message(self, session_id: UUID, message: Message) -> None:
        async with self._lock:
            if session_id not in self._sessions:
                raise RecordNotFoundError(f"session {session_id} was not found")
            self._messages[session_id].append(message.model_copy(deep=True))

    async def list_messages(self, session_id: UUID) -> tuple[Message, ...]:
        async with self._lock:
            if session_id not in self._sessions:
                raise RecordNotFoundError(f"session {session_id} was not found")
            return tuple(message.model_copy(deep=True) for message in self._messages[session_id])

    async def append_event(self, event: ExecutionEvent) -> None:
        async with self._lock:
            if event.session_id not in self._sessions:
                raise RecordNotFoundError(f"session {event.session_id} was not found")
            if event.event_id in self._event_ids:
                raise StorageConflictError(f"event {event.event_id} already exists")

            known_session = self._run_sessions.get(event.run_id)
            if known_session is not None and known_session != event.session_id:
                raise StorageConflictError("a run cannot be associated with multiple sessions")

            run_events = self._run_sequences.setdefault(event.run_id, [])
            expected_sequence = len(run_events) + 1
            if event.sequence != expected_sequence:
                raise StorageConflictError(
                    f"run {event.run_id} expected event sequence {expected_sequence}, "
                    f"received {event.sequence}"
                )

            self._run_sessions[event.run_id] = event.session_id
            stored_event = event.model_copy(deep=True)
            run_events.append(stored_event)
            self._events[event.session_id].append(stored_event)
            self._event_ids.add(event.event_id)

    async def list_events(
        self,
        session_id: UUID,
        *,
        run_id: UUID | None = None,
        after_sequence: int = 0,
    ) -> tuple[ExecutionEvent, ...]:
        if after_sequence < 0:
            raise ValueError("after_sequence cannot be negative")
        async with self._lock:
            if session_id not in self._sessions:
                raise RecordNotFoundError(f"session {session_id} was not found")
            return tuple(
                event.model_copy(deep=True)
                for event in self._events[session_id]
                if (run_id is None or event.run_id == run_id) and event.sequence > after_sequence
            )
