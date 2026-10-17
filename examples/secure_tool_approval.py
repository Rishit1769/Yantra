"""Offline demonstration of trusted, exact-invocation tool approvals."""

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
from yantra.tools import (
    ApprovalDecision,
    ApprovalProvider,
    ApprovalRequest,
    DeterministicApprovalProvider,
    ExecutionMode,
    PolicyContext,
    SideEffect,
    ToolDefinition,
    ToolRegistry,
)


class WriteInput(BaseModel):
    key: str
    value: str


class OfflineModel:
    provider_id = "offline-approval-example"
    capabilities = ProviderCapabilities(tool_calling=True)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        saw_result = any(message.role == MessageRole.TOOL for message in request.messages)
        message = (
            Message(role=MessageRole.ASSISTANT, content=(TextContent(text="finished"),))
            if saw_result
            else Message(
                role=MessageRole.ASSISTANT,
                tool_calls=(
                    ToolCall(
                        call_id="same-model-call-id",
                        name="memory.write",
                        arguments={"key": "status", "value": "ready"},
                    ),
                ),
            )
        )
        return ModelResponse(
            request_id=request.request_id,
            provider_id=self.provider_id,
            model_id=request.model_id,
            message=message,
            finish_reason=FinishReason.STOP if saw_result else FinishReason.TOOL_CALLS,
        )


class ReplayingProvider:
    """Deliberately returns a prior trusted response to demonstrate replay rejection."""

    def __init__(self) -> None:
        self._response: ApprovalDecision | None = None

    async def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        if self._response is not None:
            return self._response
        self._response = await DeterministicApprovalProvider(
            approved_tools=frozenset({"memory.write"})
        ).request_approval(request)
        return self._response


def engine(registry: ToolRegistry, approvals: ApprovalProvider) -> AgentExecutionEngine:
    providers = ProviderRegistry()
    providers.register(OfflineModel(), is_local=True)
    return AgentExecutionEngine(ModelGateway(providers), registry, approval_provider=approvals)


async def main() -> None:
    memory: dict[str, str] = {}
    writes: list[None] = []

    def write_value(arguments: WriteInput) -> dict[str, str]:
        writes.append(None)
        memory[arguments.key] = arguments.value
        return {"stored": arguments.key}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="memory.write",
            description="Write to an in-memory dictionary used only by this example.",
            input_model=WriteInput,
            executor=write_value,
            execution_mode=ExecutionMode.SYNC,
            permission_scopes=frozenset({"memory.write"}),
            side_effect=SideEffect.REVERSIBLE,
        )
    )
    context = PolicyContext(
        granted_scopes=frozenset({"memory.write"}),
        approval_required_scopes=frozenset({"memory.write"}),
    )

    async def invoke(approvals: ApprovalProvider):
        return await engine(registry, approvals).run(
            AgentRunConfig(
                model="offline-approval-example/model",
                messages=(Message(role=MessageRole.USER, content=(TextContent(text="write"),)),),
                max_steps=2,
                max_tool_calls=1,
                tool_names=("memory.write",),
                permission_context=context,
            )
        )

    approved = await invoke(
        DeterministicApprovalProvider(approved_tools=frozenset({"memory.write"}))
    )
    rejected = await invoke(DeterministicApprovalProvider())
    replay_provider = ReplayingProvider()
    await invoke(replay_provider)
    replayed = await invoke(replay_provider)
    if not approved.tool_results or not rejected.tool_results or not replayed.tool_results:
        print(format_run_result(approved))
        print("approval demonstration produced no tool result")
        raise SystemExit(1)
    print("approved:", "success" if not approved.tool_results[0].is_error else "failed")
    print("rejected:", cast(dict[str, object], rejected.tool_results[0].result)["error_code"])
    print("replay:", cast(dict[str, object], replayed.tool_results[0].result)["error_code"])
    print("handler writes:", len(writes))
    print("sanitized diagnostics:\n" + format_run_result(replayed))
    if (
        len(writes) != 2
        or not rejected.tool_results[0].is_error
        or not replayed.tool_results[0].is_error
    ):
        raise SystemExit("secure approval demonstration failed")


if __name__ == "__main__":
    asyncio.run(main())
