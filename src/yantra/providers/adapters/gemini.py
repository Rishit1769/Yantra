"""Google Gemini generateContent REST adapter."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any, cast
from urllib.parse import quote

import httpx
from pydantic import JsonValue, SecretStr

from yantra.core.contracts import ProviderCapabilities, TokenUsage, merge_capabilities
from yantra.core.errors import (
    ProviderError,
    ProviderInvalidRequestError,
    ProviderProtocolError,
    UnsupportedCapabilityError,
)
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


class GeminiAdapter(HttpxProvider):
    """Gemini REST adapter using generateContent and streamGenerateContent endpoints."""

    _allowed_options = frozenset(
        {"candidateCount", "topK", "safetySettings", "thinkingConfig", "toolConfig"}
    )

    def __init__(
        self,
        *,
        provider_id: str = "gemini",
        credential_reference: str | None = "env://GEMINI_API_KEY",
        credential_manager: CredentialManager | None = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        trusted_hosts: frozenset[str] = frozenset({"generativelanguage.googleapis.com"}),
        credential_header: str = "x-goog-api-key",
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
        self, secret: SecretStr | None = None, request: ModelRequest | None = None
    ) -> dict[str, str]:
        if secret is None:
            secret = self._credential_override.get()
        if secret is None and self.credential_reference is None:
            raise ProviderError(
                "Gemini API key reference is not configured", provider_id=self.provider_id
            )
        headers = {**self.request_headers(request), "Content-Type": "application/json"}
        if secret is not None:
            headers[self._credential_header] = (
                f"{self._credential_scheme} {secret.get_secret_value()}".strip()
            )
        elif self.credential_reference is not None:
            value = self.credential_manager.resolve(self.credential_reference).get_secret_value()
            headers[self._credential_header] = f"{self._credential_scheme} {value}".strip()
        return headers

    async def list_models(
        self, *, secret: SecretStr | None = None
    ) -> tuple[ModelCatalogEntry, ...]:
        entries: list[ModelCatalogEntry] = []
        page_token: str | None = None
        for _ in range(20):
            params = {"pageSize": "1000"}
            if page_token:
                params["pageToken"] = page_token
            payload, _ = await self.request_json(
                "GET", "models", headers=self._headers(secret), params=params
            )
            models = payload.get("models")
            if not isinstance(models, list):
                raise ProviderProtocolError(
                    "Gemini model catalog was malformed", provider_id=self.provider_id
                )
            for item in cast(list[Any], models):
                if not is_json_object(item) or not isinstance(item.get("name"), str):
                    continue
                full_name = item["name"]
                model_id = full_name.removeprefix("models/")
                methods = item.get("supportedGenerationMethods")
                entries.append(
                    ModelCatalogEntry(
                        provider_id=self.provider_id,
                        model_id=model_id,
                        display_name=item.get("displayName")
                        if isinstance(item.get("displayName"), str)
                        else model_id,
                        capabilities=self.capabilities_for(model_id),
                        context_window_tokens=_positive_int(item.get("inputTokenLimit")),
                        max_output_tokens=_positive_int(item.get("outputTokenLimit")),
                        metadata={
                            "supported_generation_methods": methods
                            if isinstance(methods, list)
                            else [],
                            "catalog_capabilities_unknown": True,
                        },
                    )
                )
            next_token = payload.get("nextPageToken")
            if not isinstance(next_token, str) or not next_token:
                break
            if next_token == page_token:
                raise ProviderProtocolError(
                    "Gemini model catalog cursor repeated", provider_id=self.provider_id
                )
            page_token = next_token
        else:
            raise ProviderProtocolError(
                "Gemini model catalog exceeded pagination limit", provider_id=self.provider_id
            )
        return tuple(entries)

    async def validate_credentials(self, secret: SecretStr | None) -> CredentialValidationResult:
        if secret is None:
            return CredentialValidationResult(
                provider_id=self.provider_id,
                status=CredentialValidationStatus.UNVERIFIED,
                message="Gemini API key was not supplied",
            )
        try:
            models = await self.list_models(secret=secret)
        except ProviderError as exc:
            return _validation_from_error(self.provider_id, exc)
        return CredentialValidationResult(
            provider_id=self.provider_id,
            status=CredentialValidationStatus.VALID,
            message="Authenticated model listing succeeded; inference access is model-specific",
            catalog_model_count=len(models),
        )

    def build_payload(self, request: ModelRequest) -> dict[str, Any]:
        system, contents = _gemini_contents(request.messages, self.provider_id)
        payload: dict[str, Any] = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        generation: dict[str, Any] = {}
        if request.generation.temperature is not None:
            generation["temperature"] = request.generation.temperature
        if request.generation.top_p is not None:
            generation["topP"] = request.generation.top_p
        if request.generation.max_output_tokens is not None:
            generation["maxOutputTokens"] = request.generation.max_output_tokens
        if request.generation.stop_sequences:
            generation["stopSequences"] = list(request.generation.stop_sequences)
        if request.response_schema is not None:
            generation["responseMimeType"] = "application/json"
            generation["responseSchema"] = request.response_schema
        for key, value in request.provider_options.items():
            if key not in self._allowed_options:
                raise UnsupportedCapabilityError(
                    f"Gemini option {key!r} is not supported by this adapter",
                    provider_id=self.provider_id,
                )
            payload[key] = value
        if generation:
            payload["generationConfig"] = generation
        if request.tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters,
                        }
                        for tool in request.tools
                    ]
                }
            ]
        return payload

    async def complete(self, request: ModelRequest) -> ModelResponse:
        model_path = quote(request.model_id, safe="-._~")
        payload, headers = await self.request_json(
            "POST",
            f"models/{model_path}:generateContent",
            headers=self._headers(request=request),
            json_body=self.build_payload(request),
            timeout_seconds=request.timeout_seconds,
        )
        return parse_gemini_response(
            payload,
            request,
            provider_id=self.provider_id,
            provider_request_id=headers.get("x-request-id"),
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        model_path = quote(request.model_id, safe="-._~")
        async with self.stream_response(
            "POST",
            f"models/{model_path}:streamGenerateContent",
            headers=self._headers(request=request),
            params={"alt": "sse"},
            json_body=self.build_payload(request),
            timeout_seconds=request.timeout_seconds,
        ) as response:
            yield ModelStreamEvent(
                event_type=ModelStreamEventType.RESPONSE_STARTED,
                request_id=request.request_id,
                provider_id=self.provider_id,
                model_id=request.model_id,
            )
            completed = False
            async for data in iter_sse_data(response, max_stream_bytes=self._max_response_bytes):
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise ProviderProtocolError(
                        "Gemini stream event was invalid JSON", provider_id=self.provider_id
                    ) from exc
                if not is_json_object(payload):
                    raise ProviderProtocolError(
                        "Gemini stream event was malformed", provider_id=self.provider_id
                    )
                candidate = _first_candidate(payload, self.provider_id)
                content = candidate.get("content")
                parts = content.get("parts") if is_json_object(content) else None
                if isinstance(parts, list):
                    for index, part in enumerate(cast(list[Any], parts)):
                        if not is_json_object(part):
                            continue
                        if isinstance(part.get("text"), str):
                            event_type = (
                                ModelStreamEventType.REASONING_DELTA
                                if part.get("thought") is True
                                else ModelStreamEventType.TEXT_DELTA
                            )
                            yield ModelStreamEvent(
                                event_type=event_type,
                                request_id=request.request_id,
                                provider_id=self.provider_id,
                                model_id=request.model_id,
                                text_delta=part["text"],
                            )
                        function = part.get("functionCall")
                        if is_json_object(function):
                            call_id = function.get("id")
                            name = function.get("name")
                            args = function.get("args", {})
                            yield ModelStreamEvent(
                                event_type=ModelStreamEventType.TOOL_CALL_DELTA,
                                request_id=request.request_id,
                                provider_id=self.provider_id,
                                model_id=request.model_id,
                                tool_call_delta=ToolCallDelta(
                                    index=index,
                                    call_id=call_id if isinstance(call_id, str) else None,
                                    name_delta=name if isinstance(name, str) else None,
                                    arguments_delta=json.dumps(args, separators=(",", ":")),
                                ),
                            )
                usage = _gemini_usage(payload.get("usageMetadata"), self.provider_id)
                if usage is not None:
                    yield ModelStreamEvent(
                        event_type=ModelStreamEventType.USAGE,
                        request_id=request.request_id,
                        provider_id=self.provider_id,
                        model_id=request.model_id,
                        usage=usage,
                    )
                finish = _gemini_finish(candidate.get("finishReason"))
                if finish is not None:
                    yield ModelStreamEvent(
                        event_type=ModelStreamEventType.RESPONSE_COMPLETED,
                        request_id=request.request_id,
                        provider_id=self.provider_id,
                        model_id=request.model_id,
                        finish_reason=finish,
                        usage=usage,
                    )
                    completed = True
            if not completed:
                raise ProviderProtocolError(
                    "Gemini stream ended without a finish reason", provider_id=self.provider_id
                )


def _gemini_contents(
    messages: tuple[Message, ...], provider_id: str
) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    conversation_started = False
    for message in messages:
        if message.role in (MessageRole.SYSTEM, MessageRole.DEVELOPER):
            if conversation_started:
                raise ProviderInvalidRequestError(
                    "Gemini system instructions must precede conversation turns",
                    provider_id=provider_id,
                )
            system_parts.extend(part.text for part in message.content)
            continue
        conversation_started = True
        if message.role == MessageRole.TOOL:
            result = message.tool_result
            if result is None:
                raise ProviderInvalidRequestError(
                    "Gemini tool result message is incomplete", provider_id=provider_id
                )
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                "id": result.call_id,
                                "name": result.name,
                                "response": {"result": result.result, "is_error": result.is_error},
                            }
                        }
                    ],
                }
            )
            continue
        role = "model" if message.role == MessageRole.ASSISTANT else "user"
        parts: list[dict[str, Any]] = [{"text": part.text} for part in message.content]
        if message.role == MessageRole.ASSISTANT:
            parts.extend(
                {"functionCall": {"id": call.call_id, "name": call.name, "args": call.arguments}}
                for call in message.tool_calls
            )
        contents.append({"role": role, "parts": parts})
    return "\n".join(system_parts), contents


def parse_gemini_response(
    payload: Mapping[str, Any],
    request: ModelRequest,
    *,
    provider_id: str,
    provider_request_id: str | None = None,
) -> ModelResponse:
    candidate = _first_candidate(payload, provider_id)
    content = candidate.get("content")
    parts = content.get("parts") if is_json_object(content) else None
    if not isinstance(parts, list):
        raise ProviderProtocolError(
            "Gemini response content was malformed", provider_id=provider_id
        )
    blocks: list[TextContent] = []
    calls: list[ToolCall] = []
    thought_parts: list[JsonValue] = []
    for index, part in enumerate(cast(list[Any], parts)):
        if not is_json_object(part):
            continue
        if isinstance(part.get("text"), str):
            if part.get("thought") is True:
                thought_parts.append(
                    {
                        "text": part["text"],
                        "thought_signature": part.get("thoughtSignature"),
                    }
                )
            else:
                blocks.append(TextContent(text=part["text"]))
        function = part.get("functionCall")
        if is_json_object(function):
            name = function.get("name")
            arguments = function.get("args", {})
            call_id = function.get("id")
            if not isinstance(name, str) or not isinstance(arguments, dict):
                raise ProviderProtocolError(
                    "Gemini function call was malformed", provider_id=provider_id
                )
            if not isinstance(call_id, str) or not call_id:
                call_id = f"{request.request_id}-{index}"
            calls.append(
                ToolCall(
                    call_id=call_id,
                    name=name,
                    arguments=cast(dict[str, JsonValue], arguments),
                )
            )
    if not blocks and not calls:
        raise ProviderProtocolError(
            "Gemini response contained no text or function call", provider_id=provider_id
        )
    usage = _gemini_usage(payload.get("usageMetadata"), provider_id)
    actual_model = payload.get("modelVersion")
    provider_extensions: dict[str, dict[str, JsonValue]] = {}
    if thought_parts:
        provider_extensions["google.gemini"] = {"thought_parts": thought_parts}
    return ModelResponse(
        request_id=request.request_id,
        provider_id=provider_id,
        model_id=actual_model if isinstance(actual_model, str) else request.model_id,
        message=Message(
            role=MessageRole.ASSISTANT,
            content=tuple(blocks),
            tool_calls=tuple(calls),
            provider_extensions=provider_extensions,
        ),
        finish_reason=_gemini_finish(candidate.get("finishReason")) or FinishReason.UNKNOWN,
        usage=usage,
        provider_request_id=provider_request_id,
        metadata={
            "safety_ratings": cast(
                JsonValue,
                payload.get("promptFeedback", {}).get("safetyRatings", [])
                if is_json_object(payload.get("promptFeedback"))
                else [],
            )
        },
    )


def _first_candidate(payload: Mapping[str, Any], provider_id: str) -> Mapping[str, Any]:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ProviderProtocolError(
            "Gemini response contained no candidate", provider_id=provider_id
        )
    candidate_list = cast(list[Any], candidates)
    if not candidate_list or not is_json_object(candidate_list[0]):
        raise ProviderProtocolError(
            "Gemini response contained no candidate", provider_id=provider_id
        )
    return candidate_list[0]


def _gemini_usage(value: object, provider_id: str) -> TokenUsage | None:
    if not is_json_object(value):
        return None
    prompt = value.get("promptTokenCount")
    output = value.get("candidatesTokenCount")
    total = value.get("totalTokenCount")
    if (
        not isinstance(prompt, int)
        or isinstance(prompt, bool)
        or not isinstance(output, int)
        or isinstance(output, bool)
    ):
        return None
    if not isinstance(total, int) or isinstance(total, bool):
        total = prompt + output
    cached = value.get("cachedContentTokenCount")
    try:
        return TokenUsage(
            input_tokens=prompt,
            output_tokens=output,
            total_tokens=total,
            cached_input_tokens=cached if isinstance(cached, int) else None,
        )
    except ValueError as exc:
        raise ProviderProtocolError(
            "Gemini usage totals were inconsistent", provider_id=provider_id
        ) from exc


def _gemini_finish(value: object) -> FinishReason | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return FinishReason.UNKNOWN
    return {
        "STOP": FinishReason.STOP,
        "MAX_TOKENS": FinishReason.LENGTH,
        "SAFETY": FinishReason.REFUSAL,
        "RECITATION": FinishReason.REFUSAL,
        "MALFORMED_FUNCTION_CALL": FinishReason.UNKNOWN,
    }.get(value, FinishReason.UNKNOWN)


def _positive_int(value: object) -> int | None:
    return value if isinstance(value, int) and value > 0 else None


def _validation_from_error(provider_id: str, error: ProviderError) -> CredentialValidationResult:
    status = (
        CredentialValidationStatus.INVALID
        if error.code == "provider_authentication_error"
        else CredentialValidationStatus.RESTRICTED
        if error.code in {"provider_authorization_error", "provider_quota_exceeded"}
        else CredentialValidationStatus.PROVIDER_UNAVAILABLE
        if error.retryable
        else CredentialValidationStatus.UNVERIFIED
    )
    return CredentialValidationResult(provider_id=provider_id, status=status, message=error.message)
