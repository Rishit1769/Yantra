import asyncio
from collections.abc import Callable, Sequence
from decimal import Decimal

import pytest
from pydantic import BaseModel, Field

from yantra.core.contracts import ProviderCapabilities, TokenUsage
from yantra.core.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.core.states import RunState
from yantra.providers.adapters.common import chat_request_messages
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
    def __init__(
        self, factories: Sequence[Callable[[ModelRequest], ModelResponse | Exception]]
    ) -> None:
        super().__init__(factories)
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        outcome = self.factories.pop(0)
        if callable(outcome):
            outcome = outcome(request)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


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
    round_tripped = [
        Message.model_validate_json(message.model_dump_json()) for message in tool_messages
    ]
    assert [message.tool_result.name for message in round_tripped if message.tool_result] == [
        "demo.echo",
        "demo.echo",
    ]
    protocol_messages = chat_request_messages(provider.requests[1].messages, provider_id="test")
    assert protocol_messages[1]["tool_calls"][0]["id"] == "call-1"
    assert protocol_messages[2]["tool_call_id"] == "call-1"
    assert protocol_messages[3]["tool_call_id"] == "call-2"


@pytest.mark.asyncio
async def test_multi_turn_workflow_preserves_history_and_allows_repeated_tool_name() -> None:
    registry = echo_registry()
    usage = TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2)
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="repeat-1", name="demo.echo", arguments={"text": "first"}),),
                usage,
            ),
            lambda request: tool_response(
                request,
                (ToolCall(call_id="repeat-2", name="demo.echo", arguments={"text": "second"}),),
                usage,
            ),
            lambda request: text_response(request, "combined", usage),
        ]
    )
    result = await engine_for(provider, registry).run(
        AgentRunConfig(
            model="test/model",
            messages=(user_message("task"),),
            max_steps=3,
            tool_names=("demo.echo",),
        )
    )

    assert result.output == "combined"
    assert result.state == RunState.COMPLETED
    assert [step.index for step in result.steps] == [1, 2, 3]
    assert [item.call_id for item in result.tool_results] == ["repeat-1", "repeat-2"]
    assert result.usage is not None and result.usage.total_tokens == 6
    history = provider.requests[-1].messages
    assert [message.role for message in history] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
        MessageRole.TOOL,
        MessageRole.ASSISTANT,
        MessageRole.TOOL,
    ]
    assert provider.requests[-1].model_id == "model"


@pytest.mark.asyncio
async def test_tool_name_allowlist_blocks_registered_but_disabled_tool() -> None:
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="not-allowed", name="demo.echo", arguments={"text": "x"}),),
            ),
            lambda request: text_response(request, "observed failure"),
        ]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(
            model="test/model",
            messages=(user_message(),),
            tool_names=("demo.other",),
        )
    )

    assert result.tool_results[0].is_error
    assert result.tool_results[0].result["error_code"] == "tool_not_permitted"


@pytest.mark.asyncio
async def test_empty_allowlist_denies_every_registered_tool_and_advertises_none() -> None:
    calls = 0

    class Input(BaseModel):
        text: str

    def side_effect(arguments: Input) -> Input:
        nonlocal calls
        calls += 1
        return arguments

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="demo.echo",
            input_model=Input,
            executor=side_effect,
            execution_mode=ExecutionMode.SYNC,
        )
    )
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="denied-1", name="demo.echo", arguments={"text": "x"}),),
            ),
            lambda request: text_response(request, "denial observed"),
        ]
    )

    result = await engine_for(provider, registry).run(
        AgentRunConfig(model="test/model", messages=(user_message(),))
    )

    assert calls == 0
    assert provider.requests[0].tools == ()
    assert result.tool_results[0].call_id == "denied-1"
    assert result.tool_results[0].result["error_code"] == "tool_not_permitted"
    assert len(provider.requests) == 2


@pytest.mark.asyncio
async def test_allowlist_advertises_only_authorized_tool_and_unknown_names_fail_closed() -> None:
    registry = echo_registry()

    def other(arguments: BaseModel) -> BaseModel:
        return arguments

    class Input(BaseModel):
        value: int

    registry.register(
        ToolDefinition(
            name="demo.other",
            input_model=Input,
            executor=other,
            execution_mode=ExecutionMode.SYNC,
        )
    )
    provider = SequenceProvider([lambda request: text_response(request, "done")])
    await engine_for(provider, registry).run(
        AgentRunConfig(
            model="test/model",
            messages=(user_message(),),
            tool_names=("demo.echo", "not.registered"),
        )
    )
    assert [schema.name for schema in provider.requests[0].tools] == ["demo.echo"]


