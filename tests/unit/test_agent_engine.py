import asyncio
from collections.abc import Callable, Sequence
from decimal import Decimal

import pytest
from pydantic import BaseModel, Field

from yantra.core.contracts import ProviderCapabilities, TokenUsage
from yantra.core.errors import ProviderError
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.core.states import RunState
from yantra.providers.base import FinishReason, ModelRequest, ModelResponse
from yantra.providers.gateway import ModelGateway
from yantra.providers.registry import ProviderRegistry
from yantra.runtime import (
    AgentExecutionEngine,
    AgentRunConfig,
    AgentTerminationReason,
    CancellationToken,
)
from yantra.tools import ExecutionMode, SideEffect, ToolDefinition, ToolRegistry


def user_message(text: str = "hello") -> Message:
    return Message(role=MessageRole.USER, content=(TextContent(text=text),))


class SequenceProvider:
    provider_id = "test"
    capabilities = ProviderCapabilities(tool_calling=True, token_usage=True, cancellation=True)

    def __init__(
        self, factories: Sequence[Callable[[ModelRequest], ModelResponse | Exception]]
    ) -> None:
        self.factories = list(factories)
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        outcome = self.factories.pop(0)
        if callable(outcome):
            outcome = outcome(request)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class SlowProvider(SequenceProvider):
    async def complete(self, request: ModelRequest) -> ModelResponse:
        await asyncio.sleep(1)
        return await super().complete(request)


def text_response(
    request: ModelRequest, text: str, usage: TokenUsage | None = None
) -> ModelResponse:
    return ModelResponse(
        request_id=request.request_id,
        provider_id="test",
        model_id=request.model_id,
        message=Message(
            role=MessageRole.ASSISTANT,
            content=(TextContent(text=text),),
        ),
        finish_reason=FinishReason.STOP,
        usage=usage,
    )


def tool_response(
    request: ModelRequest,
    calls: tuple[ToolCall, ...],
    usage: TokenUsage | None = None,
) -> ModelResponse:
    return ModelResponse(
        request_id=request.request_id,
        provider_id="test",
        model_id=request.model_id,
        message=Message(role=MessageRole.ASSISTANT, tool_calls=calls),
        finish_reason=FinishReason.TOOL_CALLS,
        usage=usage,
    )


def engine_for(
    provider: SequenceProvider, registry: ToolRegistry | None = None
) -> AgentExecutionEngine:
    providers = ProviderRegistry()
    providers.register(provider, is_local=True)
    gateway = ModelGateway(providers)
    return AgentExecutionEngine(gateway, registry or ToolRegistry())


def echo_registry() -> ToolRegistry:
    class EchoInput(BaseModel):
        text: str = Field(min_length=1)

    class EchoOutput(BaseModel):
        text: str

    def echo(arguments: EchoInput) -> EchoOutput:
        return EchoOutput(text=arguments.text)

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="demo.echo",
            input_model=EchoInput,
            output_model=EchoOutput,
            executor=echo,
            execution_mode=ExecutionMode.SYNC,
            side_effect=SideEffect.READ_ONLY,
        )
    )
    return registry


@pytest.mark.asyncio
async def test_single_response_completes_and_accumulates_usage() -> None:
    provider = SequenceProvider(
        [
            lambda request: text_response(
                request,
                "done",
                TokenUsage(input_tokens=2, output_tokens=3, total_tokens=5),
            )
        ]
    )
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),))
    )

    assert result.state == RunState.COMPLETED
    assert result.termination_reason == AgentTerminationReason.FINAL_RESPONSE
    assert result.output == "done"
    assert result.usage is not None and result.usage.total_tokens == 5
    assert result.usage_complete


@pytest.mark.asyncio
async def test_tool_result_is_ordered_and_returned_to_model() -> None:
    registry = echo_registry()
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (
                    ToolCall(call_id="call-1", name="demo.echo", arguments={"text": "one"}),
                    ToolCall(call_id="call-2", name="demo.echo", arguments={"text": "two"}),
                ),
            ),
            lambda request: text_response(request, "observed"),
        ]
    )
    result = await engine_for(provider, registry).run(
        AgentRunConfig(model="test/model", messages=(user_message(),))
    )

    assert result.output == "observed"
    assert [item.call_id for item in result.tool_results] == ["call-1", "call-2"]
    tool_messages = [
        message for message in provider.requests[1].messages if message.role == MessageRole.TOOL
    ]
    assert [message.tool_result.call_id for message in tool_messages if message.tool_result] == [
        "call-1",
        "call-2",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call", "expected_code"),
    [
        (ToolCall(call_id="call-1", name="missing", arguments={}), "tool_not_found"),
        (ToolCall(call_id="call-1", name="demo.echo", arguments={"text": ""}), "invalid_arguments"),
    ],
)
async def test_tool_failures_become_structured_observations(
    call: ToolCall, expected_code: str
) -> None:
    provider = SequenceProvider(
        [
            lambda request: tool_response(request, (call,)),
            lambda request: text_response(request, "recovered"),
        ]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(model="test/model", messages=(user_message(),))
    )

    assert result.output == "recovered"
    assert result.tool_results[0].is_error
    assert result.tool_results[0].result["error_code"] == expected_code


