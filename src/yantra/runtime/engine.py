"""Bounded, provider-neutral asynchronous agent execution loop."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Sequence
from contextlib import suppress
from decimal import Decimal
from typing import TypeVar

from yantra.core.contracts import TokenUsage
from yantra.core.errors import ProviderError, YantraError
from yantra.core.messages import Message, MessageRole, ToolResult
from yantra.core.states import RunState, validate_transition
from yantra.providers.gateway import ModelGateway
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
        try:
            return await asyncio.wait_for(
                self._run(config, cancellation), timeout=config.timeout_seconds
            )
        except TimeoutError:
            return AgentRunResult(
                run_id=config.run_id,
                session_id=config.session_id,
                state=RunState.FAILED,
                termination_reason=AgentTerminationReason.TIMEOUT,
                error_code="run_timeout",
                error_message="agent run exceeded its wall-clock timeout",
            )
        except asyncio.CancelledError:
            # External task cancellation remains normal asyncio cancellation.
            raise

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

        def set_state(target: RunState, *, event: str) -> None:
            nonlocal state
            validate_transition(state, target)
            state = target
            trace.append(
                ExecutionTraceEntry(
                    sequence=len(trace) + 1,
                    step_index=len(steps),
                    event=event,
                    state=state,
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

        def terminal(target: RunState, event: str) -> RunState:
            if state != target:
                set_state(target, event=event)
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
                            terminal(RunState.FAILED, "token_budget_exhausted"),
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
                gateway_result = await self._await(
                    self.gateway.generate(
                        model=config.model,
                        messages=messages,
                        tools=self._schemas(config),
                        timeout_seconds=config.timeout_seconds,
                    ),
                    cancellation,
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
                response_cost = (
                    gateway_result.provider_reported_cost_usd or gateway_result.estimated_cost_usd
                )
                if response_cost is None:
                    cost_known = False
                elif cost_known:
                    total_cost = (total_cost or Decimal("0")) + response_cost
                add_trace(
                    "model_response",
                    outcome="tool_calls" if response.message.tool_calls else "text",
                    usage=response.usage,
                )
                if (
                    response.message.tool_calls
                    and config.token_budget is not None
                    and total_usage is not None
                    and total_usage.total_tokens >= config.token_budget
                ):
                    return self._result(
                        config,
                        terminal(RunState.FAILED, "token_budget_exhausted"),
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
                if (
                    config.cost_budget_usd is not None
                    and cost_known
                    and total_cost > config.cost_budget_usd
                ):
                    return self._result(
                        config,
                        terminal(RunState.FAILED, "cost_budget_exhausted"),
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
                current_ids = [call.call_id for call in response.message.tool_calls]
                if len(current_ids) != len(set(current_ids)) or seen_call_ids.intersection(
                    current_ids
                ):
                    raise ValueError("duplicate tool-call identifier in model response")
                seen_call_ids.update(current_ids)
                if tool_count + len(response.message.tool_calls) > config.max_tool_calls:
                    return self._result(
                        config,
                        terminal(RunState.FAILED, "tool_budget_exhausted"),
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
                    result = await self._await(self.tool_executor.execute(call), cancellation)
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
                terminal(RunState.FAILED, "max_steps"),
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
        except ProviderError as exc:
            return self._result(
                config,
                terminal(RunState.FAILED, "provider_failure"),
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
            return self._result(
                config,
                terminal(RunState.FAILED, "invalid_response"),
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
                getattr(exc, "code", "invalid_response"),
                str(exc),
            )

    def _schemas(self, config: AgentRunConfig):
        definitions = self.tool_executor.registry.list()
        if config.tool_names:
            names = set(config.tool_names)
            definitions = tuple(tool for tool in definitions if tool.name in names)
        return tuple(tool.provider_schema() for tool in definitions)

    async def _await(self, operation: Awaitable[_T], cancellation: CancellationToken | None) -> _T:
        if cancellation is None:
            return await operation
        task: asyncio.Task[_T] = asyncio.ensure_future(operation)
        cancel_task = asyncio.create_task(cancellation.wait())
        done, _ = await asyncio.wait({task, cancel_task}, return_when=asyncio.FIRST_COMPLETED)
        if cancel_task in done and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            raise _CancellationRequested
        cancel_task.cancel()
        with suppress(asyncio.CancelledError):
            await cancel_task
        return await task

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