@pytest.mark.asyncio
async def test_multiple_tools_authorize_and_execute_only_named_tool() -> None:
    invoked: list[str] = []
    registry = echo_registry()

    class Input(BaseModel):
        value: int

    def restricted(arguments: Input) -> Input:
        invoked.append("demo.restricted")
        return arguments

    registry.register(
        ToolDefinition(
            name="demo.restricted",
            input_model=Input,
            executor=restricted,
            execution_mode=ExecutionMode.SYNC,
        )
    )
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (
                    ToolCall(call_id="allowed-1", name="demo.echo", arguments={"text": "ok"}),
                    ToolCall(call_id="blocked-1", name="demo.restricted", arguments={"value": 1}),
                ),
            ),
            lambda request: text_response(request, "observed"),
        ]
    )
    result = await engine_for(provider, registry).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), tool_names=("demo.echo",))
    )

    assert [schema.name for schema in provider.requests[0].tools] == ["demo.echo"]
    assert invoked == []
    assert [item.call_id for item in result.tool_results] == ["allowed-1", "blocked-1"]
    assert not result.tool_results[0].is_error
    assert result.tool_results[1].is_error
    assert result.tool_results[1].result["error_code"] == "tool_not_permitted"


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
        AgentRunConfig(model="test/model", messages=(user_message(),), tool_names=(call.name,))
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

    slow_started = asyncio.Event()

    async def slow(_: Input) -> dict[str, str]:
        slow_started.set()
        await asyncio.Event().wait()
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
        AgentRunConfig(
            model="test/model",
            messages=(user_message(),),
            tool_names=("demo.broken", "demo.timeout"),
        )
    )

    assert result.output == "recovered"
    assert [item.result["error_code"] for item in result.tool_results] == [
        "tool_exception",
        "tool_timeout",
    ]
    assert "secret" not in str(result.model_dump())
    assert slow_started.is_set()


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
        AgentRunConfig(
            model="test/model",
            messages=(user_message(),),
            max_steps=2,
            tool_names=("demo.echo",),
        )
    )

    assert result.termination_reason == AgentTerminationReason.MAX_STEPS
    assert len(provider.requests) == 2


@pytest.mark.asyncio
async def test_final_response_at_step_boundary_completes() -> None:
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="boundary-tool", name="demo.echo", arguments={"text": "x"}),),
            ),
            lambda request: text_response(request, "boundary complete"),
        ]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(
            model="test/model",
            messages=(user_message(),),
            max_steps=2,
            tool_names=("demo.echo",),
        )
    )
    assert result.state == RunState.COMPLETED
    assert result.output == "boundary complete"
    assert len(provider.requests) == 2


@pytest.mark.asyncio
async def test_tool_call_batch_over_budget_is_rejected_without_partial_execution() -> None:
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (
                    ToolCall(call_id="batch-1", name="demo.echo", arguments={"text": "one"}),
                    ToolCall(call_id="batch-2", name="demo.echo", arguments={"text": "two"}),
                ),
            )
        ]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(
            model="test/model",
            messages=(user_message(),),
            max_tool_calls=1,
            tool_names=("demo.echo",),
        )
    )
    assert result.termination_reason == AgentTerminationReason.TOOL_FAILURE
    assert result.error_code == "tool_budget_exhausted"
    assert result.tool_results == ()


@pytest.mark.asyncio
async def test_zero_tool_budget_executes_no_proposals() -> None:
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="zero-1", name="demo.echo", arguments={"text": "x"}),),
            )
        ]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(
            model="test/model",
            messages=(user_message(),),
            max_tool_calls=0,
            tool_names=("demo.echo",),
        )
    )
    assert result.termination_reason == AgentTerminationReason.TOOL_FAILURE
    assert result.tool_results == ()


