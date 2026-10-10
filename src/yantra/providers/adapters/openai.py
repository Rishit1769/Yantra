"""OpenAI Responses API adapter; Chat Completions is not used for the OpenAI provider."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any, cast

import httpx
from pydantic import JsonValue, SecretStr

from yantra.core.contracts import ProviderCapabilities, TokenUsage, merge_capabilities
from yantra.core.errors import ProviderError, ProviderProtocolError, UnsupportedCapabilityError
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.providers.adapters.common import (
    catalog_entries_from_openai,
    is_json_object,
    iter_sse_data,
    validation_from_error,
)
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


class OpenAIAdapter(HttpxProvider):
    """OpenAI adapter using `/v1/responses` and the official Responses item format."""

    _allowed_options = frozenset(
        {"reasoning", "service_tier", "store", "include", "parallel_tool_calls", "prompt_cache_key"}
    )

    def __init__(
        self,
        *,
        provider_id: str = "openai",
        credential_reference: str | None = "env://OPENAI_API_KEY",
        credential_manager: CredentialManager | None = None,
        base_url: str = "https://api.openai.com/v1",
        trusted_hosts: frozenset[str] = frozenset({"api.openai.com"}),
        client: httpx.AsyncClient | None = None,
        capability_overrides: Mapping[str, ProviderCapabilities] | None = None,
        max_response_bytes: int = 16 * 1024 * 1024,
        session_header_name: str | None = None,
    ) -> None:
        super().__init__(
            provider_id,
            base_url,
            credential_reference=credential_reference,
            credential_manager=credential_manager,
            trusted_hosts=trusted_hosts,
            client=client,
            max_response_bytes=max_response_bytes,
            session_header_name=session_header_name,
        )
        self._capability_overrides = dict(capability_overrides or {})

    def _headers(
        self, request: ModelRequest | None = None, secret: SecretStr | None = None
    ) -> dict[str, str]:
        return {
            **self.request_headers(request),
            "Content-Type": "application/json",
            **self.auth_headers(secret_override=secret),
        }

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True, token_usage=True)

    def capabilities_for(self, model_id: str) -> ProviderCapabilities:
        return merge_capabilities(self.capabilities, self._capability_overrides.get(model_id))

    async def list_models(
        self, *, secret: SecretStr | None = None
    ) -> tuple[ModelCatalogEntry, ...]:
        payload, _ = await self.request_json("GET", "models", headers=self._headers(secret=secret))
        entries = catalog_entries_from_openai(payload, provider_id=self.provider_id)
        return tuple(
            entry.model_copy(update={"capabilities": self.capabilities_for(entry.model_id)})
            for entry in entries
        )

    async def validate_credentials(self, secret: SecretStr | None) -> CredentialValidationResult:
        if secret is None:
            return CredentialValidationResult(
                provider_id=self.provider_id,
                status=CredentialValidationStatus.UNVERIFIED,
                message="a credential was not supplied for validation",
            )
        try:
            models = await self.list_models(secret=secret)
        except ProviderError as exc:
            return validation_from_error(self.provider_id, exc)
        return CredentialValidationResult(
            provider_id=self.provider_id,
            status=CredentialValidationStatus.VALID,
            message="Authenticated model listing succeeded; inference access is model-specific",
            catalog_model_count=len(models),
        )

    def build_payload(self, request: ModelRequest) -> dict[str, Any]:
        if request.generation.stop_sequences:
            raise UnsupportedCapabilityError(
                "stop_sequences are not translated by the OpenAI Responses adapter",
                provider_id=self.provider_id,
            )
        payload: dict[str, Any] = {
            "model": request.model_id,
            "input": _responses_input(request.messages),
        }
        settings = request.generation
        if settings.max_output_tokens is not None:
            payload["max_output_tokens"] = settings.max_output_tokens
        if settings.temperature is not None:
            payload["temperature"] = settings.temperature
        if settings.top_p is not None:
            payload["top_p"] = settings.top_p
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "strict": True,
                }
                for tool in request.tools
            ]
        if request.response_schema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "yantra_response",
                    "strict": True,
                    "schema": request.response_schema,
                }
            }
        for name, value in request.provider_options.items():
            if name not in self._allowed_options:
                raise UnsupportedCapabilityError(
                    f"OpenAI Responses option {name!r} is not supported by this adapter",
                    provider_id=self.provider_id,
                )
            payload[name] = value
        return payload

    async def complete(self, request: ModelRequest) -> ModelResponse:
        result, headers = await self.request_json(
            "POST",
            "responses",
            headers=self._headers(request=request),
            json_body=self.build_payload(request),
            timeout_seconds=request.timeout_seconds,
        )
        return parse_responses_result(
            result,
            request,
            provider_id=self.provider_id,
            provider_request_id=headers.get("x-request-id"),
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        payload = self.build_payload(request)
        payload["stream"] = True
        async with self.stream_response(
            "POST",
            "responses",
            headers=self._headers(request=request),
            json_body=payload,
            timeout_seconds=request.timeout_seconds,
        ) as response:
            yield ModelStreamEvent(
                event_type=ModelStreamEventType.RESPONSE_STARTED,
                request_id=request.request_id,
                provider_id=self.provider_id,
                model_id=request.model_id,
            )
            tool_items: dict[str, ToolCallDelta] = {}
            completed = False
            async for data in iter_sse_data(response, max_stream_bytes=self._max_response_bytes):
                if data == "[DONE]":
                    continue
                try:
                    event = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise ProviderProtocolError(
                        "OpenAI Responses stream contained invalid JSON",
                        provider_id=self.provider_id,
                    ) from exc
                if not is_json_object(event):
                    raise ProviderProtocolError(
                        "OpenAI Responses stream event was malformed", provider_id=self.provider_id
                    )
                event_type = event.get("type")
                if event_type == "response.output_text.delta":
                    delta = event.get("delta")
                    if isinstance(delta, str):
                        yield ModelStreamEvent(
                            event_type=ModelStreamEventType.TEXT_DELTA,
                            request_id=request.request_id,
                            provider_id=self.provider_id,
                            model_id=request.model_id,
                            text_delta=delta,
                        )
                elif event_type == "response.output_item.added":
                    item = event.get("item")
                    if is_json_object(item) and item.get("type") == "function_call":
                        call_id = item.get("call_id")
                        item_id = item.get("id")
                        key = str(item_id or call_id or len(tool_items))
                        delta = ToolCallDelta(
                            index=len(tool_items),
                            call_id=call_id if isinstance(call_id, str) else None,
                            name_delta=item.get("name")
                            if isinstance(item.get("name"), str)
                            else None,
                        )
                        tool_items[key] = delta
                        yield ModelStreamEvent(
                            event_type=ModelStreamEventType.TOOL_CALL_DELTA,
                            request_id=request.request_id,
                            provider_id=self.provider_id,
                            model_id=request.model_id,
                            tool_call_delta=delta,
                        )
                elif event_type == "response.function_call_arguments.delta":
                    delta_text = event.get("delta")
                    item_id = event.get("item_id")
                    if isinstance(delta_text, str):
                        prior = tool_items.get(str(item_id))
                        index = prior.index if prior is not None else len(tool_items)
                        yield ModelStreamEvent(
                            event_type=ModelStreamEventType.TOOL_CALL_DELTA,
                            request_id=request.request_id,
                            provider_id=self.provider_id,
                            model_id=request.model_id,
                            tool_call_delta=ToolCallDelta(index=index, arguments_delta=delta_text),
                        )
                elif event_type == "response.completed":
                    response_value = event.get("response")
                    usage = None
                    finish = FinishReason.UNKNOWN
                    if is_json_object(response_value):
                        usage = _responses_usage(response_value.get("usage"), self.provider_id)
                        finish = _responses_finish(response_value)
                    if usage is not None:
                        yield ModelStreamEvent(
                            event_type=ModelStreamEventType.USAGE,
                            request_id=request.request_id,
                            provider_id=self.provider_id,
                            model_id=request.model_id,
                            usage=usage,
                        )
                    yield ModelStreamEvent(
                        event_type=ModelStreamEventType.RESPONSE_COMPLETED,
                        request_id=request.request_id,
                        provider_id=self.provider_id,
                        model_id=request.model_id,
                        finish_reason=finish,
                        usage=usage,
                    )
                    completed = True
                elif event_type in {"response.failed", "error"}:
                    raise ProviderError(
                        "OpenAI Responses stream failed",
                        provider_id=self.provider_id,
                    )
            if not completed:
                raise ProviderProtocolError(
                    "OpenAI Responses stream ended without a completed response",
                    provider_id=self.provider_id,
                )


def _responses_input(messages: tuple[Message, ...]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for message in messages:
        if message.role == MessageRole.TOOL:
            result = message.tool_result
            if result is None:
                raise ProviderProtocolError("tool result message is missing its result")
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": result.call_id,
                    "output": json.dumps(result.result, separators=(",", ":"), ensure_ascii=False),
                }
            )
            continue
        if message.tool_calls:
            for call in message.tool_calls:
                items.append(
                    {
                        "type": "function_call",
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, separators=(",", ":")),
                    }
                )
        if message.content:
            content = [{"type": "input_text", "text": part.text} for part in message.content]
            items.append(
                {
                    "type": "message",
                    "role": message.role.value,
                    "content": content,
                }
            )
    return items


def parse_responses_result(
    value: Mapping[str, Any],
    request: ModelRequest,
    *,
    provider_id: str,
    provider_request_id: str | None = None,
) -> ModelResponse:
    if value.get("status") == "failed":
        raise ProviderError("OpenAI Responses request failed", provider_id=provider_id)
    output = value.get("output")
    if not isinstance(output, list):
        raise ProviderProtocolError(
            "OpenAI Responses output was malformed", provider_id=provider_id
        )
    blocks: list[TextContent] = []
    calls: list[ToolCall] = []
    refusal_seen = False
    for item in cast(list[Any], output):
        if not is_json_object(item):
            continue
        if item.get("type") == "message":
            contents = item.get("content", [])
            if not isinstance(contents, list):
                raise ProviderProtocolError(
                    "OpenAI Responses message content was malformed", provider_id=provider_id
                )
            for content in cast(list[Any], contents):
                if not is_json_object(content):
                    continue
                if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                    blocks.append(TextContent(text=content["text"]))
                elif content.get("type") == "refusal":
                    refusal_seen = True
                    if isinstance(content.get("refusal"), str):
                        blocks.append(TextContent(text=content["refusal"]))
        elif item.get("type") == "function_call":
            raw_args = item.get("arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError as exc:
                raise ProviderProtocolError(
                    "OpenAI function arguments were invalid JSON", provider_id=provider_id
                ) from exc
            call_id = item.get("call_id")
            name = item.get("name")
            if (
                not isinstance(call_id, str)
                or not isinstance(name, str)
                or not isinstance(args, dict)
            ):
                raise ProviderProtocolError(
                    "OpenAI function call was malformed", provider_id=provider_id
                )
            calls.append(
                ToolCall(
                    call_id=call_id,
                    name=name,
                    arguments=cast(dict[str, JsonValue], args),
                )
            )
    if not blocks and not calls:
        raise ProviderProtocolError(
            "OpenAI Responses returned no supported output items", provider_id=provider_id
        )
    usage = _responses_usage(value.get("usage"), provider_id)
    return ModelResponse(
        request_id=request.request_id,
        provider_id=provider_id,
        model_id=str(value.get("model") or request.model_id),
        message=Message(role=MessageRole.ASSISTANT, content=tuple(blocks), tool_calls=tuple(calls)),
        finish_reason=(
            FinishReason.REFUSAL
            if refusal_seen
            else FinishReason.TOOL_CALLS
            if calls
            else _responses_finish(value)
        ),
        usage=usage,
        provider_request_id=provider_request_id
        or (value.get("id") if isinstance(value.get("id"), str) else None),
        metadata={"status": value.get("status", "unknown")},
    )


def _responses_usage(value: object, provider_id: str) -> TokenUsage | None:
    if value is None:
        return None
    if not is_json_object(value):
        raise ProviderProtocolError("OpenAI Responses usage was malformed", provider_id=provider_id)
    input_tokens = value.get("input_tokens")
    output_tokens = value.get("output_tokens")
    total_tokens = value.get("total_tokens")
    if (
        not isinstance(input_tokens, int)
        or isinstance(input_tokens, bool)
        or not isinstance(output_tokens, int)
        or isinstance(output_tokens, bool)
        or not isinstance(total_tokens, int)
        or isinstance(total_tokens, bool)
    ):
        return None
    cached = None
    details = value.get("input_tokens_details")
    if is_json_object(details) and isinstance(details.get("cached_tokens"), int):
        cached = details["cached_tokens"]
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_input_tokens=cached,
    )


def _responses_finish(value: Mapping[str, Any]) -> FinishReason:
    if value.get("status") == "incomplete":
        details = value.get("incomplete_details")
        if is_json_object(details) and details.get("reason") == "max_output_tokens":
            return FinishReason.LENGTH
    return FinishReason.STOP
