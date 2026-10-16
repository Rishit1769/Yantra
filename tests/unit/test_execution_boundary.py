"""Offline security and lifecycle tests for controlled tool execution boundaries."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from yantra.core.contracts import ProviderCapabilities
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.providers.base import FinishReason, ModelRequest, ModelResponse
from yantra.providers.gateway import ModelGateway
from yantra.providers.registry import ProviderRegistry
from yantra.runtime import AgentExecutionEngine, AgentRunConfig
from yantra.tools import (
    DeterministicApprovalProvider,
    ExecutionLimits,
    PolicyContext,
    PolicyDecision,
    PolicyEffect,
    PolicyReason,
    SideEffect,
    SubprocessExecutionBoundary,
    ToolDefinition,
    ToolExecutionBoundaryMode,
    ToolExecutor,
    ToolRegistry,
    ToolRiskLevel,
)
from yantra.tools.execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationAuthority,
    canonical_json_digest,
)


class ConcatInput(BaseModel):
    left: str
    right: str


class ConcatOutput(BaseModel):
    value: str


class EmptyInput(BaseModel):
    pass


class OneCallModel:
    provider_id = "boundary-test"
    capabilities = ProviderCapabilities(tool_calling=True)

    def __init__(self, call: ToolCall) -> None:
        self.call = call

    async def complete(self, request: ModelRequest) -> ModelResponse:
        saw_result = any(message.role == MessageRole.TOOL for message in request.messages)
        message = (
            Message(role=MessageRole.ASSISTANT, content=(TextContent(text="done"),))
            if saw_result
            else Message(role=MessageRole.ASSISTANT, tool_calls=(self.call,))
        )
        return ModelResponse(
            request_id=request.request_id,
            provider_id=self.provider_id,
            model_id=request.model_id,
            message=message,
            finish_reason=FinishReason.STOP if saw_result else FinishReason.TOOL_CALLS,
        )


def worker_tool(handler_id: str = "yantra.demo.concat") -> ToolDefinition:
    return ToolDefinition(
        name="worker.concat",
        input_model=ConcatInput,
        output_model=ConcatOutput,
        execution_boundary=ToolExecutionBoundaryMode.SUBPROCESS,
        worker_handler_id=handler_id,
        permission_scopes=frozenset({"demo.concat"}),
        risk_level=ToolRiskLevel.LOW,
        side_effect=SideEffect.READ_ONLY,
    )


def worker_engine(
    call: ToolCall,
    registry: ToolRegistry,
    *,
    approvals=None,
    boundary: SubprocessExecutionBoundary | None = None,
) -> AgentExecutionEngine:
    providers = ProviderRegistry()
    providers.register(OneCallModel(call), is_local=True)
    return AgentExecutionEngine(
        ModelGateway(providers),
        registry,
        approval_provider=approvals,
        subprocess_boundary=boundary,
    )


def worker_config(context: PolicyContext, *, timeout: float = 5.0) -> AgentRunConfig:
    return AgentRunConfig(
        model="boundary-test/model",
        messages=(Message(role=MessageRole.USER, content=(TextContent(text="run"),)),),
        max_steps=2,
        max_tool_calls=1,
        timeout_seconds=timeout,
        tool_names=("worker.concat",),
        permission_context=context,
    )


async def direct_worker_execution(
    definition: ToolDefinition,
    arguments: dict[str, Any],
    *,
    boundary: SubprocessExecutionBoundary | None = None,
    timeout: float = 2.0,
    executor: ToolExecutor | None = None,
):
    registry = ToolRegistry()
    registry.register(definition)
    tool_executor = executor or ToolExecutor(registry, subprocess_boundary=boundary)
    authority = ExecutionAuthorizationAuthority()
    tool_executor._bind_authorization_key(authority._verifier_key())
    call = ToolCall(call_id="direct-call", name=definition.name, arguments=arguments)
    validated = definition.validate_input(call.arguments)
    del validated
    decision = PolicyDecision(effect=PolicyEffect.ALLOW, reason=PolicyReason.ALLOWED)
    token = authority.issue(
        run_id=uuid4(),
        call_id=call.call_id,
        definition=definition,
        arguments_sha256=canonical_json_digest(arguments),
        decision=decision,
        approval_granted=False,
    )
    run_id = token.run_id
    result = await tool_executor.execute(
        call,
        authorization=decision,
        execution_authorization=token,
        run_id=run_id,
        expected_definition=definition,
        timeout_seconds=timeout,
    )
    return result, tool_executor, token, authority, run_id, call


@pytest.mark.asyncio
async def test_explicitly_registered_subprocess_tool_executes_and_correlates() -> None:
    registry = ToolRegistry()
    registry.register(worker_tool())
    call = ToolCall(
        call_id="model-correlation",
        name="worker.concat",
        arguments={"left": "Yan", "right": "tra"},
    )
    engine = worker_engine(call, registry)
    result = await engine.run(worker_config(PolicyContext(granted_scopes={"demo.concat"})))
    assert result.tool_results[0].call_id == call.call_id
    assert result.tool_results[0].result == {"value": "Yantra"}
    assert engine.tool_executor.subprocess_boundary.active_worker_count == 0


@pytest.mark.asyncio
async def test_scope_and_name_denials_happen_before_worker_dispatch() -> None:
    class CountingBoundary(SubprocessExecutionBoundary):
        calls = 0

        async def execute(self, *args, **kwargs):
            self.calls += 1
            return await super().execute(*args, **kwargs)

    registry = ToolRegistry()
    registry.register(worker_tool())
    call = ToolCall(call_id="denied", name="worker.concat", arguments={"left": "a", "right": "b"})
    boundary = CountingBoundary()
    result = await worker_engine(call, registry, boundary=boundary).run(
        worker_config(PolicyContext())
    )
    assert result.tool_results[0].is_error
    assert boundary.calls == 0

    result = await worker_engine(call, registry, boundary=boundary).run(
        worker_config(PolicyContext(granted_scopes={"demo.concat"})).model_copy(
            update={"tool_names": ()}
        )
    )
    assert result.tool_results[0].result["error_code"] == "tool_not_permitted"
    assert boundary.calls == 0


@pytest.mark.asyncio
async def test_approval_is_required_before_subprocess_dispatch() -> None:
    class CountingBoundary(SubprocessExecutionBoundary):
        calls = 0

        async def execute(self, *args, **kwargs):
            self.calls += 1
            return await super().execute(*args, **kwargs)

    definition = worker_tool()
    registry = ToolRegistry()
    registry.register(definition.model_copy(update={"risk_level": ToolRiskLevel.HIGH}))
    call = ToolCall(call_id="approval", name=definition.name, arguments={"left": "a", "right": "b"})
    boundary = CountingBoundary()
    engine = worker_engine(call, registry, boundary=boundary)
    denied = await engine.run(
        worker_config(
            PolicyContext(
                granted_scopes={"demo.concat"},
                approval_required_risks={ToolRiskLevel.HIGH},
            )
        )
    )
    assert denied.tool_results[0].result["error_code"] == "tool_approval_required"
    assert boundary.calls == 0

    allowed = await worker_engine(
        call,
        registry,
        boundary=boundary,
        approvals=DeterministicApprovalProvider(approved_tools=frozenset({definition.name})),
    ).run(
        worker_config(
            PolicyContext(
                granted_scopes={"demo.concat"},
                approval_required_risks={ToolRiskLevel.HIGH},
            )
        )
    )
    assert allowed.tool_results[0].result == {"value": "ab"}
    assert boundary.calls == 1


@pytest.mark.asyncio
async def test_public_decision_and_forged_or_replayed_signed_authority_fail() -> None:
    definition = worker_tool()
    registry = ToolRegistry()
    registry.register(definition)
    executor = ToolExecutor(registry)
    call = ToolCall(
        call_id="direct-call", name=definition.name, arguments={"left": "a", "right": "b"}
    )
    public_allow = PolicyDecision(effect=PolicyEffect.ALLOW, reason=PolicyReason.ALLOWED)
    result = await executor.execute(
        call, authorization=public_allow, expected_definition=definition
    )
    assert result.is_error

    result, executor, token, authority, run_id, call = await direct_worker_execution(
        definition,
        {"left": "a", "right": "b"},
        executor=executor,
    )
    assert result.result == {"value": "ab"}
    replay = await executor.execute(
        call,
        authorization=token.decision,
        execution_authorization=token,
        run_id=run_id,
        expected_definition=definition,
    )
    assert replay.is_error
    forged = token.model_copy(update={"signature": "0" * 64})
    assert isinstance(forged, ExecutionAuthorization)
    result = await executor.execute(
        call,
        authorization=token.decision,
        execution_authorization=forged,
        run_id=run_id,
        expected_definition=definition,
    )
    assert result.is_error
    del authority


@pytest.mark.asyncio
async def test_worker_startup_protocol_crash_and_tool_failures_are_safe(tmp_path: Path) -> None:
    boundary = SubprocessExecutionBoundary()

    class StartupFailureBoundary(SubprocessExecutionBoundary):
        async def _spawn_worker(self):
            raise FileNotFoundError("fixture startup failure")

    missing_boundary = StartupFailureBoundary()
    result, *_ = await direct_worker_execution(
        worker_tool(), {"left": "a", "right": "b"}, boundary=missing_boundary
    )
    assert result.result["error_code"] == "tool_worker_startup_failed"

    for script_body in (
        "import sys\nsys.stdin.buffer.read()\nsys.stdout.write('{bad json')\n",
        "import sys,json\n"
        "r=json.loads(sys.stdin.read())\n"
        "response={'protocol_version':9,'invocation_id':r['invocation_id'],"
        "'status':'succeeded','value':{'value':'x'}}\n"
        "sys.stdout.write(json.dumps(response))\n",
    ):
        script = tmp_path / f"worker-{len(script_body)}.py"
        script.write_text(script_body, encoding="utf-8")
        malformed_boundary = SubprocessExecutionBoundary()
        malformed_boundary._worker_script = script
        result, *_ = await direct_worker_execution(
            worker_tool(), {"left": "a", "right": "b"}, boundary=malformed_boundary
        )
        assert result.result["error_code"] == "tool_worker_protocol_error"

    crashed, *_ = await direct_worker_execution(
        worker_tool("yantra.demo.crash"),
        {"left": "a", "right": "b"},
        boundary=boundary,
    )
    assert crashed.result["error_code"] == "tool_worker_failed"
    failed, *_ = await direct_worker_execution(
        worker_tool("yantra.demo.tool_error"),
        {"left": "a", "right": "b"},
        boundary=boundary,
    )
    assert failed.result["error_code"] == "tool_exception"


@pytest.mark.asyncio
async def test_worker_input_and_output_limits_are_enforced() -> None:
    class LargeInput(BaseModel):
        value: str

    large_tool = ToolDefinition(
        name="worker.echo",
        input_model=LargeInput,
        execution_boundary=ToolExecutionBoundaryMode.SUBPROCESS,
        worker_handler_id="yantra.demo.echo",
        permission_scopes=frozenset({"demo.echo"}),
    )
    boundary = SubprocessExecutionBoundary(ExecutionLimits(max_request_bytes=1024))
    oversized = await _run_direct(large_tool, {"value": "x" * 2048}, boundary)
    assert oversized.result["error_code"] == "tool_request_too_large"
    assert boundary.active_worker_count == 0

    output_tool = ToolDefinition(
        name="worker.large",
        input_model=EmptyInput,
        execution_boundary=ToolExecutionBoundaryMode.SUBPROCESS,
        worker_handler_id="yantra.demo.large_response",
        permission_scopes=frozenset({"demo.large"}),
    )
    oversized_output = await _run_direct(output_tool, {}, SubprocessExecutionBoundary())
    assert oversized_output.result["error_code"] == "tool_response_too_large"


async def _run_direct(
    definition: ToolDefinition,
    arguments: dict[str, Any],
    boundary: SubprocessExecutionBoundary,
):
    result, *_ = await direct_worker_execution(definition, arguments, boundary=boundary)
    return result


@pytest.mark.asyncio
async def test_worker_timeout_cancellation_and_repeated_cleanup() -> None:
    empty = ToolDefinition(
        name="worker.block",
        input_model=EmptyInput,
        execution_boundary=ToolExecutionBoundaryMode.SUBPROCESS,
        worker_handler_id="yantra.demo.block",
        permission_scopes=frozenset({"demo.block"}),
    )
    timed, timed_boundary = await _run_with_boundary(empty, {}, timeout=0.05)
    assert timed.result["error_code"] == "tool_timeout"
    assert timed_boundary.active_worker_count == 0

    boundary = SubprocessExecutionBoundary()
    task = asyncio.create_task(_run_direct(empty, {}, boundary))
    async with asyncio.timeout(5):
        while boundary.active_worker_count == 0:
            await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert boundary.active_worker_count == 0

    echo = worker_tool()
    results = await asyncio.gather(
        *(_run_direct(echo, {"left": "a", "right": str(index)}, boundary) for index in range(4))
    )
    assert all(result.result["value"].startswith("a") for result in results)
    assert boundary.active_worker_count == 0


async def _run_with_boundary(
    definition: ToolDefinition, arguments: dict[str, Any], *, timeout: float
):
    boundary = SubprocessExecutionBoundary()
    result, *_ = await direct_worker_execution(
        definition, arguments, boundary=boundary, timeout=timeout
    )
    return result, boundary


def test_execution_contracts_reject_unknown_handlers_and_malformed_protocol() -> None:
    with pytest.raises(ValidationError):
        ToolDefinition(
            name="worker.invalid",
            input_model=EmptyInput,
            execution_boundary=ToolExecutionBoundaryMode.SUBPROCESS,
            worker_handler_id="../../shell",
        )
    with pytest.raises(ValidationError):
        ToolDefinition(
            name="worker.missing",
            input_model=EmptyInput,
            execution_boundary=ToolExecutionBoundaryMode.SUBPROCESS,
        )
