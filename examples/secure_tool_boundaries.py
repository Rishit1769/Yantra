"""Offline demonstration of in-process and restricted subprocess tools."""

from __future__ import annotations

import asyncio
from typing import cast

from pydantic import BaseModel

from yantra.core.contracts import ProviderCapabilities
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.providers.base import FinishReason, ModelRequest, ModelResponse
from yantra.providers.gateway import ModelGateway
from yantra.providers.registry import ProviderRegistry
from yantra.runtime import AgentExecutionEngine, AgentRunConfig, format_run_result
from yantra.runtime.models import AgentRunResult
from yantra.tools import (
    ExecutionLimits,
    PolicyContext,
    ToolDefinition,
    ToolExecutionBoundaryMode,
    ToolRegistry,
)


class ConcatInput(BaseModel):
    left: str
    right: str


class LocalInput(BaseModel):
    value: str


class OfflineModel:
    provider_id = "offline-boundary-example"
    capabilities = ProviderCapabilities(tool_calling=True)

    def __init__(self, call: ToolCall) -> None:
        self.call = call

    async def complete(self, request: ModelRequest) -> ModelResponse:
        saw_tool_result = any(message.role == MessageRole.TOOL for message in request.messages)
        message = (
            Message(role=MessageRole.ASSISTANT, content=(TextContent(text="done"),))
            if saw_tool_result
            else Message(role=MessageRole.ASSISTANT, tool_calls=(self.call,))
        )
        return ModelResponse(
            request_id=request.request_id,
            provider_id=self.provider_id,
            model_id=request.model_id,
            message=message,
            finish_reason=FinishReason.STOP if saw_tool_result else FinishReason.TOOL_CALLS,
        )


async def main() -> None:
    registry = ToolRegistry()
    local_invocations = 0

    def local_echo(arguments: LocalInput) -> dict[str, str]:
        nonlocal local_invocations
        local_invocations += 1
        return {"value": arguments.value}

    registry.register(
        ToolDefinition(
            name="text.local",
            description="Return a value through a trusted in-process handler.",
            input_model=LocalInput,
            executor=local_echo,
            permission_scopes=frozenset({"text.local"}),
        )
    )
    registry.register(
        ToolDefinition(
            name="text.concat",
            description="Concatenate two strings in a fixed worker handler.",
            input_model=ConcatInput,
            execution_boundary=ToolExecutionBoundaryMode.SUBPROCESS,
            worker_handler_id="yantra.demo.concat",
            permission_scopes=frozenset({"text.combine"}),
        )
    )
    registry.register(
        ToolDefinition(
            name="text.block",
            description="Wait in a fixed worker fixture until the parent terminates it.",
            input_model=LocalInput,
            execution_boundary=ToolExecutionBoundaryMode.SUBPROCESS,
            worker_handler_id="yantra.demo.block",
            permission_scopes=frozenset({"text.block"}),
            timeout_seconds=0.05,
        )
    )

    async def invoke(call: ToolCall, scopes: frozenset[str]):
        providers = ProviderRegistry()
        providers.register(OfflineModel(call), is_local=True)
        engine = AgentExecutionEngine(
            ModelGateway(providers),
            registry,
            execution_limits=ExecutionLimits(max_execution_seconds=2),
        )
        return await engine.run(
            AgentRunConfig(
                model="offline-boundary-example/model",
                messages=(Message(role=MessageRole.USER, content=(TextContent(text="run"),)),),
                max_steps=2,
                max_tool_calls=1,
                tool_names=(call.name,),
                permission_context=PolicyContext(granted_scopes=scopes),
            )
        )

    in_process = await invoke(
        ToolCall(call_id="local-1", name="text.local", arguments={"value": "trusted"}),
        frozenset({"text.local"}),
    )
    subprocess = await invoke(
        ToolCall(
            call_id="concat-1",
            name="text.concat",
            arguments={"left": "Yan", "right": "tra"},
        ),
        frozenset({"text.combine"}),
    )
    denied = await invoke(
        ToolCall(
            call_id="denied-1",
            name="text.concat",
            arguments={"left": "not", "right": "run"},
        ),
        frozenset(),
    )
    timed_out = await invoke(
        ToolCall(call_id="block-1", name="text.block", arguments={"value": "ignored"}),
        frozenset({"text.block"}),
    )

    def result_value(result: AgentRunResult) -> dict[str, object]:
        tool_results = result.tool_results
        if not tool_results or not isinstance(tool_results[0].result, dict):
            raise SystemExit("expected a structured tool result")
        return cast(dict[str, object], tool_results[0].result)

    in_process_value = result_value(in_process)
    subprocess_value = result_value(subprocess)
    denied_value = result_value(denied)
    timeout_value = result_value(timed_out)

    print("in-process:", in_process_value)
    print("subprocess:", subprocess_value)
    print("policy denial:", denied_value.get("error_code"))
    print("timeout:", timeout_value.get("error_code"))
    print("sanitized timeout diagnostics:\n" + format_run_result(timed_out))
    if (
        local_invocations == 0
        or in_process_value != {"value": "trusted"}
        or subprocess_value != {"value": "Yantra"}
        or denied_value.get("error_code") != "tool_not_permitted"
        or timeout_value.get("error_code") != "tool_timeout"
    ):
        raise SystemExit("execution boundary demonstration failed")
    print("Boundary note: fixed-handler subprocess; not an OS sandbox.")


if __name__ == "__main__":
    asyncio.run(main())