@pytest.mark.asyncio
async def test_explicit_cancellation_cancels_in_flight_async_tool() -> None:
    class Input(BaseModel):
        value: str

    started = asyncio.Event()

    async def slow(_: Input) -> dict[str, str]:
        started.set()
        await asyncio.Event().wait()
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
            AgentRunConfig(
                model="test/model", messages=(user_message(),), tool_names=("demo.slow",)
            ),
            cancellation=token,
        )
    )
    await asyncio.wait_for(started.wait(), timeout=1)
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
async def test_explicit_cancellation_during_gateway_cleans_up_provider_task() -> None:
    provider = SlowProvider([lambda request: text_response(request, "late")])
    token = CancellationToken()
    task = asyncio.create_task(
        engine_for(provider).run(
            AgentRunConfig(model="test/model", messages=(user_message(),)), cancellation=token
        )
    )
    await asyncio.wait_for(provider.started.wait(), timeout=1)
    token.cancel()
    result = await task

    assert result.state == RunState.CANCELLED
    assert provider.cancelled.is_set()
    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_cancellation_after_terminal_run_does_not_change_result() -> None:
    provider = SequenceProvider([lambda request: text_response(request, "already done")])
    token = CancellationToken()
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),)), cancellation=token
    )
    token.cancel()

    assert result.state == RunState.COMPLETED
    assert result.output == "already done"
    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_total_deadline_cancels_async_tool_and_preserves_observation_history() -> None:
    class Input(BaseModel):
        value: str

    started = asyncio.Event()
    stopped = asyncio.Event()

    async def hanging(_: Input) -> dict[str, str]:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="demo.hang",
            input_model=Input,
            executor=hanging,
            execution_mode=ExecutionMode.ASYNC,
        )
    )
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="deadline-tool", name="demo.hang", arguments={"value": "x"}),),
            )
        ]
    )
    result = await engine_for(provider, registry).run(
        AgentRunConfig(
            model="test/model",
            messages=(user_message(),),
            timeout_seconds=0.05,
            tool_names=("demo.hang",),
        )
    )

    assert result.termination_reason == AgentTerminationReason.TIMEOUT
    assert started.is_set() and stopped.is_set()
    assert result.tool_results == ()
    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_cancellation_between_tool_proposals_prevents_next_handler() -> None:
    class Input(BaseModel):
        value: str

    token = CancellationToken()
    calls: list[str] = []

    async def run_tool(arguments: Input) -> dict[str, str]:
        calls.append(arguments.value)
        if arguments.value == "first":
            token.cancel()
        return {"value": arguments.value}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="demo.track",
            input_model=Input,
            executor=run_tool,
            execution_mode=ExecutionMode.ASYNC,
        )
    )
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (
                    ToolCall(call_id="first-id", name="demo.track", arguments={"value": "first"}),
                    ToolCall(call_id="second-id", name="demo.track", arguments={"value": "second"}),
                ),
            )
        ]
    )
    result = await engine_for(provider, registry).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), tool_names=("demo.track",)),
        cancellation=token,
    )

    assert result.state == RunState.CANCELLED
    assert calls == ["first"]
    assert [item.call_id for item in result.tool_results] == ["first-id"]


@pytest.mark.asyncio
async def test_gateway_timeout_error_is_not_retried_by_agent_loop() -> None:
    provider = SequenceProvider(
        [lambda request: ProviderTimeoutError("upstream timed out", provider_id="test")]
    )
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),))
    )
    assert result.termination_reason == AgentTerminationReason.PROVIDER_FAILURE
    assert result.error_code == "provider_timeout"
    assert len(provider.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        (
            ProviderAuthenticationError("credential rejected", provider_id="test"),
            "provider_authentication_error",
        ),
        (ProviderRateLimitError("rate limited", provider_id="test"), "provider_rate_limited"),
    ],
)
async def test_normalized_provider_failures_are_terminal_and_traced(
    failure: ProviderError, expected_code: str
) -> None:
    provider = SequenceProvider([failure])
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),))
    )
    assert result.termination_reason == AgentTerminationReason.PROVIDER_FAILURE
    assert result.error_code == expected_code
    assert result.trace[-1].event == "provider_failure"
    assert result.trace[-1].error_code == expected_code
    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_wall_clock_timeout_covers_model_request() -> None:
    provider = SlowProvider([lambda request: text_response(request, "late")])
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), timeout_seconds=0.01)
    )
    assert result.state == RunState.FAILED
    assert result.termination_reason == AgentTerminationReason.TIMEOUT
    assert provider.started.is_set()
    assert result.trace[-1].event == "run_timeout"


