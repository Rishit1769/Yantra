"""Deterministic, fully offline first agent run for the installed package."""

from __future__ import annotations

import asyncio
from typing import cast

from pydantic import BaseModel

from yantra.core.contracts import ProviderCapabilities, TokenUsage
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.providers.base import FinishReason, ModelRequest, ModelResponse
from yantra.providers.gateway import ModelGateway
from yantra.providers.registry import ProviderRegistry
from yantra.runtime import (
    AgentExecutionEngine,
    AgentRunConfig,
    AgentRunResult,
    AgentTerminationReason,
)
from yantra.tools import ExecutionMode, SideEffect, ToolDefinition, ToolRegistry


class CalculatorInput(BaseModel):
    left: int
    right: int


class CalculatorOutput(BaseModel):
    total: int


class OfflineQuickstartProvider:
    """Deterministic model fixture implementing the provider contract."""

    provider_id = "offline-demo"
    capabilities = ProviderCapabilities(tool_calling=True, token_usage=True)

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        observations = [
            message.tool_result
            for message in request.messages
            if message.role == MessageRole.TOOL and message.tool_result is not None
        ]
        if not observations:
            return ModelResponse(
                request_id=request.request_id,
                provider_id=self.provider_id,
                model_id=request.model_id,
                message=Message(
                    role=MessageRole.ASSISTANT,
                    tool_calls=(
                        ToolCall(
                            call_id="offline-add-1",
                            name="calculator.add",
                            arguments={"left": 12, "right": 8},
                        ),
                    ),
                ),
                finish_reason=FinishReason.TOOL_CALLS,
                usage=TokenUsage(input_tokens=8, output_tokens=3, total_tokens=11),
            )

        observation = cast(dict[str, object], observations[-1].result)
        total = observation["total"]
        return ModelResponse(
            request_id=request.request_id,
            provider_id=self.provider_id,
            model_id=request.model_id,
            message=Message(
                role=MessageRole.ASSISTANT,
                content=(TextContent(text=f"12 + 8 = {total}. The sum is {total}."),),
            ),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(input_tokens=12, output_tokens=9, total_tokens=21),
        )


def create_engine() -> tuple[AgentExecutionEngine, OfflineQuickstartProvider]:
    provider = OfflineQuickstartProvider()
    providers = ProviderRegistry()
    providers.register(provider, display_name="Offline demonstration", is_local=True)
    gateway = ModelGateway(providers, default_model="offline-demo/calculator")
    tools = ToolRegistry()

    def add(arguments: CalculatorInput) -> CalculatorOutput:
        return CalculatorOutput(total=arguments.left + arguments.right)

    tools.register(
        ToolDefinition(
            name="calculator.add",
            description="Add two integers.",
            input_model=CalculatorInput,
            output_model=CalculatorOutput,
            executor=add,
            execution_mode=ExecutionMode.SYNC,
            side_effect=SideEffect.READ_ONLY,
        )
    )
    return AgentExecutionEngine(gateway, tools), provider


async def run_demo() -> tuple[AgentRunResult, OfflineQuickstartProvider]:
    """Run the same bounded model/tool/model scenario used in the quickstart."""
    engine, provider = create_engine()
    result = await engine.run(
        AgentRunConfig(
            model="offline-demo/calculator",
            messages=(
                Message(
                    role=MessageRole.USER,
                    content=(TextContent(text="Calculate 12 + 8 and explain the result."),),
                ),
            ),
            max_steps=3,
            max_tool_calls=1,
            timeout_seconds=5,
            tool_names=("calculator.add",),
        )
    )
    return result, provider


def run_quickstart() -> int:
    """Run and display the offline agent quickstart; return a process status."""
    result, provider = asyncio.run(run_demo())
    print("YANTRA quickstart (offline; no credentials or network requests)")
    if result.steps and result.steps[0].response_message.tool_calls:
        call = result.steps[0].response_message.tool_calls[0]
        print(f"Model tool proposal: {call.name}({call.arguments})")
    if result.tool_results:
        tool_result = result.tool_results[0]
        print(f"Tool result: {tool_result.result}")
    if len(result.steps) > 1:
        print(f"Final model response: {result.output or '(no visible answer)'}")
    if result.termination_reason != AgentTerminationReason.FINAL_RESPONSE:
        print(f"Quickstart failed: {result.error_code or 'unknown'}")
        return 1
    if len(provider.requests) != 2 or len(result.tool_results) != 1:
        print("Quickstart did not complete the expected tool cycle")
        return 1
    return 0
