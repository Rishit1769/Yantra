"""Configurable OpenAI Chat Completions-compatible provider adapter."""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

import httpx
from pydantic import SecretStr

from yantra.core.contracts import ProviderCapabilities, merge_capabilities
from yantra.core.errors import (
    ProviderError,
    ProviderProtocolError,
    UnsupportedCapabilityError,
)
from yantra.providers.adapters.common import (
    catalog_entries_from_openai,
    chat_request_messages,
    chat_tools,
    is_json_object,
    iter_sse_data,
    parse_chat_response,
    usage_from_openai,
)
from yantra.providers.base import (
    FinishReason,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    ToolCallDelta,
)
from yantra.providers.catalog import ModelCatalogEntry, ModelPricing
from yantra.providers.http import HttpxProvider
from yantra.providers.validation import (
    CredentialValidationResult,
    CredentialValidationStatus,
)
from yantra.security.credentials import CredentialManager


class OpenAICompatibleAdapter(HttpxProvider):
    """Adapter for endpoints that implement a tested subset of Chat Completions."""

    _allowed_options = frozenset(
        {
            "seed",
            "frequency_penalty",
            "presence_penalty",
            "logit_bias",
            "logprobs",
            "top_logprobs",
            "parallel_tool_calls",
            "tool_choice",
            "user",
            "provider",
        }
    )

    def __init__(
        self,
        provider_id: str,
        base_url: str,
        *,
        credential_reference: str | None = None,
        credential_manager: CredentialManager | None = None,
        trusted_hosts: frozenset[str] = frozenset(),
        allow_private_network: bool = False,
        client: httpx.AsyncClient | None = None,
        capability_overrides: Mapping[str, ProviderCapabilities] | None = None,
        default_capabilities: ProviderCapabilities | None = None,
        structured_output: str | None = "json_schema",
        stream_usage: bool = True,
        session_header_name: str | None = None,
    ) -> None:
        super().__init__(
            provider_id,
            base_url,
            credential_reference=credential_reference,
            credential_manager=credential_manager,
            trusted_hosts=trusted_hosts,
            allow_private_network=allow_private_network,
            client=client,
            session_header_name=session_header_name,
        )
        self._default_capabilities = default_capabilities or ProviderCapabilities(
            streaming=True,
            token_usage=True,
        )
        self._capability_overrides = dict(capability_overrides or {})
        if structured_output not in {None, "json_schema", "json_object"}:
            raise ValueError("structured_output must be json_schema, json_object, or None")
        self.structured_output_style = structured_output
        self.stream_usage = stream_usage

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Adapter-wide fallback; unknown model capabilities remain unknown."""
        return self._default_capabilities

    def capabilities_for(self, model_id: str) -> ProviderCapabilities:
        """Return explicit model override or adapter-level declared capability data."""
        return merge_capabilities(
            self._default_capabilities,
            self._capability_overrides.get(model_id),
        )

    def _headers(
        self,
        secret: SecretStr | None = None,
        request: ModelRequest | None = None,
    ) -> dict[str, str]:
        return {
            **self.request_headers(request),
            "Content-Type": "application/json",
            **self.auth_headers(secret_override=secret),
        }

    async def list_models(
        self, *, secret: SecretStr | None = None
    ) -> tuple[ModelCatalogEntry, ...]:
        payload, _ = await self.request_json("GET", "models", headers=self._headers(secret))
        return self._normalize_catalog(payload)

    def _normalize_catalog(self, payload: Mapping[str, Any]) -> tuple[ModelCatalogEntry, ...]:
        entries = catalog_entries_from_openai(payload, provider_id=self.provider_id)
        normalized: list[ModelCatalogEntry] = []
        raw_models = payload.get("data")
        if not isinstance(raw_models, list):
            raise ProviderProtocolError(
                "provider model catalog response was malformed", provider_id=self.provider_id
            )
        for entry, raw in zip(entries, cast(list[Any], raw_models), strict=False):
            if not is_json_object(raw):
                normalized.append(entry)
                continue
            params = raw.get("supported_parameters")
            cap = self.capabilities_for(entry.model_id)
            if isinstance(params, list):
                supported = {item for item in cast(list[Any], params) if isinstance(item, str)}
                cap = cap.model_copy(
                    update={
                        "tool_calling": "tools" in supported,
                        "structured_output": bool(
                            {"response_format", "structured_outputs"} & supported
                        ),
                    }
                )
            pricing = _pricing_from_openrouter(raw.get("pricing"))
            normalized.append(
                entry.model_copy(
                    update={
                        "capabilities": cap,
                        "pricing": pricing or entry.pricing,
                        "context_window_tokens": _first_int(
                            raw.get("context_length"), raw.get("context_window")
                        )
                        or entry.context_window_tokens,
                        "metadata": {
                            **entry.metadata,
                            **_selected_catalog_metadata(raw),
                        },
                    }
                )
            )
        return tuple(normalized)

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
            if exc.code == "provider_authentication_error":
                status = CredentialValidationStatus.INVALID
            elif exc.code == "provider_authorization_error":
                status = CredentialValidationStatus.RESTRICTED
            elif exc.retryable:
                status = CredentialValidationStatus.PROVIDER_UNAVAILABLE
            else:
                status = CredentialValidationStatus.UNVERIFIED
            return CredentialValidationResult(
                provider_id=self.provider_id,
                status=status,
                message=exc.message,
            )
        return CredentialValidationResult(
            provider_id=self.provider_id,
            status=CredentialValidationStatus.VALID,
            message="Authenticated catalog listing succeeded; inference access is model-specific",
            catalog_model_count=len(models),
        )

    def build_chat_payload(self, request: ModelRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model_id,
            "messages": chat_request_messages(request.messages, provider_id=self.provider_id),
        }
        settings = request.generation
        if settings.temperature is not None:
            payload["temperature"] = settings.temperature
        if settings.top_p is not None:
            payload["top_p"] = settings.top_p
        if settings.max_output_tokens is not None:
            payload["max_completion_tokens"] = settings.max_output_tokens
        if settings.stop_sequences:
            payload["stop"] = list(settings.stop_sequences)
        if request.tools:
            payload["tools"] = chat_tools(request)
        if request.response_schema is not None:
            if self.structured_output_style is None:
                raise UnsupportedCapabilityError(
                    "this endpoint does not implement YANTRA structured-output translation",
                    provider_id=self.provider_id,
                )
            if self.structured_output_style == "json_schema":
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "yantra_response",
                        "strict": True,
                        "schema": request.response_schema,
                    },
                }
            else:
                raise UnsupportedCapabilityError(
                    "provider JSON mode cannot guarantee the requested JSON Schema",
                    provider_id=self.provider_id,
                )
        for name, value in request.provider_options.items():
            if name not in self._allowed_options:
                raise UnsupportedCapabilityError(
                    f"provider option {name!r} is not allowed by this adapter",
                    provider_id=self.provider_id,
                )
            payload[name] = value
        return payload

    async def complete(self, request: ModelRequest) -> ModelResponse:
        payload = self.build_chat_payload(request)
        result, headers = await self.request_json(
            "POST",
            "chat/completions",
            headers=self._headers(request=request),
            json_body=payload,
            timeout_seconds=request.timeout_seconds,
        )
        return parse_chat_response(
            result,
            request,
            provider_id=self.provider_id,
            provider_request_id=headers.get("x-request-id"),
        )

    async def stream(self, request: ModelRequest):
        payload = self.build_chat_payload(request)
        payload["stream"] = True
        if self.stream_usage:
            payload["stream_options"] = {"include_usage": True}
        async with self.stream_response(
            "POST",
            "chat/completions",
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
            async for data in iter_sse_data(response, max_stream_bytes=self._max_stream_bytes):
                if data == "[DONE]":
                    continue
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise ProviderProtocolError(
                        "provider stream contained invalid JSON", provider_id=self.provider_id
                    ) from exc
                if not is_json_object(chunk):
                    raise ProviderProtocolError(
                        "provider stream event was not an object", provider_id=self.provider_id
                    )
                usage = usage_from_openai(chunk.get("usage"), provider_id=self.provider_id)
                if usage is not None:
                    yield ModelStreamEvent(
                        event_type=ModelStreamEventType.USAGE,
                        request_id=request.request_id,
                        provider_id=self.provider_id,
                        model_id=str(chunk.get("model") or request.model_id),
                        usage=usage,
                    )
                choices_value = chunk.get("choices")
                if choices_value is None:
                    choices_value = []
                if not isinstance(choices_value, list):
                    raise ProviderProtocolError(
                        "provider stream choices were malformed", provider_id=self.provider_id
                    )
                for choice in cast(list[Any], choices_value):
                    if not is_json_object(choice):
                        continue
                    delta = choice.get("delta")
                    if is_json_object(delta):
                        text = delta.get("content")
                        if isinstance(text, str) and text:
                            yield ModelStreamEvent(
                                event_type=ModelStreamEventType.TEXT_DELTA,
                                request_id=request.request_id,
                                provider_id=self.provider_id,
                                model_id=str(chunk.get("model") or request.model_id),
                                text_delta=text,
                            )
                        reasoning = delta.get("reasoning_content")
                        if isinstance(reasoning, str) and reasoning:
                            yield ModelStreamEvent(
                                event_type=ModelStreamEventType.REASONING_DELTA,
                                request_id=request.request_id,
                                provider_id=self.provider_id,
                                model_id=str(chunk.get("model") or request.model_id),
                                text_delta=reasoning,
                            )
                        raw_tool_deltas_value = delta.get("tool_calls")
                        if raw_tool_deltas_value is None:
                            raw_tool_deltas_value = []
                        if not isinstance(raw_tool_deltas_value, list):
                            raise ProviderProtocolError(
                                "provider stream tool deltas were malformed",
                                provider_id=self.provider_id,
                            )
                        for raw_delta in cast(list[Any], raw_tool_deltas_value):
                            event = _tool_delta_event(raw_delta, request, self.provider_id)
                            if event is not None:
                                yield event
                    finish = _finish_reason(choice.get("finish_reason"))
                    if finish is not None:
                        yield ModelStreamEvent(
                            event_type=ModelStreamEventType.RESPONSE_COMPLETED,
                            request_id=request.request_id,
                            provider_id=self.provider_id,
                            model_id=str(chunk.get("model") or request.model_id),
                            finish_reason=finish,
                            usage=usage,
                        )

    @property
    def _max_stream_bytes(self) -> int:
        return self._max_response_bytes


def _tool_delta_event(
    raw: object, request: ModelRequest, provider_id: str
) -> ModelStreamEvent | None:
    if not is_json_object(raw):
        raise ProviderProtocolError("provider tool delta was malformed", provider_id=provider_id)
    function = raw.get("function")
    if not is_json_object(function):
        raise ProviderProtocolError(
            "provider tool delta function was malformed", provider_id=provider_id
        )
    index = raw.get("index", 0)
    if not isinstance(index, int):
        raise ProviderProtocolError(
            "provider tool delta index was malformed", provider_id=provider_id
        )
    call_id = raw.get("id")
    name = function.get("name")
    arguments = function.get("arguments")
    delta = ToolCallDelta(
        index=index,
        call_id=call_id if isinstance(call_id, str) else None,
        name_delta=name if isinstance(name, str) else None,
        arguments_delta=arguments if isinstance(arguments, str) else "",
    )
    return ModelStreamEvent(
        event_type=ModelStreamEventType.TOOL_CALL_DELTA,
        request_id=request.request_id,
        provider_id=provider_id,
        model_id=request.model_id,
        tool_call_delta=delta,
    )


def _finish_reason(value: object) -> FinishReason | None:
    if value is None:
        return None
    finish_reasons = {
        "stop": FinishReason.STOP,
        "tool_calls": FinishReason.TOOL_CALLS,
        "length": FinishReason.LENGTH,
        "content_filter": FinishReason.REFUSAL,
    }
    return (
        finish_reasons.get(value, FinishReason.UNKNOWN)
        if isinstance(value, str)
        else FinishReason.UNKNOWN
    )


def _first_int(*values: object) -> int | None:
    return next((value for value in values if isinstance(value, int) and value > 0), None)


def _pricing_from_openrouter(value: object) -> ModelPricing | None:
    if not is_json_object(value):
        return None
    try:
        input_rate = Decimal(str(value["prompt"])) * Decimal(1_000_000)
        output_rate = Decimal(str(value["completion"])) * Decimal(1_000_000)
        cached_raw = value.get("input_cache_read") or value.get("input_cache_read_price")
        cached_rate = (
            Decimal(str(cached_raw)) * Decimal(1_000_000) if cached_raw is not None else None
        )
    except (KeyError, ArithmeticError, ValueError):
        return None
    if not input_rate.is_finite() or not output_rate.is_finite():
        return None
    return ModelPricing(
        input_usd_per_million=input_rate,
        output_usd_per_million=output_rate,
        cached_input_usd_per_million=cached_rate,
        source="OpenRouter model catalog",
    )


def _selected_catalog_metadata(raw: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("supported_parameters", "architecture", "top_provider", "created", "owned_by")
    return {key: raw[key] for key in keys if key in raw}