@pytest.mark.asyncio
async def test_timeout_after_tool_cycle_retains_completed_steps_and_observations() -> None:
    registry = echo_registry()
    # Let the first call return immediately and block only on the second.
    second_waiting = asyncio.Event()

    class OneFastThenBlocked(SequenceProvider):
        async def complete(self, request: ModelRequest) -> ModelResponse:
            if self.requests:
                second_waiting.set()
                await asyncio.Event().wait()
            return await super().complete(request)

    staged = OneFastThenBlocked(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="done-1", name="demo.echo", arguments={"text": "saved"}),),
            ),
            lambda request: text_response(request, "never returned"),
        ]
    )
    result = await engine_for(staged, registry).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), timeout_seconds=0.05)
    )

    assert result.termination_reason == AgentTerminationReason.TIMEOUT
    assert len(result.steps) == 1
    assert [item.call_id for item in result.tool_results] == ["done-1"]
    assert second_waiting.is_set()


@pytest.mark.asyncio
async def test_external_cancellation_cleans_up_gateway_task() -> None:
    provider = SlowProvider([lambda request: text_response(request, "late")])
    task = asyncio.create_task(
        engine_for(provider).run(AgentRunConfig(model="test/model", messages=(user_message(),)))
    )
    await asyncio.wait_for(provider.started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert provider.cancelled.is_set()


@pytest.mark.asyncio
async def test_missing_usage_is_reported_without_fabrication() -> None:
    provider = SequenceProvider([lambda request: text_response(request, "done")])
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), token_budget=1)
    )
    assert result.output is None
    assert result.termination_reason == AgentTerminationReason.TOKEN_BUDGET
    assert result.error_code == "token_budget_unverifiable"
    assert result.usage is None
    assert not result.usage_complete


@pytest.mark.asyncio
async def test_missing_usage_on_intermediate_call_keeps_aggregate_unknown() -> None:
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="usage-1", name="demo.echo", arguments={"text": "x"}),),
            ),
            lambda request: text_response(
                request,
                "done",
                TokenUsage(input_tokens=5, output_tokens=1, total_tokens=6),
            ),
        ]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), tool_names=("demo.echo",))
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
    assert provider.requests[0].generation.max_output_tokens == 3


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
    assert provider.requests[0].generation.max_output_tokens == 2


@pytest.mark.asyncio
async def test_token_budget_excess_on_final_response_is_reported_and_not_success() -> None:
    provider = SequenceProvider(
        [
            lambda request: text_response(
                request,
                "over budget",
                TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5),
            )
        ]
    )
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), token_budget=4)
    )
    assert result.termination_reason == AgentTerminationReason.TOKEN_BUDGET
    assert result.error_code == "token_budget_exhausted"
    assert result.usage is not None and result.usage.total_tokens == 5
    assert result.final_message is None
    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_budget_accounting_after_tool_execution_prevents_next_model_request() -> None:
    usage = TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2)
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="budget-first", name="demo.echo", arguments={"text": "x"}),),
                usage,
            ),
            lambda request: tool_response(
                request,
                (ToolCall(call_id="budget-second", name="demo.echo", arguments={"text": "y"}),),
                usage,
            ),
        ]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(
            model="test/model",
            messages=(user_message(),),
            token_budget=4,
            tool_names=("demo.echo",),
        )
    )
    assert result.termination_reason == AgentTerminationReason.TOKEN_BUDGET
    assert [item.call_id for item in result.tool_results] == ["budget-first"]
    assert len(provider.requests) == 2
    assert provider.requests[0].generation.max_output_tokens == 4
    assert provider.requests[1].generation.max_output_tokens == 2


@pytest.mark.asyncio
async def test_exact_token_budget_boundary_can_finish_without_more_work() -> None:
    provider = SequenceProvider(
        [
            lambda request: text_response(
                request,
                "exact",
                TokenUsage(input_tokens=2, output_tokens=2, total_tokens=4),
            )
        ]
    )
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), token_budget=4)
    )
    assert result.termination_reason == AgentTerminationReason.FINAL_RESPONSE
    assert result.output == "exact"


@pytest.mark.asyncio
async def test_cost_budget_fails_closed_when_gateway_cost_is_unknown() -> None:
    provider = SequenceProvider([lambda request: text_response(request, "done")])
    result = await engine_for(provider).run(
        AgentRunConfig(
            model="test/model",
            messages=(user_message(),),
            cost_budget_usd=Decimal("1.00"),
        )
    )
    assert result.termination_reason == AgentTerminationReason.COST_BUDGET
    assert result.error_code == "cost_budget_unverifiable"
    assert result.total_cost_usd is None
    assert not result.cost_budget_enforced


