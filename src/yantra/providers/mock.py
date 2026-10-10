"""Deterministic model provider for tests and examples without network access."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from pydantic import JsonValue

from yantra.core.contracts import ProviderCapabilities, TokenUsage
from yantra.core.errors import (
    MockResponseSequenceExhaustedError,
    ProviderError,
    UnsupportedCapabilityError,
)
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.providers.base import (
    FinishReason,
    ModelRequest,
    ModelResponse,
    missing_capabilities,
)


class MockProvider:
    """Consumes configured responses in order and records every submitted request."""

    def __init__(
        self,
        responses: Sequence[ModelResponse | ProviderError] = (),
        *,
        provider_id: str = "mock",
        capabilities: ProviderCapabilities | None = None,
    ) -> None:
        if not provider_id.strip():
            raise ValueError("provider_id must be non-empty")
        self._provider_id = provider_id
        self._capabilities = capabilities or ProviderCapabilities(
            tool_calling=True,
            structured_output=True,
            token_usage=True,
            cancellation=True,
        )
        self._responses = list(responses)
        self._requests: list[ModelRequest] = []
        self._lock = asyncio.Lock()

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    @property
    def requests(self) -> tuple[ModelRequest, ...]:
        """Immutable snapshot of requests in deterministic consumption order."""
        return tuple(self._requests)

    @property
    def remaining_responses(self) -> int:
        return len(self._responses)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        async with self._lock:
            self._requests.append(request)
            missing = missing_capabilities(self.capabilities, request.required_capabilities)
            if missing:
                names = ", ".join(sorted(capability.value for capability in missing))
                raise UnsupportedCapabilityError(
                    f"mock provider does not support required capabilities: {names}",
                    provider_id=self.provider_id,
                )
            if not self._responses:
                raise MockResponseSequenceExhaustedError(
                    "mock provider response sequence is exhausted",
                    provider_id=self.provider_id,
                )

            outcome = self._responses.pop(0)
            if isinstance(outcome, ProviderError):
                raise outcome.clone()
            return outcome

    @staticmethod
    def text_response(
        request: ModelRequest,
        text: str,
        *,
        provider_id: str = "mock",
        usage: TokenUsage | None = None,
    ) -> ModelResponse:
        """Create a deterministic assistant text response for `request`."""
        return ModelResponse(
            request_id=request.request_id,
            provider_id=provider_id,
            model_id=request.model_id,
            message=Message(
                role=MessageRole.ASSISTANT,
                content=(TextContent(text=text),),
            ),
            finish_reason=FinishReason.STOP,
            usage=usage,
        )

    @staticmethod
    def tool_call_response(
        request: ModelRequest,
        name: str,
        arguments: dict[str, JsonValue],
        *,
        call_id: str = "mock-call-1",
        provider_id: str = "mock",
        usage: TokenUsage | None = None,
    ) -> ModelResponse:
        """Create an assistant response containing one untrusted tool proposal."""
        return ModelResponse(
            request_id=request.request_id,
            provider_id=provider_id,
            model_id=request.model_id,
            message=Message(
                role=MessageRole.ASSISTANT,
                tool_calls=(ToolCall(call_id=call_id, name=name, arguments=arguments),),
            ),
            finish_reason=FinishReason.TOOL_CALLS,
            usage=usage,
        )
