"""Bounded, provider-neutral asynchronous agent execution loop."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TypeVar
from uuid import uuid4

from yantra.core.contracts import TokenUsage
from yantra.core.errors import ProviderError, ToolNotFoundError, YantraError
from yantra.core.messages import Message, MessageRole, ToolCall, ToolResult
from yantra.core.states import RunState, validate_transition
from yantra.core.tools_schema import ProviderToolSchema
from yantra.providers.base import GenerationSettings
from yantra.providers.gateway import GatewayResponse, ModelGateway
from yantra.runtime.models import (
    AgentRunConfig,
    AgentRunResult,
    AgentStep,
    AgentTerminationReason,
    ExecutionTraceEntry,
)
from yantra.tools.approvals import (
    ApprovalDecision,
    ApprovalProvider,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStore,
    InMemoryApprovalStore,
)
from yantra.tools.base import ToolDefinition
from yantra.tools.execution import (
    ExecutionAuthorizationAuthority,
    ExecutionLimits,
    canonical_json_digest,
)
from yantra.tools.executor import ToolExecutor
from yantra.tools.policy import (
    DefaultPolicyEvaluator,
    PolicyContext,
    PolicyDecision,
    PolicyEffect,
    PolicyEvaluator,
    PolicyReason,
    PolicyRequest,
)
from yantra.tools.registry import ToolRegistry
from yantra.tools.subprocess_boundary import SubprocessExecutionBoundary

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


def _canonical_digest(value: object) -> str:
    return canonical_json_digest(value)


def _authorization_digest(
    config: AgentRunConfig, definition: ToolDefinition, decision: PolicyDecision
) -> str:
    policy_context = config.permission_context
    context = None
    if policy_context is not None:
        context = {
            "granted_scopes": sorted(policy_context.granted_scopes),
            "denied_scopes": sorted(policy_context.denied_scopes),
            "approval_required_scopes": sorted(policy_context.approval_required_scopes),
            "approval_required_risks": sorted(
                risk.value for risk in policy_context.approval_required_risks
            ),
        }
    return _canonical_digest(
        {
            "allow_legacy_unscoped_tools": config.allow_legacy_unscoped_tools,
            "context": context,
            "decision": decision.model_dump(mode="json"),
            "definition_identity": id(definition),
            "permission_scopes": sorted(definition.permission_scopes),
            "risk_level": definition.risk_level.value,
            "side_effect": definition.side_effect.value,
            "tool_names": sorted(config.tool_names),
        }
    )


class AgentExecutionEngine:
    """Execute a bounded model/tool loop using an existing ``ModelGateway``."""

    def __init__(
        self,
        gateway: ModelGateway,
        tools: ToolRegistry | ToolExecutor,
        *,
        policy_evaluator: PolicyEvaluator | None = None,
        approval_provider: ApprovalProvider | None = None,
        approval_store: ApprovalStore | None = None,
        approval_ttl_seconds: float = 60.0,
        subprocess_boundary: SubprocessExecutionBoundary | None = None,
        execution_limits: ExecutionLimits | None = None,
    ) -> None:
        self.gateway = gateway
        self.__execution_authority = ExecutionAuthorizationAuthority()
        if isinstance(tools, ToolExecutor):
            self.tool_executor = tools
            if subprocess_boundary is not None:
                self.tool_executor.subprocess_boundary = subprocess_boundary
            elif execution_limits is not None:
                self.tool_executor.subprocess_boundary = SubprocessExecutionBoundary(
                    execution_limits
                )
            self.tool_executor._bind_authorization_key(  # pyright: ignore[reportPrivateUsage]
                self.__execution_authority._verifier_key()  # pyright: ignore[reportPrivateUsage]
            )
        else:
            self.tool_executor = ToolExecutor(
                tools,
                subprocess_boundary=subprocess_boundary,
                execution_limits=execution_limits,
            )
            self.tool_executor._bind_authorization_key(  # pyright: ignore[reportPrivateUsage]
                self.__execution_authority._verifier_key()  # pyright: ignore[reportPrivateUsage]
            )
        self.policy_evaluator = policy_evaluator or DefaultPolicyEvaluator()
        self.approval_provider = approval_provider
        self.approval_store = approval_store or InMemoryApprovalStore()
        if not 0 < approval_ttl_seconds <= 3600:
            raise ValueError("approval_ttl_seconds must be between 0 and 3600")
        self.approval_ttl_seconds = approval_ttl_seconds

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
                        decision = PolicyDecision(
                            effect=PolicyEffect.DENY, reason=PolicyReason.POLICY_RESTRICTED
                        )
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
                        definition: ToolDefinition | None = None
                        try:
                            definition = self.tool_executor.registry.get(call.name)
                        except ToolNotFoundError:
                            decision = PolicyDecision(
                                effect=PolicyEffect.DENY,
                                reason=PolicyReason.INVALID_POLICY,
                            )
                        else:
                            decision = self._authorize(config, definition)

                        async def execute_tool(
                            current_call: ToolCall = call,
                            current_decision: PolicyDecision = decision,
                            current_definition: ToolDefinition | None = definition,
                        ) -> ToolResult:
                            if current_definition is None:
                                return await self.tool_executor.execute(
                                    current_call,
                                    authorization=current_decision,
                                )
                            if current_decision.effect == PolicyEffect.DENY:
                                return self.tool_executor.policy_failure(
                                    current_call,
                                    "tool_not_permitted",
                                    "tool is not authorized for this run",
                                    current_decision,
                                )
                            approved = False
                            if current_decision.effect == PolicyEffect.APPROVAL_REQUIRED:
                                approval_provider = self.approval_provider
                                if approval_provider is None:
                                    add_trace("approval_provider_failed", outcome="unavailable")
                                    return self.tool_executor.policy_failure(
                                        current_call,
                                        "tool_approval_required",
                                        "trusted approval is unavailable",
                                        current_decision,
                                    )
                                try:
                                    args_digest = _canonical_digest(current_call.arguments)
                                    authorization_digest = _authorization_digest(
                                        config, current_definition, current_decision
                                    )
                                except (TypeError, ValueError):
                                    add_trace("approval_mismatched", outcome="invalid_binding")
                                    return self.tool_executor.failure(
                                        current_call,
                                        "tool_approval_invalid",
                                        "approval request could not be bound safely",
                                    )
                                request = ApprovalRequest(
                                    request_id=uuid4(),
                                    run_id=config.run_id,
                                    session_id=config.session_id,
                                    invocation_id=uuid4(),
                                    tool_name=current_definition.name,
                                    definition_identity=id(current_definition),
                                    required_scopes=current_definition.permission_scopes,
                                    risk_level=current_definition.risk_level,
                                    policy_effect=current_decision.effect,
                                    policy_reason=current_decision.reason,
                                    arguments_sha256=args_digest,
                                    authorization_sha256=authorization_digest,
                                    expires_at=datetime.now(UTC)
                                    + timedelta(seconds=self.approval_ttl_seconds),
                                )
                                self.approval_store.register(request, current_definition)
                                add_trace("approval_requested", outcome="pending")
                                try:
                                    provider_response = await self._await(
                                        lambda: approval_provider.request_approval(request),
                                        cancellation,
                                        deadline=deadline,
                                    )
                                    decision = ApprovalDecision.model_validate(provider_response)
                                    if decision.status != ApprovalStatus.APPROVED:
                                        add_trace("approval_denied", outcome="denied")
                                        return self.tool_executor.failure(
                                            current_call,
                                            "tool_approval_denied",
                                            "tool invocation was not approved",
                                        )
                                    if (
                                        decision.request_id != request.request_id
                                        or decision.authorization_sha256
                                        != request.authorization_sha256
                                    ):
                                        add_trace("approval_mismatched", outcome="response_binding")
                                        return self.tool_executor.failure(
                                            current_call,
                                            "tool_approval_mismatched",
                                            "approval response does not match this invocation",
                                        )
                                    add_trace("approval_granted", outcome="approved")
                                    if datetime.now(UTC) >= request.expires_at:
                                        add_trace("approval_expired", outcome="expired")
                                        return self.tool_executor.failure(
                                            current_call,
                                            "tool_approval_expired",
                                            "approval expired before tool dispatch",
                                        )
                                    if cancellation is not None and cancellation.is_cancelled:
                                        raise _CancellationRequested
                                    if asyncio.get_running_loop().time() >= deadline:
                                        raise TimeoutError
                                    if (
                                        current_definition
                                        is not self.tool_executor.registry.get(current_call.name)
                                        or _authorization_digest(
                                            config,
                                            current_definition,
                                            self._authorize(config, current_definition),
                                        )
                                        != request.authorization_sha256
                                        or self._authorize(config, current_definition)
                                        != current_decision
                                    ):
                                        add_trace(
                                            "approval_mismatched", outcome="revalidation_failed"
                                        )
                                        return self.tool_executor.failure(
                                            current_call,
                                            "tool_approval_mismatched",
                                            "approval no longer matches the authorized invocation",
                                        )
                                    if not self.approval_store.consume(
                                        request, current_definition, decision
                                    ):
                                        add_trace(
                                            "approval_replay_rejected", outcome="not_consumed"
                                        )
                                        return self.tool_executor.failure(
                                            current_call,
                                            "tool_approval_replay",
                                            "approval is expired, mismatched, or already consumed",
                                        )
                                    approved = True
                                    add_trace("approval_consumed", outcome="approved")
                                    if cancellation is not None and cancellation.is_cancelled:
                                        add_trace(
                                            "approval_cancelled", outcome="consumed_before_dispatch"
                                        )
                                        raise _CancellationRequested
                                except (_CancellationRequested, TimeoutError):
                                    raise
                                except Exception:
                                    add_trace("approval_provider_failed", outcome="failed")
                                    return self.tool_executor.failure(
                                        current_call,
                                        "tool_approval_unavailable",
                                        "trusted approval could not be obtained",
                                    )
                                finally:
                                    self.approval_store.revoke(request.request_id)
                                    if (
                                        not approved
                                        and cancellation is not None
                                        and cancellation.is_cancelled
                                    ):
                                        add_trace("approval_cancelled", outcome="cancelled")
                            else:
                                # Re-check immediately; the registry remains authoritative.
                                if self._authorize(config, current_definition) != current_decision:
                                    return self.tool_executor.failure(
                                        current_call,
                                        "tool_not_permitted",
                                        "tool authorization changed before dispatch",
                                    )
                            try:
                                arguments_digest = _canonical_digest(current_call.arguments)
                            except (TypeError, ValueError):
                                return self.tool_executor.failure(
                                    current_call,
                                    "tool_invalid_serialization",
                                    "tool arguments cannot be serialized safely",
                                )
                            execution_authorization = self.__execution_authority.issue(
                                run_id=config.run_id,
                                call_id=current_call.call_id,
                                definition=current_definition,
                                arguments_sha256=arguments_digest,
                                decision=current_decision,
                                approval_granted=approved,
                            )
                            add_trace(
                                "tool_dispatched",
                                outcome="approved" if approved else "authorized",
                            )
                            return await self.tool_executor.execute(
                                current_call,
                                authorization=current_decision,
                                execution_authorization=execution_authorization,
                                run_id=config.run_id,
                                expected_definition=current_definition,
                                timeout_seconds=max(
                                    0.000001,
                                    deadline - asyncio.get_running_loop().time(),
                                ),
                            )

                        result = await self._await(
                            execute_tool,
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

    def _schemas(self, config: AgentRunConfig) -> tuple[ProviderToolSchema, ...]:
        definitions = self.tool_executor.registry.list()
        names = set(config.tool_names)
        definitions = tuple(tool for tool in definitions if tool.name in names)
        eligible: list[ProviderToolSchema] = []
        for tool in definitions:
            effect = self._authorize(config, tool).effect
            if effect == PolicyEffect.ALLOW or (
                effect == PolicyEffect.APPROVAL_REQUIRED and self.approval_provider is not None
            ):
                eligible.append(tool.provider_schema())
        return tuple(eligible)

    def _authorize(self, config: AgentRunConfig, definition: ToolDefinition) -> PolicyDecision:
        """Apply run authority before consulting a policy that can only restrict it."""
        required = definition.permission_scopes
        context = config.permission_context
        if not required:
            if not config.allow_legacy_unscoped_tools:
                return PolicyDecision(
                    effect=PolicyEffect.DENY,
                    reason=PolicyReason.POLICY_RESTRICTED,
                )
            if context is None:
                context = PolicyContext()
        if context is None:
            return PolicyDecision(effect=PolicyEffect.DENY, reason=PolicyReason.MISSING_CONTEXT)
        if required & context.denied_scopes:
            return PolicyDecision(effect=PolicyEffect.DENY, reason=PolicyReason.EXPLICIT_DENY)
        if not required <= context.granted_scopes:
            return PolicyDecision(effect=PolicyEffect.DENY, reason=PolicyReason.MISSING_SCOPE)
        if required & context.approval_required_scopes:
            return PolicyDecision(
                effect=PolicyEffect.APPROVAL_REQUIRED,
                reason=PolicyReason.APPROVAL_REQUIRED,
            )
        if definition.risk_level in context.approval_required_risks:
            return PolicyDecision(
                effect=PolicyEffect.APPROVAL_REQUIRED,
                reason=PolicyReason.RISK_RESTRICTED,
            )
        request = PolicyRequest(
            tool_name=definition.name,
            required_scopes=required,
            risk_level=definition.risk_level,
        )
        try:
            candidate = self.policy_evaluator.evaluate(request, context)
        except Exception:
            return PolicyDecision(effect=PolicyEffect.DENY, reason=PolicyReason.EVALUATOR_ERROR)
        try:
            decision = PolicyDecision.model_validate(candidate)
        except Exception:
            return PolicyDecision(
                effect=PolicyEffect.DENY,
                reason=PolicyReason.INVALID_POLICY,
            )
        if (
            decision.effect == PolicyEffect.ALLOW
            and not required
            and config.permission_context is None
        ):
            return PolicyDecision(
                effect=PolicyEffect.ALLOW,
                reason=PolicyReason.LEGACY_UNSCOPED,
            )
        return decision

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
