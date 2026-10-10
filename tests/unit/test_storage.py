import asyncio
from uuid import uuid4

import pytest

from yantra.core.errors import RecordNotFoundError, StorageConflictError
from yantra.core.events import RunCreatedEvent, RunStartedEvent
from yantra.core.messages import Message, MessageRole, TextContent
from yantra.storage.base import SessionRecord
from yantra.storage.memory import InMemoryStorage


@pytest.mark.asyncio
async def test_session_messages_and_events_round_trip() -> None:
    storage = InMemoryStorage()
    session = SessionRecord()
    run_id = uuid4()
    await storage.create_session(session)
    message = Message(role=MessageRole.USER, content=(TextContent(text="hello"),))
    await storage.append_message(session.session_id, message)
    created = RunCreatedEvent(
        session_id=session.session_id,
        run_id=run_id,
        sequence=1,
        agent_id="test.agent",
    )
    started = RunStartedEvent(session_id=session.session_id, run_id=run_id, sequence=2)
    await storage.append_event(created)
    await storage.append_event(started)

    assert await storage.get_session(session.session_id) == session
    assert await storage.list_messages(session.session_id) == (message,)
    assert await storage.list_events(session.session_id) == (created, started)
    assert await storage.list_events(session.session_id, run_id=run_id, after_sequence=1) == (
        started,
    )


@pytest.mark.asyncio
async def test_storage_instances_are_isolated() -> None:
    left = InMemoryStorage()
    right = InMemoryStorage()
    session = SessionRecord()
    await left.create_session(session)

    with pytest.raises(RecordNotFoundError):
        await right.get_session(session.session_id)


@pytest.mark.asyncio
async def test_missing_session_operations_raise_typed_error() -> None:
    storage = InMemoryStorage()
    session_id = uuid4()
    with pytest.raises(RecordNotFoundError):
        await storage.get_session(session_id)
    with pytest.raises(RecordNotFoundError):
        await storage.append_message(
            session_id,
            Message(role=MessageRole.USER, content=(TextContent(text="hello"),)),
        )
    with pytest.raises(RecordNotFoundError):
        await storage.list_events(session_id)


@pytest.mark.asyncio
async def test_event_sequence_and_session_conflicts_are_rejected() -> None:
    storage = InMemoryStorage()
    session = SessionRecord()
    await storage.create_session(session)
    run_id = uuid4()
    event = RunStartedEvent(session_id=session.session_id, run_id=run_id, sequence=2)
    with pytest.raises(StorageConflictError, match="expected event sequence 1"):
        await storage.append_event(event)

    first = RunCreatedEvent(
        session_id=session.session_id,
        run_id=run_id,
        sequence=1,
        agent_id="test.agent",
    )
    await storage.append_event(first)
    with pytest.raises(StorageConflictError, match="already exists"):
        await storage.append_event(first)


@pytest.mark.asyncio
async def test_concurrent_message_appends_are_not_lost() -> None:
    storage = InMemoryStorage()
    session = SessionRecord()
    await storage.create_session(session)
    messages = [
        Message(role=MessageRole.USER, content=(TextContent(text=f"message-{index}"),))
        for index in range(30)
    ]

    await asyncio.gather(
        *(storage.append_message(session.session_id, message) for message in messages)
    )

    assert len(await storage.list_messages(session.session_id)) == len(messages)


@pytest.mark.asyncio
async def test_storage_snapshots_do_not_share_mutable_payloads() -> None:
    storage = InMemoryStorage()
    session = SessionRecord()
    await storage.create_session(session)
    message = Message(
        role=MessageRole.USER,
        content=(TextContent(text="hello"),),
        metadata={"source": "original"},
    )
    await storage.append_message(session.session_id, message)
    message.metadata["source"] = "changed by caller"
    retrieved = (await storage.list_messages(session.session_id))[0]
    retrieved.metadata["source"] = "changed by reader"

    final_read = (await storage.list_messages(session.session_id))[0]
    assert final_read.metadata["source"] == "original"
