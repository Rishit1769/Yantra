"""Bounded, provider-neutral asynchronous agent execution loop."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from decimal import Decimal
from typing import TypeVar

from yantra.core.contracts import TokenUsage
from yantra.core.errors import ProviderError, YantraError
from yantra.core.messages import Message, MessageRole, ToolResult
from yantra.core.states import RunState, validate_transition
from yantra.providers.base import GenerationSettings
from yantra.providers.gateway import GatewayResponse, ModelGateway
from yantra.runtime.models import (
    AgentRunConfig,
    AgentRunResult,
    AgentStep,
    AgentTerminationReason,
    ExecutionTraceEntry,
)
from yantra.tools.executor import ToolExecutor
from yantra.tools.registry import ToolRegistry

_T = TypeVar("_T")


class CancellationToken:
    """Cooperative cancellation signal for an explicit runtime cancellation."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()


class _CancellationRequested(Exception):
    pass


class AgentExecutionEngine:
    """Execute a bounded model/tool loop using an existing ``ModelGateway``."""

    def __init__(self, gateway: ModelGateway, tools: ToolRegistry | ToolExecutor) -> None:
        self.gateway = gateway
        self.tool_executor = tools if isinstance(tools, ToolExecutor) else ToolExecutor(tools)

    async def run(
        self, config: AgentRunConfig, *, cancellation: CancellationToken | None = None
    ) -> AgentRunResult:
        return await self._run(config, cancellation)

    async def _run(
        self, config: AgentRunConfig, cancellation: CancellationToken | None
    ) -> AgentRunResult:
        state = RunState.CREATED
        trace: list[ExecutionTraceEntry] = []
        steps: list[AgentStep] = []
        tool_results: list[ToolResult] = []
        messages = list(config.messages)
        seen_call_ids: set[str] = set()
        total_usage: TokenUsage | None = None
        usage_complete = True
        total_cost: Decimal | None = Decimal("0")
        cost_known = True
        tool_count = 0
        deadline = asyncio.get_running_loop().time() + config.timeout_seconds

        def set_state(target: RunState, *, event: str, error_code: str | None = None) -> None:
            nonlocal state
            validate_transition(state, target)
            state = target
            trace.append(
                ExecutionTraceEntry(
                    sequence=len(trace) + 1,
                    step_index=len(steps),
                    event=event,
                    state=state,
                    error_code=error_code,
                )
            )

        def add_trace(
            event: str,
            *,
            outcome: str | None = None,
            tool_name: str | None = None,
            call_id: str | None = None,
            usage: TokenUsage | None = None,
            error_code: str | None = None,
        ) -> None:
            trace.append(
                ExecutionTraceEntry(
                    sequence=len(trace) + 1,
                    step_index=len(steps),
                    event=event,
                    state=state,
                    outcome=outcome,
                    tool_name=tool_name,
                    call_id=call_id,
                    usage=usage,
                    error_code=error_code,
                )
            )

        def terminal(target: RunState, event: str, *, error_code: str | None = None) -> RunState:
            if state != target:
                set_state(target, event=event, error_code=error_code)
            return target

        set_state(RunState.QUEUED, event="run_queued")
        set_state(RunState.RUNNING, event="run_started")
        try:
            for _ in range(config.max_steps):
                if cancellation is not None and cancellation.is_cancelled:
                    raise _CancellationRequested
                if total_usage is not None and config.token_budget is not None:
                    if total_usage.total_tokens >= config.token_budget:
                        return self._result(
                            config,
                            terminal(
                                RunState.FAILED,
                                "token_budget_exhausted",
                                error_code="token_budget_exhausted",
                            ),
                            AgentTerminationReason.TOKEN_BUDGET,
                            steps,
                            tool_results,
                            total_usage,
                            usage_complete,
                            total_cost if cost_known else None,
                            False,
                            trace,
                            "token_budget_exhausted",
                            "token budget exhausted",
                        )
                set_state(RunState.WAITING_FOR_MODEL, event="model_waiting")
                remaining_tokens = None
                if config.token_budget is not None:
                    remaining_tokens = (
                        config.token_budget
                        if total_usage is None
                        else max(1, config.token_budget - total_usage.total_tokens)
                    )

                async def request_model(output_token_limit: int | None) -> GatewayResponse:
                    return await self.gateway.generate(
                        model=config.model,
                        messages=messages,
                        tools=self._schemas(config),
                        generation=GenerationSettings(max_output_tokens=output_token_limit),
                        timeout_seconds=config.timeout_seconds,
                    )

                gateway_result = await self._await(
                    lambda output_token_limit=remaining_tokens: request_model(output_token_limit),
                    cancellation,
                    deadline=deadline,
                )
                set_state(RunState.RUNNING, event="model_received")
                response = gateway_result.response
                if response.message.role != MessageRole.ASSISTANT:
                    raise ValueError("model response was not an assistant message")
                steps.append(
                    AgentStep(
                        index=len(steps) + 1,
                        request_id=response.request_id,
                        response_message=response.message,
                        usage=response.usage,
                        estimated_cost_usd=gateway_result.estimated_cost_usd,
                        provider_reported_cost_usd=gateway_result.provider_reported_cost_usd,
                    )
                )
                messages.append(response.message)
                if response.usage is None:
                    usage_complete = False
                    total_usage = None
                else:
                    total_usage = self._add_usage(total_usage, response.usage)
                response_cost = gateway_result.provider_reported_cost_usd
                if response_cost is None:
                    response_cost = gateway_result.estimated_cost_usd
                if response_cost is None:
                    cost_known = False
                elif cost_known:
                    total_cost = (total_cost or Decimal("0")) + response_cost
                add_trace(
                    "model_response",
                    outcome="tool_calls" if response.message.tool_calls else "text",
                    usage=response.usage,
                )
                if config.token_budget is not None and not usage_complete:
                    return self._result(
                        config,
                        terminal(
                            RunState.FAILED,
                            "token_budget_unverifiable",
                            error_code="token_budget_unverifiable",
                        ),
                        AgentTerminationReason.TOKEN_BUDGET,
                        steps,
                        tool_results,
                        None,
                        False,
                        total_cost if cost_known else None,
                        False,
                        trace,
                        "token_budget_unverifiable",
                        "token budget cannot be verified because provider usage is missing",
                    )
                if config.cost_budget_usd is not None and not cost_known:
                    return self._result(
                        config,
                        terminal(
                            RunState.FAILED,
                            "cost_budget_unverifiable",
                            error_code="cost_budget_unverifiable",
                        ),
                        AgentTerminationReason.COST_BUDGET,
                        steps,
                        tool_results,
                        total_usage,
                        usage_complete,
                        None,
                        False,
                        trace,
                        "cost_budget_unverifiable",
                        "cost budget cannot be verified from available gateway cost data",
                    )
                if (
                    config.token_budget is not None
                    and total_usage is not None
                    and (
                        total_usage.total_tokens > config.token_budget
                        or (
                            response.message.tool_calls
                            and total_usage.total_tokens >= config.token_budget
                        )
                    )
                ):
                    return self._result(
                        config,
                        terminal(
                            RunState.FAILED,
                            "token_budget_exhausted",
                            error_code="token_budget_exhausted",
                        ),
                        AgentTerminationReason.TOKEN_BUDGET,
                        steps,
                        tool_results,
                        total_usage,
                        usage_complete,
                        total_cost if cost_known else None,
                        False,
                        trace,
                        "token_budget_exhausted",
                        "token budget exhausted",
                    )
                current_ids = [call.call_id for call in response.message.tool_calls]
                if len(current_ids) != len(set(current_ids)) or seen_call_ids.intersection(
                    current_ids
                ):
                    return self._result(
                        config,
                        terminal(
                            RunState.FAILED,
                            "invalid_response",
                            error_code="duplicate_tool_call_id",
                        ),
                        AgentTerminationReason.INVALID_RESPONSE,
                        steps,
                        tool_results,
                        total_usage,
                        usage_complete,
                        total_cost if cost_known else None,
                        False,
                        trace,
                        "duplicate_tool_call_id",
                        "model response contained a duplicate tool-call identifier",
                    )
                if (
                    config.cost_budget_usd is not None
                    and cost_known
                    and (
                        total_cost > config.cost_budget_usd
                        or (response.message.tool_calls and total_cost >= config.cost_budget_usd)
                    )
                ):
                    return self._result(
                        config,
                        terminal(
                            RunState.FAILED,
                            "cost_budget_exhausted",
                            error_code="cost_budget_exhausted",
                        ),
                        AgentTerminationReason.COST_BUDGET,
                        steps,
                        tool_results,
                        total_usage,
                        usage_complete,
                        total_cost,
                        True,
                        trace,
                        "cost_budget_exhausted",
                        "cost budget exhausted",
                    )
                if not response.message.tool_calls:
                    if not response.message.content:
                        raise ValueError(
                            "model response contained neither visible text nor tool calls"
                        )
                    return self._result(
                        config,
                        terminal(RunState.COMPLETED, "run_completed"),
                        AgentTerminationReason.FINAL_RESPONSE,
                        steps,
                        tool_results,
                        total_usage,
                        usage_complete,
                        total_cost if cost_known else None,
                        config.cost_budget_usd is not None and cost_known,
                        trace,
                        None,
                        None,
                        final_message=response.message,
                    )
                if len(steps) >= config.max_steps:
                    break
                seen_call_ids.update(current_ids)
                if tool_count + len(response.message.tool_calls) > config.max_tool_calls:
                    return self._result(
                        config,
                        terminal(
                            RunState.FAILED,
                            "tool_budget_exhausted",
                            error_code="tool_budget_exhausted",
                        ),
                        AgentTerminationReason.TOOL_FAILURE,
                        steps,
                        tool_results,
                        total_usage,
                        usage_complete,
                        total_cost if cost_known else None,
                        False,
                        trace,
                        "tool_budget_exhausted",
                        "maximum tool calls exceeded",
                    )
                set_state(RunState.WAITING_FOR_TOOL, event="tools_waiting")
                for call in response.message.tool_calls:
                    if call.name not in config.tool_names:
                        result = ToolResult(
                            call_id=call.call_id,
                            name=call.name,
                            result={
                                "error_code": "tool_not_permitted",
                                "message": "tool is not enabled for this run",
                            },
                            is_error=True,
                        )
                    else:
                        result = await self._await(
                            lambda current_call=call: self.tool_executor.execute(
                                current_call,
                                timeout_seconds=max(
                                    0.000001,
                                    deadline - asyncio.get_running_loop().time(),
                                ),
                            ),
                            cancellation,
                            deadline=deadline,
                        )
                    tool_results.append(result)
                    tool_count += 1
                    messages.append(Message(role=MessageRole.TOOL, content=(), tool_result=result))
                    add_trace(
                        "tool_result",
                        tool_name=call.name,
                        call_id=call.call_id,
                        outcome="error" if result.is_error else "success",
                    )
                set_state(RunState.RUNNING, event="tools_completed")
            return self._result(
                config,
                terminal(RunState.FAILED, "max_steps", error_code="max_steps"),
                AgentTerminationReason.MAX_STEPS,
                steps,
                tool_results,
                total_usage,
                usage_complete,
                total_cost if cost_known else None,
                False,
                trace,
                "max_steps",
                "maximum model steps reached",
            )
        except _CancellationRequested:
            if state not in {RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED}:
                set_state(RunState.CANCELLED, event="run_cancelled")
            return self._result(
                config,
                RunState.CANCELLED,
                AgentTerminationReason.CANCELLED,
                steps,
                tool_results,
                total_usage,
                usage_complete,
                total_cost if cost_known else None,
                False,
                trace,
                "cancelled",
                "agent run was cancelled",
            )
        except TimeoutError:
            if state not in {RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED}:
                set_state(RunState.FAILED, event="run_timeout", error_code="run_timeout")
            return self._result(
                config,
                RunState.FAILED,
                AgentTerminationReason.TIMEOUT,
                steps,
                tool_results,
                total_usage,
                usage_complete,
                total_cost if cost_known else None,
                False,
                trace,
                "run_timeout",
                "agent run exceeded its wall-clock timeout",
            )
        except ProviderError as exc:
            if state not in {RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED}:
                set_state(RunState.FAILED, event="provider_failure", error_code=exc.code)
            return self._result(
                config,
                RunState.FAILED,
                AgentTerminationReason.PROVIDER_FAILURE,
                steps,
                tool_results,
                total_usage,
                usage_complete,
                total_cost if cost_known else None,
                False,
                trace,
                exc.code,
                exc.message,
            )
        except (YantraError, ValueError) as exc:
            error_code = getattr(exc, "code", "invalid_response")
            if state not in {RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED}:
                set_state(RunState.FAILED, event="invalid_response", error_code=error_code)
            return self._result(
                config,
                RunState.FAILED,
                (
                    AgentTerminationReason.INVALID_RESPONSE
                    if isinstance(exc, ValueError)
                    else AgentTerminationReason.TOOL_FAILURE
                ),
                steps,
                tool_results,
                total_usage,
                usage_complete,
                total_cost if cost_known else None,
                False,
                trace,
                error_code,
                str(exc),
            )
        except Exception:
            add_trace("provider_failure", outcome="unexpected_error", error_code="provider_error")
            if state not in {RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED}:
                set_state(RunState.FAILED, event="provider_failure", error_code="provider_error")
            return self._result(
                config,
                RunState.FAILED,
                AgentTerminationReason.PROVIDER_FAILURE,
                steps,
                tool_results,
                total_usage,
                usage_complete,
                total_cost if cost_known else None,
                False,
                trace,
                "provider_error",
                "model gateway execution failed unexpectedly",
            )

    def _schemas(self, config: AgentRunConfig):
        definitions = self.tool_executor.registry.list()
        names = set(config.tool_names)
        definitions = tuple(tool for tool in definitions if tool.name in names)
        return tuple(tool.provider_schema() for tool in definitions)

    async def _await(
        self,
        operation: Callable[[], Awaitable[_T]],
        cancellation: CancellationToken | None,
        *,
        deadline: float,
    ) -> _T:
        if cancellation is not None and cancellation.is_cancelled:
            raise _CancellationRequested

        async def within_deadline() -> _T:
            remaining = deadline - asyncio.get_running_loop().time()
            async with asyncio.timeout(max(0.0, remaining)):
                return await operation()

        task: asyncio.Task[_T] = asyncio.create_task(within_deadline())
        if cancellation is None:
            return await task
        cancel_task = asyncio.create_task(cancellation.wait())
        try:
            done, _ = await asyncio.wait({task, cancel_task}, return_when=asyncio.FIRST_COMPLETED)
            if cancel_task in done and not task.done():
                raise _CancellationRequested
            return await task
        finally:
            owned_tasks = (task, cancel_task)
            for owned_task in owned_tasks:
                if not owned_task.done():
                    owned_task.cancel()
            await asyncio.gather(*owned_tasks, return_exceptions=True)

    @staticmethod
    def _add_usage(current: TokenUsage | None, new: TokenUsage) -> TokenUsage:
        if current is None:
            return new
        return TokenUsage(
            input_tokens=current.input_tokens + new.input_tokens,
            output_tokens=current.output_tokens + new.output_tokens,
            total_tokens=current.total_tokens + new.total_tokens,
            cached_input_tokens=(
                None
                if current.cached_input_tokens is None or new.cached_input_tokens is None
                else current.cached_input_tokens + new.cached_input_tokens
            ),
            reasoning_tokens=(
                None
                if current.reasoning_tokens is None or new.reasoning_tokens is None
                else current.reasoning_tokens + new.reasoning_tokens
            ),
        )

    @staticmethod
    def _result(
        config: AgentRunConfig,
        state: RunState,
        reason: AgentTerminationReason,
        steps: Sequence[AgentStep],
        tool_results: Sequence[ToolResult],
        usage: TokenUsage | None,
        usage_complete: bool,
        total_cost: Decimal | None,
        cost_enforced: bool,
        trace: Sequence[ExecutionTraceEntry],
        error_code: str | None,
        error_message: str | None,
        *,
        final_message: Message | None = None,
    ) -> AgentRunResult:
        return AgentRunResult(
            run_id=config.run_id,
            session_id=config.session_id,
            state=state,
            termination_reason=reason,
            final_message=final_message,
            steps=tuple(steps),
            tool_results=tuple(tool_results),
            usage=usage if usage_complete else None,
            usage_complete=usage_complete,
            total_cost_usd=total_cost,
            cost_budget_enforced=cost_enforced,
            error_code=error_code,
            error_message=error_message,
            trace=tuple(trace),
        )
