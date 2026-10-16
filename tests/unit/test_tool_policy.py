"""Offline contract and enforcement tests for YANTRA-004-V01 policy checks."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import cast

import pytest
from pydantic import BaseModel, ValidationError

from yantra.core.contracts import ProviderCapabilities
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.core.states import RunState
from yantra.providers.base import FinishReason, ModelRequest, ModelResponse
from yantra.providers.gateway import ModelGateway
from yantra.providers.registry import ProviderRegistry
from yantra.runtime import AgentExecutionEngine, AgentRunConfig, format_run_result
from yantra.tools import (
    DefaultPolicyEvaluator,
    ExecutionMode,
    PolicyContext,
    PolicyDecision,
    PolicyEffect,
    PolicyReason,
    PolicyRequest,
    SideEffect,
    ToolDefinition,
    ToolExecutor,
    ToolRegistry,
    ToolRiskLevel,
)


class Input(BaseModel):
    value: int


class Output(BaseModel):
    value: int


class SequenceProvider:
    provider_id = "policy-test"
    capabilities = ProviderCapabilities(tool_calling=True, token_usage=True)

    def __init__(self, calls: Sequence[ToolCall]) -> None:
        self.calls = calls
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        observed = any(message.role == MessageRole.TOOL for message in request.messages)
        message = (
            Message(role=MessageRole.ASSISTANT, content=(TextContent(text="done"),))
            if observed
            else Message(role=MessageRole.ASSISTANT, tool_calls=self.calls)
        )
        return ModelResponse(
            request_id=request.request_id,
            provider_id=self.provider_id,
            model_id=request.model_id,
            message=message,
            finish_reason=FinishReason.STOP if observed else FinishReason.TOOL_CALLS,
        )


def tool(name: str, scope: str, handler: Callable[[Input], Output], *, risk=ToolRiskLevel.LOW):
    return ToolDefinition(
        name=name,
        input_model=Input,
        output_model=Output,
        executor=handler,
        execution_mode=ExecutionMode.SYNC,
        permission_scopes=frozenset({scope}),
        risk_level=risk,
        side_effect=SideEffect.READ_ONLY,
    )


def make_engine(
    provider: SequenceProvider,
    registry: ToolRegistry,
    *,
    evaluator=None,
) -> AgentExecutionEngine:
    providers = ProviderRegistry()
    providers.register(provider, is_local=True)
    return AgentExecutionEngine(ModelGateway(providers), registry, policy_evaluator=evaluator)


def config(*, names: tuple[str, ...], context: PolicyContext | None = None, **kwargs):
    return AgentRunConfig(
        model="policy-test/model",
        messages=(Message(role=MessageRole.USER, content=(TextContent(text="run"),)),),
        max_steps=3,
        max_tool_calls=4,
        timeout_seconds=3,
        tool_names=names,
        permission_context=context,
        **kwargs,
    )


def test_scope_contract_validation_normalization_and_serialization() -> None:
    context = PolicyContext(granted_scopes=["filesystem.read", "filesystem.read"])
    assert context.granted_scopes == frozenset({"filesystem.read"})
    assert PolicyContext.model_validate_json(context.model_dump_json()) == context
    with pytest.raises(ValidationError):
        PolicyContext(granted_scopes={"filesystem.*"})
    with pytest.raises(ValidationError):
        PolicyContext(granted_scopes={"Filesystem.read"})
    with pytest.raises(ValidationError):
        PolicyContext(granted_scopes={"filesystem..read"})
    with pytest.raises(ValidationError):
        tool("invalid.scope", "filesystem.*", lambda arguments: Output(value=0))
    with pytest.raises(ValidationError):
        PolicyDecision(effect="permit", reason="allowed")


def test_contracts_are_immutable_and_risk_class_is_validated() -> None:
    context = PolicyContext(granted_scopes={"network.request"})
    with pytest.raises(ValidationError):
        context.granted_scopes = frozenset()
    request = PolicyRequest(
        tool_name="net.fetch",
        required_scopes={"network.request"},
        risk_level=ToolRiskLevel.HIGH,
    )
    assert request.risk_level == ToolRiskLevel.HIGH
    assert PolicyDecision(effect=PolicyEffect.ALLOW, reason=PolicyReason.ALLOWED).model_dump(
        mode="json"
    ) == {"effect": "allow", "reason": "allowed"}
    with pytest.raises(ValidationError):
        PolicyRequest(tool_name="test.tool", required_scopes={"filesystem.read"})
    with pytest.raises(ValidationError):
        PolicyRequest(
            tool_name="test.tool",
            required_scopes={"filesystem.read"},
            risk_level="extreme",
        )


@pytest.mark.parametrize(
    ("required", "context", "effect", "reason"),
    [
        ({"filesystem.read"}, {"granted_scopes": {"filesystem.read"}}, "allow", "allowed"),
        ({"filesystem.read"}, {}, "deny", "missing_scope"),
        (
            {"filesystem.read"},
            {
                "granted_scopes": {"filesystem.read"},
                "denied_scopes": {"filesystem.read"},
            },
            "deny",
            "explicit_deny",
        ),
        (
            {"filesystem.read"},
            {
                "granted_scopes": {"filesystem.read"},
                "approval_required_scopes": {"filesystem.read"},
            },
            "approval_required",
            "approval_required",
        ),
        (
            set(),
            {"approval_required_risks": {ToolRiskLevel.CRITICAL}},
            "approval_required",
            "risk_restricted",
        ),
    ],
)
def test_default_evaluator_is_exact_and_deterministic(required, context, effect, reason) -> None:
    request = PolicyRequest(
        tool_name="test.tool",
        required_scopes=required,
        risk_level=ToolRiskLevel.CRITICAL,
    )
    result = DefaultPolicyEvaluator().evaluate(request, PolicyContext(**context))
    assert (result.effect.value, result.reason.value) == (effect, reason)


@pytest.mark.asyncio
async def test_direct_executor_denies_without_an_authorization_decision() -> None:
    calls = 0

    def handler(arguments: Input) -> Output:
        nonlocal calls
        calls += 1
        return Output(value=arguments.value)

    registry = ToolRegistry()
    registry.register(tool("secure.read", "filesystem.read", handler))
    result = await ToolExecutor(registry).execute(
        ToolCall(call_id="local-call", name="secure.read", arguments={"value": 1})
    )
    assert result.is_error
    assert result.result["error_code"] == "tool_not_permitted"
    assert calls == 0


@pytest.mark.asyncio
async def test_direct_executor_rejects_malformed_authorization_decision() -> None:
    calls = 0

    def handler(arguments: Input) -> Output:
        nonlocal calls
        calls += 1
        return Output(value=arguments.value)

    registry = ToolRegistry()
    registry.register(tool("secure.read", "filesystem.read", handler))
    result = await ToolExecutor(registry).execute(
        ToolCall(call_id="local-call", name="secure.read", arguments={"value": 1}),
        authorization=cast(PolicyDecision, object()),
    )
    assert result.is_error
    assert result.result["error_code"] == "tool_not_permitted"
    assert calls == 0


@pytest.mark.asyncio
async def test_empty_name_allowlist_denies_even_with_a_scope_grant() -> None:
    calls = 0

    def handler(arguments: Input) -> Output:
        nonlocal calls
        calls += 1
        return Output(value=arguments.value)

    registry = ToolRegistry()
    registry.register(tool("secure.read", "filesystem.read", handler))
    provider = SequenceProvider(
        (ToolCall(call_id="batch-secret-id", name="secure.read", arguments={"value": 1}),)
    )
    engine = make_engine(provider, registry)
    result = await engine.run(
        config(
            names=(),
            context=PolicyContext(granted_scopes={"filesystem.read"}),
        )
    )
    assert calls == 0
    assert result.tool_results[0].result["error_code"] == "tool_not_permitted"
    assert "secure.read" not in [schema.name for schema in provider.requests[0].tools]


@pytest.mark.asyncio
async def test_missing_scope_and_unrelated_scope_never_invoke_handler() -> None:
    calls = 0

    def handler(arguments: Input) -> Output:
        nonlocal calls
        calls += 1
        return Output(value=arguments.value)

    registry = ToolRegistry()
    registry.register(tool("secure.read", "filesystem.read", handler))
    provider = SequenceProvider(
        (ToolCall(call_id="c1", name="secure.read", arguments={"value": 1}),)
    )
    result = await make_engine(provider, registry).run(
        config(names=("secure.read",), context=PolicyContext(granted_scopes={"network.request"}))
    )
    assert result.tool_results[0].result["error_code"] == "tool_not_permitted"
    assert result.tool_results[0].result["policy_reason"] == "missing_scope"
    assert calls == 0
    assert provider.requests[0].tools == ()


@pytest.mark.asyncio
async def test_exact_scope_allows_and_required_scopes_are_conjunctive() -> None:
    calls: list[int] = []

    def handler(arguments: Input) -> Output:
        calls.append(arguments.value)
        return Output(value=arguments.value)

    registry = ToolRegistry()
    definition = tool("secure.read", "filesystem.read", handler)
    definition = definition.model_copy(
        update={"permission_scopes": frozenset({"filesystem.read", "system.inspect"})}
    )
    registry.register(definition)
    call = ToolCall(call_id="allowed-call", name="secure.read", arguments={"value": 7})
    provider = SequenceProvider((call,))
    result = await make_engine(provider, registry).run(
        config(
            names=("secure.read",),
            context=PolicyContext(
                granted_scopes={"filesystem.read", "system.inspect", "filesystem.write"}
            ),
        )
    )
    assert calls == [7]
    assert result.tool_results[0].result == {"value": 7}
    assert result.tool_results[0].call_id == "allowed-call"
    assert [schema.name for schema in provider.requests[0].tools] == ["secure.read"]

    denied_provider = SequenceProvider((call,))
    denied = await make_engine(denied_provider, registry).run(
        config(
            names=("secure.read",),
            context=PolicyContext(granted_scopes={"filesystem.read"}),
        )
    )
    assert calls == [7]
    assert denied.tool_results[0].result["policy_reason"] == "missing_scope"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("context", "expected_code", "expected_reason"),
    [
        (
            PolicyContext(granted_scopes={"filesystem.read"}, denied_scopes={"filesystem.read"}),
            "tool_not_permitted",
            "explicit_deny",
        ),
        (
            PolicyContext(
                granted_scopes={"filesystem.read"},
                approval_required_scopes={"filesystem.read"},
            ),
            "tool_approval_required",
            "approval_required",
        ),
        (
            PolicyContext(
                granted_scopes={"filesystem.read"},
                approval_required_risks={ToolRiskLevel.HIGH},
            ),
            "tool_approval_required",
            "risk_restricted",
        ),
    ],
)
async def test_deny_and_approval_decisions_never_invoke_handler(
    context, expected_code, expected_reason
) -> None:
    calls = 0

    def handler(arguments: Input) -> Output:
        nonlocal calls
        calls += 1
        return Output(value=arguments.value)

    registry = ToolRegistry()
    registry.register(tool("secure.read", "filesystem.read", handler, risk=ToolRiskLevel.HIGH))
    provider = SequenceProvider(
        (ToolCall(call_id="c1", name="secure.read", arguments={"value": 1}),)
    )
    result = await make_engine(provider, registry).run(
        config(names=("secure.read",), context=context)
    )
    assert result.tool_results[0].result["error_code"] == expected_code
    assert result.tool_results[0].result["policy_reason"] == expected_reason
    assert calls == 0


class AllowEverything:
    def evaluate(self, request, context):
        return PolicyDecision(effect=PolicyEffect.ALLOW, reason=PolicyReason.ALLOWED)


class RaisingEvaluator:
    def evaluate(self, request, context):
        raise RuntimeError("SYNTHETIC_SECRET_CANARY_model_arguments_call_id")


class InvalidEvaluator:
    def evaluate(self, request, context):
        return object()


@pytest.mark.asyncio
@pytest.mark.parametrize("evaluator", [AllowEverything(), RaisingEvaluator(), InvalidEvaluator()])
async def test_evaluator_cannot_escalate_and_failures_are_safe(evaluator) -> None:
    calls = 0

    def handler(arguments: Input) -> Output:
        nonlocal calls
        calls += 1
        return Output(value=arguments.value)

    registry = ToolRegistry()
    registry.register(tool("secure.read", "filesystem.read", handler))
    provider = SequenceProvider(
        (ToolCall(call_id="model-controlled-id", name="secure.read", arguments={"value": 1}),)
    )
    result = await make_engine(provider, registry, evaluator=evaluator).run(
        config(
            names=("secure.read",),
            context=PolicyContext(
                granted_scopes=(
                    frozenset()
                    if isinstance(evaluator, AllowEverything)
                    else frozenset({"filesystem.read"})
                )
            ),
        )
    )
    assert calls == 0
    assert result.tool_results[0].result["error_code"] == "tool_not_permitted"
    expected_reason = (
        "missing_scope"
        if isinstance(evaluator, AllowEverything)
        else "invalid_policy"
        if isinstance(evaluator, InvalidEvaluator)
        else "evaluator_error"
    )
    assert result.tool_results[0].result["policy_reason"] == expected_reason
    formatted = format_run_result(result)
    assert "SYNTHETIC_SECRET_CANARY" not in formatted
    assert "model-controlled-id" not in formatted
    assert "secure.read" not in formatted


@pytest.mark.asyncio
async def test_mixed_batch_has_independent_decisions_and_ordered_results() -> None:
    executed: list[str] = []

    def allowed(arguments: Input) -> Output:
        executed.append("allowed")
        return Output(value=arguments.value)

    def denied(arguments: Input) -> Output:
        executed.append("denied")
        return Output(value=arguments.value)

    registry = ToolRegistry()
    registry.register(tool("tool.allowed", "filesystem.read", allowed))
    registry.register(tool("tool.denied", "filesystem.write", denied))
    calls = (
        ToolCall(call_id="call-allowed", name="tool.allowed", arguments={"value": 1}),
        ToolCall(call_id="call-denied", name="tool.denied", arguments={"value": 2}),
    )
    provider = SequenceProvider(calls)
    result = await make_engine(provider, registry).run(
        config(
            names=("tool.allowed", "tool.denied"),
            context=PolicyContext(granted_scopes={"filesystem.read"}),
        )
    )
    assert executed == ["allowed"]
    assert [item.call_id for item in result.tool_results] == ["call-allowed", "call-denied"]
    assert [item.is_error for item in result.tool_results] == [False, True]
    assert result.tool_results[1].result["policy_reason"] == "missing_scope"
    assert result.state == RunState.COMPLETED


@pytest.mark.asyncio
async def test_unscoped_legacy_mode_is_explicit_and_name_allowlist_still_applies() -> None:
    calls = 0

    def handler(arguments: Input) -> Output:
        nonlocal calls
        calls += 1
        return Output(value=arguments.value)

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="legacy.echo",
            input_model=Input,
            executor=handler,
            execution_mode=ExecutionMode.SYNC,
        )
    )
    call = ToolCall(call_id="legacy", name="legacy.echo", arguments={"value": 1})
    provider = SequenceProvider((call,))
    result = await make_engine(provider, registry).run(
        config(names=("legacy.echo",), allow_legacy_unscoped_tools=True)
    )
    assert result.tool_results[0].is_error is False
    assert calls == 1

    provider = SequenceProvider((call,))
    result = await make_engine(provider, registry).run(
        config(names=("legacy.echo",), allow_legacy_unscoped_tools=False)
    )
    assert result.tool_results[0].is_error is True
    assert calls == 1


@pytest.mark.asyncio
async def test_model_arguments_cannot_supply_scope_authority() -> None:
    calls = 0

    def handler(arguments: Input) -> Output:
        nonlocal calls
        calls += 1
        return Output(value=arguments.value)

    registry = ToolRegistry()
    registry.register(tool("secure.read", "filesystem.read", handler))
    provider = SequenceProvider(
        (
            ToolCall(
                call_id="ignored-for-policy",
                name="secure.read",
                arguments={"value": 1, "granted_scopes": ["filesystem.read"]},
            ),
        )
    )
    result = await make_engine(provider, registry).run(
        config(names=("secure.read",), context=PolicyContext())
    )
    assert calls == 0
    assert result.tool_results[0].result["error_code"] == "tool_not_permitted"
    assert result.tool_results[0].result["policy_reason"] == "missing_scope"


@pytest.mark.asyncio
async def test_legacy_unscoped_name_denial_remains_authoritative() -> None:
    calls = 0

    def handler(arguments: Input) -> Output:
        nonlocal calls
        calls += 1
        return Output(value=arguments.value)

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="legacy.echo",
            input_model=Input,
            executor=handler,
            execution_mode=ExecutionMode.SYNC,
        )
    )
    provider = SequenceProvider(
        (ToolCall(call_id="legacy", name="legacy.echo", arguments={"value": 1}),)
    )
    result = await make_engine(provider, registry, evaluator=AllowEverything()).run(
        config(names=())
    )
    assert calls == 0
    assert result.tool_results[0].result["error_code"] == "tool_not_permitted"


@pytest.mark.asyncio
async def test_scoped_tool_without_policy_context_fails_closed() -> None:
    calls = 0

    def handler(arguments: Input) -> Output:
        nonlocal calls
        calls += 1
        return Output(value=arguments.value)

    registry = ToolRegistry()
    registry.register(tool("secure.read", "filesystem.read", handler))
    provider = SequenceProvider(
        (ToolCall(call_id="missing-context", name="secure.read", arguments={"value": 1}),)
    )
    result = await make_engine(provider, registry).run(config(names=("secure.read",), context=None))
    assert calls == 0
    assert result.tool_results[0].result["policy_reason"] == "missing_context"


@pytest.mark.asyncio
async def test_registry_change_after_policy_check_fails_closed() -> None:
    invocations: list[str] = []
    registry = ToolRegistry()

    def original(arguments: Input) -> Output:
        invocations.append("original")
        return Output(value=arguments.value)

    def replacement(arguments: Input) -> Output:
        invocations.append("replacement")
        return Output(value=arguments.value)

    original_definition = tool("secure.read", "filesystem.read", original)
    registry.register(original_definition)

    class ReplaceOnDispatch:
        evaluations = 0

        def evaluate(self, request, context):
            self.evaluations += 1
            if self.evaluations == 2:
                registry.unregister("secure.read")
                registry.register(tool("secure.read", "filesystem.write", replacement))
            return PolicyDecision(effect=PolicyEffect.ALLOW, reason=PolicyReason.ALLOWED)

    provider = SequenceProvider(
        (ToolCall(call_id="mutation", name="secure.read", arguments={"value": 1}),)
    )
    result = await make_engine(provider, registry, evaluator=ReplaceOnDispatch()).run(
        config(names=("secure.read",), context=PolicyContext(granted_scopes={"filesystem.read"}))
    )
    assert invocations == []
    assert result.tool_results[0].result["error_code"] == "tool_not_permitted"
