"""Anthropic Messages API adapter with explicit system/tool translation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any, cast

import httpx
from pydantic import JsonValue, SecretStr

from yantra.core.contracts import ProviderCapabilities, TokenUsage, merge_capabilities
from yantra.core.errors import ProviderError, ProviderInvalidRequestError, ProviderProtocolError
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.providers.adapters.common import is_json_object, iter_sse_data
from yantra.providers.base import (
    FinishReason,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    ToolCallDelta,
)
from yantra.providers.catalog import ModelCatalogEntry
from yantra.providers.http import HttpxProvider
from yantra.providers.validation import CredentialValidationResult, CredentialValidationStatus
from yantra.security.credentials import CredentialManager


class AnthropicAdapter(HttpxProvider):
    """Anthropic Messages adapter, keeping Anthropic content blocks and IDs explicit."""

    API_VERSION = "2023-06-01"
    _allowed_options = frozenset(
        {"tool_choice", "thinking", "service_tier", "metadata", "cache_control"}
    )

    def __init__(
        self,
        *,
        provider_id: str = "anthropic",
        credential_reference: str | None = "env://ANTHROPIC_API_KEY",
        credential_manager: CredentialManager | None = None,
        base_url: str = "https://api.anthropic.com/v1",
        trusted_hosts: frozenset[str] = frozenset({"api.anthropic.com"}),
        credential_header: str = "x-api-key",
        credential_scheme: str = "",
        client: httpx.AsyncClient | None = None,
        capability_overrides: Mapping[str, ProviderCapabilities] | None = None,
        session_header_name: str | None = None,
    ) -> None:
        super().__init__(
            provider_id,
            base_url,
            credential_reference=credential_reference,
            credential_manager=credential_manager,
            trusted_hosts=trusted_hosts,
            client=client,
            session_header_name=session_header_name,
        )
        self._capability_overrides = dict(capability_overrides or {})
        self._credential_header = credential_header
        self._credential_scheme = credential_scheme

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True, token_usage=True)

    def capabilities_for(self, model_id: str) -> ProviderCapabilities:
        return merge_capabilities(self.capabilities, self._capability_overrides.get(model_id))

    def _headers(
        self,
        secret: SecretStr | None = None,
        *,
        stream: bool = False,
        request: ModelRequest | None = None,
    ) -> dict[str, str]:
        return {
            **self.request_headers(request),
            "Content-Type": "application/json",
            "anthropic-version": self.API_VERSION,
            "accept": "text/event-stream" if stream else "application/json",
            **self.auth_headers(
                header_name=self._credential_header,
                scheme=self._credential_scheme,
                secret_override=secret,
            ),
        }

    async def list_models(
        self, *, secret: SecretStr | None = None
    ) -> tuple[ModelCatalogEntry, ...]:
        entries: list[ModelCatalogEntry] = []
        after_id: str | None = None
        for _ in range(20):
            params = {"limit": "1000"}
            if after_id:
                params["after_id"] = after_id
            payload, _ = await self.request_json(
                "GET", "models", headers=self._headers(secret), params=params
            )
            data = payload.get("data")
            if not isinstance(data, list):
                raise ProviderProtocolError(
                    "Anthropic model catalog was malformed", provider_id=self.provider_id
                )
            for item in cast(list[Any], data):
                if not is_json_object(item) or not isinstance(item.get("id"), str):
                    continue
                display_name = item.get("display_name")
                caps = self.capabilities_for(item["id"])
                api_caps = item.get("capabilities")
                if is_json_object(api_caps):
                    structured = api_caps.get("structured_outputs")
                    if is_json_object(structured) and isinstance(structured.get("supported"), bool):
                        caps = caps.model_copy(
                            update={"structured_output": structured["supported"]}
                        )
                entries.append(
                    ModelCatalogEntry(
                        provider_id=self.provider_id,
                        model_id=item["id"],
                        display_name=display_name if isinstance(display_name, str) else None,
                        capabilities=caps,
                        context_window_tokens=(
                            item.get("max_input_tokens")
                            if isinstance(item.get("max_input_tokens"), int)
                            else None
                        ),
                        max_output_tokens=(
                            item.get("max_tokens")
                            if isinstance(item.get("max_tokens"), int)
                            else None
                        ),
                        metadata={
                            "lifecycle": item.get("lifecycle", "unknown"),
                            "created_at": item.get("created_at", "unknown"),
                        },
                    )
                )
            if payload.get("has_more") is not True:
                break
            next_id = payload.get("last_id")
            if not isinstance(next_id, str) or next_id == after_id:
                raise ProviderProtocolError(
                    "Anthropic model pagination cursor was invalid", provider_id=self.provider_id
                )
            after_id = next_id
        else:
            raise ProviderProtocolError(
                "Anthropic model catalog exceeded pagination limit", provider_id=self.provider_id
            )
        return tuple(entries)

    async def validate_credentials(self, secret: SecretStr | None) -> CredentialValidationResult:
        if secret is None:
            return CredentialValidationResult(
                provider_id=self.provider_id,
                status=CredentialValidationStatus.UNVERIFIED,
                message="Anthropic credential was not supplied",
            )
        try:
            models = await self.list_models(secret=secret)
        except ProviderError as exc:
            return _validation_from_error(self.provider_id, exc)
        return CredentialValidationResult(
            provider_id=self.provider_id,
            status=CredentialValidationStatus.VALID,
            message="Authenticated model listing succeeded; model access remains model-specific",
            catalog_model_count=len(models),
        )

    def build_payload(self, request: ModelRequest, *, stream: bool = False) -> dict[str, Any]:
        system: list[dict[str, str]] = []
        messages: list[dict[str, Any]] = []
        conversation_started = False
        for message in request.messages:
            if message.role in (MessageRole.SYSTEM, MessageRole.DEVELOPER):
                if conversation_started:
                    raise ProviderInvalidRequestError(
                        "Anthropic Messages cannot represent system/developer messages "
                        "after conversation turns",
                        provider_id=self.provider_id,
                    )
                system.extend({"type": "text", "text": part.text} for part in message.content)
                continue
            conversation_started = True
            if message.role == MessageRole.TOOL:
                result = message.tool_result
                if result is None:
                    raise ProviderInvalidRequestError(
                        "tool message has no result", provider_id=self.provider_id
                    )
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": result.call_id,
                                "content": json.dumps(
                                    result.result, separators=(",", ":"), ensure_ascii=False
                                ),
                                "is_error": result.is_error,
                            }
                        ],
                    }
                )
                continue
            content: list[dict[str, Any]] = [
                {"type": "text", "text": part.text} for part in message.content
            ]
            if message.role == MessageRole.ASSISTANT:
                content.extend(
                    {
                        "type": "tool_use",
                        "id": call.call_id,
                        "name": call.name,
                        "input": call.arguments,
                    }
                    for call in message.tool_calls
                )
            messages.append({"role": message.role.value, "content": content})

        max_tokens = request.generation.max_output_tokens
        if max_tokens is None:
            raise ProviderInvalidRequestError(
                "Anthropic requires max_output_tokens in GenerationSettings",
                provider_id=self.provider_id,
            )
        payload: dict[str, Any] = {
            "model": request.model_id,
            "max_tokens": max_tokens,
            "messages": messages,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if request.generation.temperature is not None:
            payload["temperature"] = request.generation.temperature
        if request.generation.top_p is not None:
            payload["top_p"] = request.generation.top_p
        if request.generation.stop_sequences:
            payload["stop_sequences"] = list(request.generation.stop_sequences)
        if request.tools:
            payload["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for tool in request.tools
            ]
        if request.response_schema is not None:
            payload["output_config"] = {
                "format": {"type": "json_schema", "schema": request.response_schema}
            }
        for key, value in request.provider_options.items():
            if key not in self._allowed_options:
                raise ProviderInvalidRequestError(
                    f"Anthropic option {key!r} is not supported by the adapter",
                    provider_id=self.provider_id,
                )
            payload[key] = value
        return payload

    async def complete(self, request: ModelRequest) -> ModelResponse:
        payload, headers = await self.request_json(
            "POST",
            "messages",
            headers=self._headers(request=request),
            json_body=self.build_payload(request),
            timeout_seconds=request.timeout_seconds,
        )
        return parse_anthropic_response(
            payload,
            request,
            provider_id=self.provider_id,
            provider_request_id=headers.get("request-id"),
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        async with self.stream_response(
            "POST",
            "messages",
            headers=self._headers(stream=True, request=request),
            json_body=self.build_payload(request, stream=True),
            timeout_seconds=request.timeout_seconds,
        ) as response:
            yield ModelStreamEvent(
                event_type=ModelStreamEventType.RESPONSE_STARTED,
                request_id=request.request_id,
                provider_id=self.provider_id,
                model_id=request.model_id,
            )
            tool_ids: dict[int, tuple[str | None, str | None]] = {}
            message_model = request.model_id
            finish: FinishReason | None = None
            async for data in iter_sse_data(response, max_stream_bytes=self._max_response_bytes):
                if not data:
                    continue
                try:
                    item = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise ProviderProtocolError(
                        "Anthropic stream event was invalid JSON", provider_id=self.provider_id
                    ) from exc
                if not is_json_object(item):
                    continue
                event_name = item.get("type")
                if event_name == "message_start":
                    message = item.get("message")
                    if is_json_object(message) and isinstance(message.get("model"), str):
                        message_model = message["model"]
                    usage = _anthropic_usage(
                        message.get("usage") if is_json_object(message) else None
                    )
                    if usage is not None:
                        yield _anthropic_usage_event(
                            request, self.provider_id, message_model, usage
                        )
                elif event_name == "content_block_start":
                    index = item.get("index")
                    block = item.get("content_block")
                    if (
                        isinstance(index, int)
                        and is_json_object(block)
                        and block.get("type") == "tool_use"
                    ):
                        call_id = block.get("id")
                        name = block.get("name")
                        tool_ids[index] = (
                            call_id if isinstance(call_id, str) else None,
                            name if isinstance(name, str) else None,
                        )
                        yield ModelStreamEvent(
                            event_type=ModelStreamEventType.TOOL_CALL_DELTA,
                            request_id=request.request_id,
                            provider_id=self.provider_id,
                            model_id=message_model,
                            tool_call_delta=ToolCallDelta(
                                index=index,
                                call_id=tool_ids[index][0],
                                name_delta=tool_ids[index][1],
                            ),
                        )
                elif event_name == "content_block_delta":
                    index = item.get("index")
                    delta = item.get("delta")
                    if not is_json_object(delta):
                        continue
                    if delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
                        yield ModelStreamEvent(
                            event_type=ModelStreamEventType.TEXT_DELTA,
                            request_id=request.request_id,
                            provider_id=self.provider_id,
                            model_id=message_model,
                            text_delta=delta["text"],
                        )
                    elif delta.get("type") == "thinking_delta" and isinstance(
                        delta.get("thinking"), str
                    ):
                        yield ModelStreamEvent(
                            event_type=ModelStreamEventType.REASONING_DELTA,
                            request_id=request.request_id,
                            provider_id=self.provider_id,
                            model_id=message_model,
                            text_delta=delta["thinking"],
                        )
                    elif delta.get("type") == "input_json_delta":
                        call_id, name = (
                            tool_ids.get(index, (None, None))
                            if isinstance(index, int)
                            else (None, None)
                        )
                        yield ModelStreamEvent(
                            event_type=ModelStreamEventType.TOOL_CALL_DELTA,
                            request_id=request.request_id,
                            provider_id=self.provider_id,
                            model_id=message_model,
                            tool_call_delta=ToolCallDelta(
                                index=index if isinstance(index, int) else 0,
                                call_id=call_id,
                                name_delta=name,
                                arguments_delta=str(delta.get("partial_json", "")),
                            ),
                        )
                elif event_name == "message_delta":
                    delta = item.get("delta")
                    if is_json_object(delta):
                        finish = _anthropic_finish(delta.get("stop_reason"))
                    usage = _anthropic_usage(item.get("usage"))
                    if usage is not None:
                        yield _anthropic_usage_event(
                            request, self.provider_id, message_model, usage
                        )
                elif event_name == "message_stop":
                    yield ModelStreamEvent(
                        event_type=ModelStreamEventType.RESPONSE_COMPLETED,
                        request_id=request.request_id,
                        provider_id=self.provider_id,
                        model_id=message_model,
                        finish_reason=finish or FinishReason.UNKNOWN,
                    )


def parse_anthropic_response(
    payload: Mapping[str, Any],
    request: ModelRequest,
    *,
    provider_id: str,
    provider_request_id: str | None = None,
) -> ModelResponse:
    content = payload.get("content")
    if not isinstance(content, list):
        raise ProviderProtocolError(
            "Anthropic response content was malformed", provider_id=provider_id
        )
    blocks: list[TextContent] = []
    calls: list[ToolCall] = []
    provider_blocks: list[JsonValue] = []
    for item in cast(list[Any], content):
        if not is_json_object(item):
            continue
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            blocks.append(TextContent(text=item["text"]))
        elif item.get("type") == "tool_use":
            call_id = item.get("id")
            name = item.get("name")
            arguments = item.get("input")
            if (
                not isinstance(call_id, str)
                or not isinstance(name, str)
                or not isinstance(arguments, dict)
            ):
                raise ProviderProtocolError(
                    "Anthropic tool-use block was malformed", provider_id=provider_id
                )
            calls.append(
                ToolCall(
                    call_id=call_id,
                    name=name,
                    arguments=cast(dict[str, JsonValue], arguments),
                )
            )
        else:
            # Preserve non-text blocks instead of flattening or discarding them.
            provider_blocks.append(dict(item))
    if not blocks and not calls and not provider_blocks:
        raise ProviderProtocolError(
            "Anthropic returned no supported content blocks", provider_id=provider_id
        )
    extensions: dict[str, dict[str, JsonValue]] = {}
    if provider_blocks:
        extensions["anthropic.messages"] = {"content_blocks": provider_blocks}
    message = Message(
        role=MessageRole.ASSISTANT,
        content=tuple(blocks),
        tool_calls=tuple(calls),
        provider_extensions=extensions,
    )
    model_id = payload.get("model")
    usage = _anthropic_usage(payload.get("usage"))
    return ModelResponse(
        request_id=request.request_id,
        provider_id=provider_id,
        model_id=model_id if isinstance(model_id, str) else request.model_id,
        message=message,
        finish_reason=_anthropic_finish(payload.get("stop_reason")),
        usage=usage,
        provider_request_id=provider_request_id
        or (payload.get("id") if isinstance(payload.get("id"), str) else None),
    )


def _anthropic_usage(value: object) -> TokenUsage | None:
    if not is_json_object(value):
        return None
    input_tokens = value.get("input_tokens")
    output_tokens = value.get("output_tokens")
    if (
        not isinstance(input_tokens, int)
        or isinstance(input_tokens, bool)
        or not isinstance(output_tokens, int)
        or isinstance(output_tokens, bool)
    ):
        return None
    cached = value.get("cache_read_input_tokens", 0)
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cached_input_tokens=cached if isinstance(cached, int) else None,
    )


def _anthropic_usage_event(
    request: ModelRequest, provider_id: str, model_id: str, usage: TokenUsage
) -> ModelStreamEvent:
    return ModelStreamEvent(
        event_type=ModelStreamEventType.USAGE,
        request_id=request.request_id,
        provider_id=provider_id,
        model_id=model_id,
        usage=usage,
    )


def _anthropic_finish(reason: object) -> FinishReason:
    finish_reasons = {
        "end_turn": FinishReason.STOP,
        "stop_sequence": FinishReason.STOP,
        "tool_use": FinishReason.TOOL_CALLS,
        "max_tokens": FinishReason.LENGTH,
        "refusal": FinishReason.REFUSAL,
    }
    return (
        finish_reasons.get(reason, FinishReason.UNKNOWN)
        if isinstance(reason, str)
        else FinishReason.UNKNOWN
    )


def _validation_from_error(provider_id: str, error: ProviderError) -> CredentialValidationResult:
    status = (
        CredentialValidationStatus.INVALID
        if error.code == "provider_authentication_error"
        else CredentialValidationStatus.RESTRICTED
        if error.code == "provider_authorization_error"
        else CredentialValidationStatus.PROVIDER_UNAVAILABLE
        if error.retryable
        else CredentialValidationStatus.UNVERIFIED
    )
    return CredentialValidationResult(provider_id=provider_id, status=status, message=error.message)
