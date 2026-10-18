"""A deterministic model → validated tool → model agent run; no network access."""

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
    format_run_result,
)
from yantra.tools import ExecutionMode, SideEffect, ToolDefinition, ToolRegistry


class CalculatorInput(BaseModel):
    left: int
    right: int


class CalculatorOutput(BaseModel):
    total: int


class OfflineAgentProvider:
    """Small deterministic fixture implementing the existing provider contract."""

    provider_id = "offline-demo"
    capabilities = ProviderCapabilities(tool_calling=True, token_usage=True)

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        tool_observations = [
            message.tool_result
            for message in request.messages
            if message.role == MessageRole.TOOL and message.tool_result is not None
        ]
        if not tool_observations:
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

        observation = cast(dict[str, object], tool_observations[-1].result)
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


def create_engine() -> tuple[AgentExecutionEngine, OfflineAgentProvider]:
    provider = OfflineAgentProvider()
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


async def run_demo() -> tuple[AgentRunResult, OfflineAgentProvider]:
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


async def main() -> None:
    result, provider = await run_demo()
    print("YANTRA offline agent demonstration (no network requests)")
    print(f"Final answer: {result.output or '(no visible answer)'}")
    print(format_run_result(result))
    if result.termination_reason != AgentTerminationReason.FINAL_RESPONSE:
        raise SystemExit(f"offline agent demo failed: {result.error_code or 'unknown'}")
    if len(provider.requests) != 2 or len(result.tool_results) != 1:
        raise SystemExit("offline agent demo did not complete the expected tool cycle")


if __name__ == "__main__":
    asyncio.run(main())