@pytest.mark.asyncio
async def test_unexpected_provider_exception_is_sanitized_and_structured() -> None:
    provider = SequenceProvider([lambda request: RuntimeError("api_key=synthetic-secret")])
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),))
    )
    assert result.termination_reason == AgentTerminationReason.PROVIDER_FAILURE
    assert result.error_code == "provider_error"
    assert "synthetic-secret" not in str(result.model_dump())
    assert result.trace[-1].error_code == "provider_error"


@pytest.mark.asyncio
async def test_malformed_assistant_response_fails_with_terminal_trace() -> None:
    provider = SequenceProvider(
        [
            lambda request: ModelResponse(
                request_id=request.request_id,
                provider_id="test",
                model_id=request.model_id,
                message=Message(role=MessageRole.USER, content=(TextContent(text="bad role"),)),
                finish_reason=FinishReason.STOP,
            )
        ]
    )
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),))
    )
    assert result.termination_reason == AgentTerminationReason.INVALID_RESPONSE
    assert result.trace[-1].event == "invalid_response"
    assert result.trace[-1].state == RunState.FAILED
    assert result.trace[-1].error_code == "invalid_response"


@pytest.mark.asyncio
async def test_provider_failure_after_tool_cycle_preserves_prior_progress() -> None:
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="completed-1", name="demo.echo", arguments={"text": "x"}),),
            ),
            ProviderError("authentication failed: api_key=synthetic-secret", provider_id="test"),
        ]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(model="test/model", messages=(user_message(),), tool_names=("demo.echo",))
    )
    assert result.termination_reason == AgentTerminationReason.PROVIDER_FAILURE
    assert len(result.steps) == 1
    assert [item.call_id for item in result.tool_results] == ["completed-1"]
    assert result.error_message is not None and "synthetic-secret" not in result.error_message
    assert result.trace[-1].state == RunState.FAILED


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


@pytest.mark.asyncio
async def test_same_tool_name_can_repeat_with_distinct_call_ids() -> None:
    provider = SequenceProvider(
        [
            lambda request: tool_response(
                request,
                (ToolCall(call_id="new-id-1", name="demo.echo", arguments={"text": "x"}),),
            ),
            lambda request: tool_response(
                request,
                (ToolCall(call_id="new-id-2", name="demo.echo", arguments={"text": "x"}),),
            ),
            lambda request: text_response(request, "done"),
        ]
    )
    result = await engine_for(provider, echo_registry()).run(
        AgentRunConfig(
            model="test/model",
            messages=(user_message(),),
            max_steps=3,
            tool_names=("demo.echo",),
        )
    )
    assert result.output == "done"
    assert [item.call_id for item in result.tool_results] == ["new-id-1", "new-id-2"]


@pytest.mark.asyncio
async def test_concurrent_runs_keep_histories_usage_and_traces_isolated() -> None:
    def response_for_task(request: ModelRequest) -> ModelResponse:
        task_text = request.messages[0].content[0].text
        return text_response(
            request,
            f"answer:{task_text}",
            TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2),
        )

    provider = SequenceProvider([response_for_task, response_for_task])
    engine = engine_for(provider)
    config_a = AgentRunConfig(model="test/model", messages=(user_message("A"),))
    config_b = AgentRunConfig(model="test/model", messages=(user_message("B"),))
    result_a, result_b = await asyncio.gather(engine.run(config_a), engine.run(config_b))

    assert result_a.output == "answer:A"
    assert result_b.output == "answer:B"
    assert result_a.run_id != result_b.run_id
    assert result_a.trace is not result_b.trace
    assert result_a.usage is not None and result_a.usage.total_tokens == 2
    assert result_b.usage is not None and result_b.usage.total_tokens == 2


@pytest.mark.asyncio
async def test_trace_order_and_reasoning_redaction() -> None:
    request_message = Message(
        role=MessageRole.ASSISTANT,
        content=(TextContent(text="visible"),),
        provider_extensions={"test.provider": {"reasoning_content": "private-reasoning"}},
    )
    provider = SequenceProvider(
        [
            lambda request: ModelResponse(
                request_id=request.request_id,
                provider_id="test",
                model_id=request.model_id,
                message=request_message,
                finish_reason=FinishReason.STOP,
            )
        ]
    )
    result = await engine_for(provider).run(
        AgentRunConfig(model="test/model", messages=(user_message(),))
    )
    assert [entry.sequence for entry in result.trace] == list(range(1, len(result.trace) + 1))
    assert result.trace[-1].state == RunState.COMPLETED
    assert "private-reasoning" not in str(result.trace)
