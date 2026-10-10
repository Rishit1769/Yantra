"""Local Ollama API adapter; never installs or downloads models."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any, cast

import httpx
from pydantic import JsonValue, SecretStr

from yantra.core.contracts import ProviderCapabilities, TokenUsage
from yantra.core.errors import (
    ProviderError,
    ProviderInvalidRequestError,
    ProviderProtocolError,
    UnsupportedCapabilityError,
)
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.providers.adapters.common import chat_tools, is_json_object
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


class OllamaAdapter(HttpxProvider):
    """Adapter for an explicitly configured local Ollama server."""

    _allowed_options = frozenset(
        {
            "seed",
            "top_k",
            "min_p",
            "num_ctx",
            "num_predict",
            "think",
            "keep_alive",
            "logprobs",
            "top_logprobs",
        }
    )

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        client: httpx.AsyncClient | None = None,
        capability_overrides: Mapping[str, ProviderCapabilities] | None = None,
    ) -> None:
        super().__init__(
            "ollama",
            base_url,
            credential_reference=None,
            trusted_hosts=frozenset({"localhost", "127.0.0.1", "::1"}),
            client=client,
        )
        self._capability_overrides = dict(capability_overrides or {})
        self._discovered_capabilities: dict[str, ProviderCapabilities] = {}

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True, cancellation=True)

    def capabilities_for(self, model_id: str) -> ProviderCapabilities:
        return self._capability_overrides.get(
            model_id,
            self._discovered_capabilities.get(model_id, self.capabilities),
        )

    async def list_models(self) -> tuple[ModelCatalogEntry, ...]:
        payload, _ = await self.request_json("GET", "api/tags", timeout_seconds=5.0)
        models = payload.get("models")
        if not isinstance(models, list):
            raise ProviderProtocolError(
                "Ollama tags response was malformed", provider_id=self.provider_id
            )
        model_records = cast(list[Any], models)
        if len(model_records) > 500:
            raise ProviderProtocolError(
                "Ollama model catalog exceeds 500 entries", provider_id=self.provider_id
            )
        entries: list[ModelCatalogEntry] = []
        for item in model_records:
            if not is_json_object(item) or not isinstance(item.get("name"), str):
                continue
            model_id = item["name"]
            capabilities, details = await self._show_model(model_id)
            self._discovered_capabilities[model_id] = capabilities
            details_value = item.get("details")
            raw_details: Mapping[str, Any] = details_value if is_json_object(details_value) else {}
            entries.append(
                ModelCatalogEntry(
                    provider_id=self.provider_id,
                    model_id=model_id,
                    display_name=model_id,
                    capabilities=capabilities,
                    is_local=True,
                    metadata={
                        "digest": item.get("digest", "unknown"),
                        "size_bytes": item.get("size") if isinstance(item.get("size"), int) else 0,
                        "family": raw_details.get("family", "unknown"),
                        "show_capabilities": list(details),
                    },
                )
            )
        return tuple(entries)

    async def _show_model(self, model_id: str) -> tuple[ProviderCapabilities, tuple[str, ...]]:
        try:
            payload, _ = await self.request_json(
                "POST", "api/show", json_body={"model": model_id}, timeout_seconds=5.0
            )
        except ProviderError:
            return self._capability_overrides.get(model_id, ProviderCapabilities()), ()
        raw = payload.get("capabilities")
        raw_capabilities = cast(list[Any], raw) if isinstance(raw, list) else []
        capabilities = tuple(item for item in raw_capabilities if isinstance(item, str))
        model_info = payload.get("model_info")
        context_window = (
            model_info.get("llama.context_length") if is_json_object(model_info) else None
        )
        if not isinstance(context_window, int) or isinstance(context_window, bool):
            context_window = None
        declared = ProviderCapabilities(
            tool_calling=True if "tools" in capabilities else False if raw is not None else None,
            streaming=True,
            cancellation=True,
            context_window_tokens=context_window,
        )
        override = self._capability_overrides.get(model_id)
        if override is not None:
            declared = _merge_capabilities(override, declared)
        return declared, capabilities

    async def validate_credentials(
        self, secret: SecretStr | None = None
    ) -> CredentialValidationResult:
        if secret is not None:
            return CredentialValidationResult(
                provider_id=self.provider_id,
                status=CredentialValidationStatus.INVALID,
                message="standard local Ollama does not use cloud credentials",
            )
        try:
            models = await self.list_models()
        except ProviderError as exc:
            status = (
                CredentialValidationStatus.PROVIDER_UNAVAILABLE
                if exc.retryable
                else CredentialValidationStatus.UNVERIFIED
            )
            return CredentialValidationResult(
                provider_id=self.provider_id,
                status=status,
                message=exc.message,
            )
        return CredentialValidationResult(
            provider_id=self.provider_id,
            status=CredentialValidationStatus.NOT_REQUIRED,
            message="local Ollama is reachable; no API key is required",
            catalog_model_count=len(models),
        )

    def build_payload(self, request: ModelRequest, *, stream: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model_id,
            "messages": _ollama_messages(request.messages, self.provider_id),
            "stream": stream,
        }
        options: dict[str, Any] = {}
        if request.generation.temperature is not None:
            options["temperature"] = request.generation.temperature
        if request.generation.top_p is not None:
            options["top_p"] = request.generation.top_p
        if request.generation.max_output_tokens is not None:
            options["num_predict"] = request.generation.max_output_tokens
        if request.generation.stop_sequences:
            options["stop"] = list(request.generation.stop_sequences)
        for name, value in request.provider_options.items():
            if name not in self._allowed_options:
                raise UnsupportedCapabilityError(
                    f"Ollama option {name!r} is not supported by this adapter",
                    provider_id=self.provider_id,
                )
            options[name] = value
        if options:
            payload["options"] = options
        if request.tools:
            payload["tools"] = chat_tools(request)
        if request.response_schema is not None:
            payload["format"] = request.response_schema
        return payload

    async def complete(self, request: ModelRequest) -> ModelResponse:
        payload, _ = await self.request_json(
            "POST",
            "api/chat",
            headers=self.request_headers(request),
            json_body=self.build_payload(request),
            timeout_seconds=request.timeout_seconds,
        )
        return parse_ollama_response(payload, request)

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        total_bytes = 0
        async with self.stream_response(
            "POST",
            "api/chat",
            headers=self.request_headers(request),
            json_body=self.build_payload(request, stream=True),
            timeout_seconds=request.timeout_seconds,
        ) as response:
            yield ModelStreamEvent(
                event_type=ModelStreamEventType.RESPONSE_STARTED,
                request_id=request.request_id,
                provider_id=self.provider_id,
                model_id=request.model_id,
            )
            async for line in response.aiter_lines():
                total_bytes += len(line.encode("utf-8")) + 1
                if total_bytes > self._max_response_bytes:
                    raise ProviderProtocolError(
                        "Ollama stream exceeded configured size limit", provider_id=self.provider_id
                    )
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ProviderProtocolError(
                        "Ollama stream line was invalid JSON", provider_id=self.provider_id
                    ) from exc
                if not is_json_object(payload):
                    raise ProviderProtocolError(
                        "Ollama stream event was malformed", provider_id=self.provider_id
                    )
                message = payload.get("message")
                if is_json_object(message):
                    text = message.get("content")
                    if isinstance(text, str) and text:
                        yield ModelStreamEvent(
                            event_type=ModelStreamEventType.TEXT_DELTA,
                            request_id=request.request_id,
                            provider_id=self.provider_id,
                            model_id=str(payload.get("model") or request.model_id),
                            text_delta=text,
                        )
                    for index, tool_call in enumerate(message.get("tool_calls") or []):
                        if not is_json_object(tool_call):
                            continue
                        function = tool_call.get("function")
                        if is_json_object(function):
                            yield ModelStreamEvent(
                                event_type=ModelStreamEventType.TOOL_CALL_DELTA,
                                request_id=request.request_id,
                                provider_id=self.provider_id,
                                model_id=str(payload.get("model") or request.model_id),
                                tool_call_delta=ToolCallDelta(
                                    index=index,
                                    name_delta=function.get("name")
                                    if isinstance(function.get("name"), str)
                                    else None,
                                    arguments_delta=json.dumps(
                                        function.get("arguments", {}), separators=(",", ":")
                                    ),
                                ),
                            )
                usage = _ollama_usage(payload)
                if usage is not None:
                    yield ModelStreamEvent(
                        event_type=ModelStreamEventType.USAGE,
                        request_id=request.request_id,
                        provider_id=self.provider_id,
                        model_id=str(payload.get("model") or request.model_id),
                        usage=usage,
                    )
                if payload.get("done") is True:
                    yield ModelStreamEvent(
                        event_type=ModelStreamEventType.RESPONSE_COMPLETED,
                        request_id=request.request_id,
                        provider_id=self.provider_id,
                        model_id=str(payload.get("model") or request.model_id),
                        finish_reason=_ollama_finish(payload.get("done_reason")),
                        usage=usage,
                    )


def _ollama_messages(messages: tuple[Message, ...], provider_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in messages:
        if message.role == MessageRole.TOOL:
            tool_result = message.tool_result
            if tool_result is None:
                raise ProviderInvalidRequestError(
                    "Ollama tool message has no result", provider_id=provider_id
                )
            result.append(
                {
                    "role": "tool",
                    "tool_name": tool_result.name,
                    "content": json.dumps(
                        tool_result.result, separators=(",", ":"), ensure_ascii=False
                    ),
                }
            )
            continue
        item: dict[str, Any] = {
            "role": message.role.value,
            "content": "".join(part.text for part in message.content),
        }
        if message.tool_calls:
            item["tool_calls"] = [
                {"function": {"name": call.name, "arguments": call.arguments}}
                for call in message.tool_calls
            ]
        result.append(item)
    return result


def parse_ollama_response(payload: Mapping[str, Any], request: ModelRequest) -> ModelResponse:
    message = payload.get("message")
    if not is_json_object(message):
        raise ProviderProtocolError(
            "Ollama response did not contain a message", provider_id="ollama"
        )
    content = message.get("content")
    blocks = (TextContent(text=content),) if isinstance(content, str) and content else ()
    tool_calls: list[ToolCall] = []
    calls_value = message.get("tool_calls")
    if calls_value is None:
        calls_value = []
    if not isinstance(calls_value, list):
        raise ProviderProtocolError("Ollama tool calls were malformed", provider_id="ollama")
    for index, call in enumerate(cast(list[Any], calls_value)):
        if not is_json_object(call) or not is_json_object(call.get("function")):
            raise ProviderProtocolError("Ollama tool call was malformed", provider_id="ollama")
        function = call["function"]
        name = function.get("name")
        arguments = function.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise ProviderProtocolError("Ollama function call was malformed", provider_id="ollama")
        tool_calls.append(
            ToolCall(
                call_id=f"{request.request_id}-{index}",
                name=name,
                arguments=cast(dict[str, JsonValue], arguments),
            )
        )
    if not blocks and not tool_calls:
        raise ProviderProtocolError("Ollama returned no text or tool call", provider_id="ollama")
    return ModelResponse(
        request_id=request.request_id,
        provider_id="ollama",
        model_id=str(payload.get("model") or request.model_id),
        message=Message(role=MessageRole.ASSISTANT, content=blocks, tool_calls=tuple(tool_calls)),
        finish_reason=_ollama_finish(payload.get("done_reason")),
        usage=_ollama_usage(payload),
        metadata={
            key: payload[key]
            for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration")
            if isinstance(payload.get(key), int)
        },
    )


def _ollama_usage(payload: Mapping[str, Any]) -> TokenUsage | None:
    prompt = payload.get("prompt_eval_count")
    output = payload.get("eval_count")
    if not isinstance(prompt, int) or not isinstance(output, int):
        return None
    return TokenUsage(input_tokens=prompt, output_tokens=output, total_tokens=prompt + output)


def _ollama_finish(value: object) -> FinishReason:
    if value in (None, "stop"):
        return FinishReason.STOP
    if value == "length":
        return FinishReason.LENGTH
    return FinishReason.UNKNOWN


def _merge_capabilities(
    override: ProviderCapabilities, discovered: ProviderCapabilities
) -> ProviderCapabilities:
    return ProviderCapabilities(
        tool_calling=(
            discovered.tool_calling if override.tool_calling is None else override.tool_calling
        ),
        structured_output=(
            discovered.structured_output
            if override.structured_output is None
            else override.structured_output
        ),
        streaming=(discovered.streaming if override.streaming is None else override.streaming),
        token_usage=(
            discovered.token_usage if override.token_usage is None else override.token_usage
        ),
        cancellation=(
            discovered.cancellation if override.cancellation is None else override.cancellation
        ),
        context_window_tokens=override.context_window_tokens or discovered.context_window_tokens,
    )
