from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from yantra.core.contracts import ModelCapability, ProviderCapabilities, TokenUsage
from yantra.core.errors import (
    MockResponseSequenceExhaustedError,
    ProviderTimeoutError,
    UnsupportedCapabilityError,
)
from yantra.core.messages import Message, MessageRole, TextContent
from yantra.core.tools_schema import ProviderToolSchema
from yantra.providers.base import FinishReason, ModelRequest
from yantra.providers.mock import MockProvider


def request(request_id: UUID | None = None) -> ModelRequest:
    return ModelRequest(
        request_id=request_id or uuid4(),
        model_id="mock-small",
        messages=(Message(role=MessageRole.USER, content=(TextContent(text="hello"),)),),
    )


async def test_mock_provider_returns_configured_text_and_records_requests() -> None:
    model_request = request()
    usage = TokenUsage(input_tokens=2, output_tokens=4, total_tokens=6)
    response = MockProvider.text_response(model_request, "hello back", usage=usage)
    provider = MockProvider([response])

    result = await provider.complete(model_request)

    assert result.message.content[0].text == "hello back"
    assert result.usage == usage
    assert provider.requests == (model_request,)
    assert provider.remaining_responses == 0


async def test_mock_provider_returns_tool_call_response() -> None:
    model_request = request()
    response = MockProvider.tool_call_response(
        model_request,
        "demo.echo",
        {"text": "hello"},
    )
    provider = MockProvider([response])

    result = await provider.complete(model_request)

    assert result.finish_reason == FinishReason.TOOL_CALLS
    assert result.message.tool_calls[0].name == "demo.echo"
    assert result.message.tool_calls[0].arguments == {"text": "hello"}


async def test_mock_provider_consumes_responses_in_configured_order() -> None:
    first_request = request()
    second_request = request()
    provider = MockProvider(
        [
            MockProvider.text_response(first_request, "first"),
            MockProvider.text_response(second_request, "second"),
        ]
    )

    first_response = await provider.complete(first_request)
    second_response = await provider.complete(second_request)

    assert first_response.message.content[0].text == "first"
    assert second_response.message.content[0].text == "second"
    assert provider.requests == (first_request, second_request)


async def test_mock_provider_simulates_provider_errors() -> None:
    provider = MockProvider([ProviderTimeoutError("provider timeout", retryable=True)])
    with pytest.raises(ProviderTimeoutError, match="provider timeout") as error:
        await provider.complete(request())
    assert error.value.retryable
    assert len(provider.requests) == 1


async def test_mock_provider_rejects_empty_sequence() -> None:
    provider = MockProvider()
    with pytest.raises(MockResponseSequenceExhaustedError):
        await provider.complete(request())


async def test_mock_provider_checks_capabilities_without_consuming_response() -> None:
    model_request = request()
    response = MockProvider.text_response(model_request, "unused")
    provider = MockProvider([response])
    unsupported_request = model_request.model_copy(
        update={"required_capabilities": frozenset({ModelCapability.STREAMING})}
    )

    with pytest.raises(UnsupportedCapabilityError):
        await provider.complete(unsupported_request)

    assert provider.remaining_responses == 1
    assert provider.requests == (unsupported_request,)


def test_request_requires_explicit_capabilities_for_tools_and_schemas() -> None:
    messages = (Message(role=MessageRole.USER, content=(TextContent(text="hello"),)),)
    tool_schema = ProviderToolSchema(name="demo.echo", description="Echo", parameters={})

    with pytest.raises(ValidationError, match="tool_calling"):
        ModelRequest(model_id="mock-small", messages=messages, tools=(tool_schema,))
    with pytest.raises(ValidationError, match="structured_output"):
        ModelRequest(
            model_id="mock-small",
            messages=messages,
            response_schema={"type": "object"},
        )


def test_provider_capabilities_do_not_assume_remote_cancellation() -> None:
    assert not ProviderCapabilities().cancellation
