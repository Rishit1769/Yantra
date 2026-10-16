"""Offline demonstration of an approved fixed-handler subprocess tool."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from yantra.core.contracts import ProviderCapabilities
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.providers.base import FinishReason, ModelRequest, ModelResponse
from yantra.providers.gateway import ModelGateway
from yantra.providers.registry import ProviderRegistry
from yantra.runtime import AgentExecutionEngine, AgentRunConfig, format_run_result
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


class OfflineModel:
    provider_id = "offline-boundary-example"
    capabilities = ProviderCapabilities(tool_calling=True)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        saw_tool_result = any(message.role == MessageRole.TOOL for message in request.messages)
        message = (
            Message(role=MessageRole.ASSISTANT, content=(TextContent(text="combined"),))
            if saw_tool_result
            else Message(
                role=MessageRole.ASSISTANT,
                tool_calls=(
                    ToolCall(
                        call_id="concat-1",
                        name="text.concat",
                        arguments={"left": "Yan", "right": "tra"},
                    ),
                ),
            )
        )
        return ModelResponse(
            request_id=request.request_id,
            provider_id=self.provider_id,
            model_id=request.model_id,
            message=message,
            finish_reason=FinishReason.STOP if saw_tool_result else FinishReason.TOOL_CALLS,
        )


async def main() -> None:
    providers = ProviderRegistry()
    providers.register(OfflineModel(), is_local=True)
    registry = ToolRegistry()
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
    engine = AgentExecutionEngine(
        ModelGateway(providers),
        registry,
        execution_limits=ExecutionLimits(max_execution_seconds=2),
    )
    result = await engine.run(
        AgentRunConfig(
            model="offline-boundary-example/model",
            messages=(Message(role=MessageRole.USER, content=(TextContent(text="combine"),)),),
            max_steps=2,
            max_tool_calls=1,
            tool_names=("text.concat",),
            permission_context=PolicyContext(granted_scopes=frozenset({"text.combine"})),
        )
    )
    print("tool result:", result.tool_results[0].result if result.tool_results else "missing")
    print(format_run_result(result))
    if (
        not result.tool_results
        or result.tool_results[0].is_error
        or result.tool_results[0].result != {"value": "Yantra"}
    ):
        raise SystemExit("subprocess boundary demonstration failed")
    print("Boundary note: fixed handler subprocess; not an OS sandbox.")


if __name__ == "__main__":
    asyncio.run(main())