@pytest.mark.asyncio
async def test_tool_exception_and_timeout_are_structured_observations() -> None:
    class Input(BaseModel):
        value: str

    async def broken(_: Input) -> dict[str, str]:
        raise RuntimeError("secret should not be exposed")

    async def slow(_: Input) -> dict[str, str]:
        await asyncio.sleep(1)
        return {"value": "done"}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="demo.broken",
            input_model=Input,
            executor=broken,
            execution_mode=ExecutionMode.ASYNC,
        )
    )
    registry.register(
        ToolDefinition(
            name="demo.timeout",
            input_model=Input,
            executor=slow,
            execution_mode=ExecutionMode.ASYNC,
            timeout_seconds=0.01,
        )
    )
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (
                    ToolCall(call_id="broken", name="demo.broken", arguments={"value": "x"}),
                    ToolCall(call_id="timeout", name="demo.timeout", arguments={"value": "x"}),
                ),
            ),
            lambda request: text_response(request, "recovered"),
        ]
    )
    result = await engine_for(provider, registry).run(
        AgentRunConfig(model="test/model", messages=(user_message(),))
    )

    assert result.output == "recovered"
    assert [item.result["error_code"] for item in result.tool_results] == [
        "tool_exception",
        "tool_timeout",
    ]
    assert "secret" not in str(result.model_dump())


@pytest.mark.asyncio
async def test_max_steps_prevents_repeated_tool_loop() -> None:
    calls = [
        ToolCall(call_id=f"call-{index}", name="demo.echo", arguments={"text": "x"})
        for index in range(3)
    ]
    provider = SequenceProvider(
        [lambda request, call=call: tool_response(request, (call,)) for call in calls]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), max_steps=2)
    )

    assert result.termination_reason == AgentTerminationReason.MAX_STEPS
    assert len(provider.requests) == 2


@pytest.mark.asyncio
async def test_explicit_cancellation_cancels_in_flight_async_tool() -> None:
    class Input(BaseModel):
        value: str

    async def slow(_: Input) -> dict[str, str]:
        await asyncio.sleep(10)
        return {"value": "done"}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="demo.slow",
            input_model=Input,
            executor=slow,
            execution_mode=ExecutionMode.ASYNC,
            side_effect=SideEffect.READ_ONLY,
        )
    )
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request, (ToolCall(call_id="slow-1", name="demo.slow", arguments={"value": "x"}),)
            )
        ]
    )
    token = CancellationToken()
    task = asyncio.create_task(
        engine_for(provider, registry).run(
            AgentRunConfig(model="test/model", messages=(user_message(),)), cancellation=token
        )
    )
    await asyncio.sleep(0.02)
    token.cancel()
    result = await task

    assert result.state == RunState.CANCELLED
    assert result.termination_reason == AgentTerminationReason.CANCELLED


@pytest.mark.asyncio
async def test_provider_failure_is_structured_and_external_cancellation_propagates() -> None:
    provider = SequenceProvider(
        [lambda request: ProviderError("provider broke", provider_id="test")]
    )
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),))
    )
    assert result.termination_reason == AgentTerminationReason.PROVIDER_FAILURE
    assert result.error_code == "provider_error"

    pending_provider = SequenceProvider([lambda request: text_response(request, "late")])
    task = asyncio.create_task(
        engine_for(pending_provider).run(
            AgentRunConfig(model="test/model", messages=(user_message(),))
        )
    )
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_wall_clock_timeout_covers_model_request() -> None:
    provider = SlowProvider([lambda request: text_response(request, "late")])
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), timeout_seconds=0.01)
    )
    assert result.state == RunState.FAILED
    assert result.termination_reason == AgentTerminationReason.TIMEOUT


@pytest.mark.asyncio
async def test_missing_usage_is_reported_without_fabrication() -> None:
    provider = SequenceProvider([lambda request: text_response(request, "done")])
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), token_budget=1)
    )
    assert result.output == "done"
    assert result.usage is None
    assert not result.usage_complete


@pytest.mark.asyncio
async def test_token_and_cost_budgets_terminate_when_reliably_reported() -> None:
    usage = TokenUsage(
        input_tokens=1,
        output_tokens=1,
        total_tokens=2,
        provider_reported_cost_usd=Decimal("0.10"),
    )
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="call-1", name="demo.echo", arguments={"text": "x"}),),
                usage,
            )
        ]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(
            model="test/model",
            messages=(user_message(),),
            token_budget=3,
            cost_budget_usd=Decimal("0.05"),
        )
    )
    assert result.termination_reason == AgentTerminationReason.COST_BUDGET
    assert result.total_cost_usd == Decimal("0.10")
    assert result.cost_budget_enforced


@pytest.mark.asyncio
async def test_token_budget_stops_before_more_tool_execution() -> None:
    usage = TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2)
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="call-1", name="demo.echo", arguments={"text": "x"}),),
                usage,
            )
        ]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), token_budget=2)
    )
    assert result.termination_reason == AgentTerminationReason.TOKEN_BUDGET
    assert result.tool_results == ()


@pytest.mark.asyncio
async def test_duplicate_call_ids_are_not_executed() -> None:
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (
                    ToolCall(call_id="same", name="demo.echo", arguments={"text": "a"}),
                    ToolCall(call_id="same", name="demo.echo", arguments={"text": "b"}),
                ),
            )
        ]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(model="test/model", messages=(user_message(),))
    )
    assert result.termination_reason == AgentTerminationReason.INVALID_RESPONSE
    assert result.tool_results == ()
    assert all(entry.call_id is None for entry in result.trace)
