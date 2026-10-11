from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from yantra import __version__
from yantra.core.agent import AgentConfig
from yantra.core.budgets import ExecutionBudget
from yantra.core.contracts import TokenUsage
from yantra.core.events import RunCreatedEvent, deserialize_event, serialize_event
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall, ToolResult
from yantra.core.states import RunState, RunStateRecord, transition_state


def valid_agent(**changes: object) -> AgentConfig:
    values: dict[str, object] = {
        "agent_id": "example.reader",
        "name": "Reader",
        "system_instructions": "Read and summarize supplied text.",
        "provider_id": "mock",
        "model_id": "mock-small",
        "tool_references": ("demo.echo",),
    }
    values.update(changes)
    return AgentConfig(**values)


def test_agent_config_is_validated_and_immutable() -> None:
    config = valid_agent(metadata={"nested": {"items": ["original"]}})
    assert config.agent_id == "example.reader"
    with pytest.raises(ValidationError):
        config.name = "Changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        config.metadata["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        config.metadata["nested"]["items"][0] = "changed"  # type: ignore[index]
    assert config.model_dump(mode="json")["metadata"] == {"nested": {"items": ["original"]}}
    with pytest.raises(ValidationError):
        valid_agent(agent_id="invalid id")
    with pytest.raises(ValidationError):
        valid_agent(tool_references=("demo.echo", "demo.echo"))
    with pytest.raises(ValidationError):
        valid_agent(system_instructions="")


def test_budget_requires_positive_sensible_limits() -> None:
    assert ExecutionBudget().max_steps >= ExecutionBudget().max_model_calls
    with pytest.raises(ValidationError):
        ExecutionBudget(max_steps=2, max_model_calls=3)
    with pytest.raises(ValidationError):
        ExecutionBudget(max_tool_calls=-1)
    with pytest.raises(ValidationError):
        ExecutionBudget(max_wall_time_seconds=float("inf"))


def test_message_tool_call_round_trips_with_explicit_extension() -> None:
    message = Message(
        role=MessageRole.ASSISTANT,
        tool_calls=(ToolCall(call_id="call-1", name="demo.echo", arguments={"text": "hello"}),),
        provider_extensions={"vendor.chat": {"finish_reason": "tool_calls"}},
    )
    decoded = Message.from_json(message.to_json())
    assert decoded == message
    assert decoded.tool_calls[0].arguments == {"text": "hello"}
    with pytest.raises(ValidationError):
        Message(role=MessageRole.TOOL, content=(TextContent(text="orphan"),))
    with pytest.raises(ValidationError):
        Message(
            role=MessageRole.USER,
            content=(TextContent(text="hello"),),
            tool_result=ToolResult(call_id="call-1", name="demo.echo", result="hello"),
        )
    with pytest.raises(ValidationError):
        Message(
            role=MessageRole.USER,
            content=(TextContent(text="hello"),),
            provider_extensions={"unqualified": {"x": 1}},
        )


def test_reasoning_only_assistant_message_remains_private_provider_metadata() -> None:
    message = Message(
        role=MessageRole.ASSISTANT,
        provider_extensions={"deepseek.chat": {"reasoning_content": "private reasoning"}},
    )

    assert message.content == ()
    assert message.tool_calls == ()
    assert message.provider_extensions["deepseek.chat"]["reasoning_content"] == "private reasoning"
    with pytest.raises(ValidationError, match="reasoning metadata"):
        Message(role=MessageRole.ASSISTANT)


def test_tool_result_has_explicit_typed_linkage() -> None:
    result = ToolResult(call_id="call-1", name="demo.echo", result={"text": "hello"})
    message = Message(role=MessageRole.TOOL, tool_result=result)
    assert Message.from_json(message.to_json()).tool_result == result


def test_runtime_state_is_separate_and_transition_returns_new_snapshot() -> None:
    initial = RunStateRecord(
        run_id=uuid4(),
        session_id=uuid4(),
        agent_id="example.reader",
    )
    queued = transition_state(initial, RunState.QUEUED)
    assert initial.state == RunState.CREATED
    assert queued.state == RunState.QUEUED
    assert queued.version == initial.version + 1


def test_execution_events_are_versioned_and_serializable() -> None:
    event = RunCreatedEvent(
        session_id=uuid4(),
        run_id=uuid4(),
        sequence=1,
        agent_id="example.reader",
        occurred_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    assert deserialize_event(serialize_event(event)) == event
    assert event.event_type == "run.created"


def test_token_usage_requires_consistent_totals() -> None:
    assert TokenUsage(input_tokens=2, output_tokens=3, total_tokens=5).total_tokens == 5
    with pytest.raises(ValidationError):
        TokenUsage(input_tokens=2, output_tokens=3, total_tokens=6)


def test_package_has_version_metadata() -> None:
    assert __version__ == "0.1.0"
