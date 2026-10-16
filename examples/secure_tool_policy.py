"""Deterministic offline example of scoped tool authorization."""

from __future__ import annotations

import asyncio
from typing import cast

from pydantic import BaseModel

from yantra.core.contracts import ProviderCapabilities
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.providers.base import FinishReason, ModelRequest, ModelResponse
from yantra.providers.gateway import ModelGateway
from yantra.providers.registry import ProviderRegistry
from yantra.runtime import AgentExecutionEngine, AgentRunConfig
from yantra.tools import (
    ExecutionMode,
    PolicyContext,
    SideEffect,
    ToolDefinition,
    ToolRegistry,
)


class ReadInput(BaseModel):
    key: str


class OfflinePolicyProvider:
    provider_id = "offline-policy-example"
    capabilities = ProviderCapabilities(tool_calling=True)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        saw_tool_result = any(message.role == MessageRole.TOOL for message in request.messages)
        message = (
            Message(role=MessageRole.ASSISTANT, content=(TextContent(text="finished"),))
            if saw_tool_result
            else Message(
                role=MessageRole.ASSISTANT,
                tool_calls=(
                    ToolCall(
                        call_id="offline-policy-call",
                        name="store.read",
                        arguments={"key": "status"},
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
    invocations = 0

    def read_value(arguments: ReadInput) -> dict[str, str]:
        nonlocal invocations
        invocations += 1
        return {"value": f"offline:{arguments.key}"}

    tools = ToolRegistry()
    tools.register(
        ToolDefinition(
            name="store.read",
            description="Read a deterministic in-memory example value.",
            input_model=ReadInput,
            executor=read_value,
            execution_mode=ExecutionMode.SYNC,
            permission_scopes=frozenset({"store.read"}),
            side_effect=SideEffect.READ_ONLY,
        )
    )
    provider = OfflinePolicyProvider()
    providers = ProviderRegistry()
    providers.register(provider, is_local=True)
    engine = AgentExecutionEngine(ModelGateway(providers), tools)

    async def invoke(context: PolicyContext) -> str:
        result = await engine.run(
            AgentRunConfig(
                model="offline-policy-example/store",
                messages=(
                    Message(role=MessageRole.USER, content=(TextContent(text="read status"),)),
                ),
                max_steps=2,
                max_tool_calls=1,
                tool_names=("store.read",),
                permission_context=context,
            )
        )
        observation = cast(dict[str, object], result.tool_results[0].result)
        return str(observation.get("error_code", observation.get("value", "unknown")))

    allowed = await invoke(PolicyContext(granted_scopes={"store.read"}))
    denied = await invoke(PolicyContext())
    print(f"with explicit grant: {allowed}")
    print(f"without grant: {denied}")
    print(f"handler invocations: {invocations}")
    if allowed != "offline:status" or denied != "tool_not_permitted" or invocations != 1:
        raise SystemExit("secure tool policy example failed")


if __name__ == "__main__":
    asyncio.run(main())
