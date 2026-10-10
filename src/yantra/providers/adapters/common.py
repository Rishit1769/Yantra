"""Shared, strictly bounded OpenAI-compatible request and response translation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any, TypeGuard, cast

from pydantic import JsonValue

from yantra.core.contracts import TokenUsage
from yantra.core.errors import ProviderError, ProviderProtocolError, UnsupportedCapabilityError
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.providers.base import (
    FinishReason,
    ModelRequest,
    ModelResponse,
)
from yantra.providers.catalog import ModelCatalogEntry
from yantra.providers.validation import CredentialValidationResult, CredentialValidationStatus


def is_json_object(value: object) -> TypeGuard[Mapping[str, Any]]:
    """Validate string keys and narrow untrusted provider JSON for strict typing."""
    if not isinstance(value, Mapping):
        return False
    candidate = cast(Mapping[Any, Any], value)
    return all(isinstance(key, str) for key in candidate)


def _text_parts(content: object, *, provider_id: str) -> tuple[TextContent, ...]:
    if content is None:
        return ()
    if isinstance(content, str):
        return (TextContent(text=content),) if content else ()
    if isinstance(content, list):
        result: list[TextContent] = []
        for part in cast(list[Any], content):
            if is_json_object(part) and part.get("type") in {"text", "output_text"}:
                text = part.get("text")
                if isinstance(text, str):
                    result.append(TextContent(text=text))
                    continue
            raise UnsupportedCapabilityError(
                "provider returned content blocks unsupported by the normalized YANTRA message",
                provider_id=provider_id,
            )
        return tuple(result)
    raise ProviderProtocolError(
        "provider returned an unsupported content representation", provider_id=provider_id
    )


def chat_request_messages(
    messages: tuple[Message, ...], *, provider_id: str
) -> list[dict[str, Any]]:
    """Translate explicit normalized text/tool messages to chat-completions messages."""
    converted: list[dict[str, Any]] = []
    for message in messages:
        content = "".join(part.text for part in message.content)
        if message.role == MessageRole.TOOL:
            result = message.tool_result
            if result is None:
                raise ProviderProtocolError(
                    "tool message is missing its result", provider_id=provider_id
                )
            converted.append(
                {
                    "role": "tool",
                    "tool_call_id": result.call_id,
                    "name": result.name,
                    "content": json.dumps(result.result, separators=(",", ":"), ensure_ascii=False),
                }
            )
            continue
        item: dict[str, Any] = {"role": message.role.value, "content": content}
        if message.tool_calls:
            item["tool_calls"] = [
                {
                    "id": call.call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, separators=(",", ":")),
                    },
                }
                for call in message.tool_calls
            ]
        converted.append(item)
    return converted


def chat_tools(request: ModelRequest) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in request.tools
    ]


def usage_from_openai(value: object, *, provider_id: str) -> TokenUsage | None:
    if value is None:
        return None
    if not is_json_object(value):
        raise ProviderProtocolError(
            "provider usage metadata was malformed", provider_id=provider_id
        )
    prompt = value.get("prompt_tokens", value.get("input_tokens"))
    completion = value.get("completion_tokens", value.get("output_tokens"))
    total = value.get("total_tokens")
    if (
        not isinstance(prompt, int)
        or isinstance(prompt, bool)
        or not isinstance(completion, int)
        or isinstance(completion, bool)
    ):
        return None
    cached: int | None = None
    prompt_details = value.get("prompt_tokens_details") or value.get("input_tokens_details")
    if is_json_object(prompt_details):
        candidate = prompt_details.get("cached_tokens")
        if isinstance(candidate, int):
            cached = candidate
    if not isinstance(total, int) or isinstance(total, bool):
        total = prompt + completion
    reasoning: int | None = None
    output_details = value.get("completion_tokens_details") or value.get("output_tokens_details")
    if is_json_object(output_details) and isinstance(output_details.get("reasoning_tokens"), int):
        reasoning = output_details["reasoning_tokens"]
    return TokenUsage(
        input_tokens=prompt,
        output_tokens=completion,
        total_tokens=total,
        cached_input_tokens=cached,
        reasoning_tokens=reasoning,
    )


def parse_chat_response(
    value: Mapping[str, Any],
    request: ModelRequest,
    *,
    provider_id: str,
    model_id: str | None = None,
    provider_request_id: str | None = None,
) -> ModelResponse:
    choices = value.get("choices")
    if not isinstance(choices, list):
        raise ProviderProtocolError(
            "provider chat response contained no choices", provider_id=provider_id
        )
    choice_records = cast(list[Any], choices)
    if not choice_records or not is_json_object(choice_records[0]):
        raise ProviderProtocolError(
            "provider chat response contained no choices", provider_id=provider_id
        )
    choice = choice_records[0]
    source_message = choice.get("message")
    if not is_json_object(source_message):
        raise ProviderProtocolError(
            "provider chat response contained no message", provider_id=provider_id
        )
    blocks = _text_parts(source_message.get("content"), provider_id=provider_id)
    tool_calls: list[ToolCall] = []
    raw_calls_value = source_message.get("tool_calls")
    if raw_calls_value is None:
        raw_calls_value = []
    if not isinstance(raw_calls_value, list):
        raise ProviderProtocolError("provider tool calls were malformed", provider_id=provider_id)
    raw_calls = cast(list[Any], raw_calls_value)
    for index, raw_call in enumerate(raw_calls):
        if not is_json_object(raw_call):
            raise ProviderProtocolError("provider tool call was malformed", provider_id=provider_id)
        function = raw_call.get("function")
        if not is_json_object(function):
            raise ProviderProtocolError(
                "provider tool call function was malformed", provider_id=provider_id
            )
        raw_arguments = function.get("arguments", "{}")
        if isinstance(raw_arguments, str):
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                raise ProviderProtocolError(
                    "provider tool arguments were invalid JSON", provider_id=provider_id
                ) from exc
        else:
            arguments = raw_arguments
        if not is_json_object(arguments):
            raise ProviderProtocolError(
                "provider tool arguments were not an object", provider_id=provider_id
            )
        call_id = raw_call.get("id")
        if not isinstance(call_id, str) or not call_id:
            # Assign a stable YANTRA ID if a compatible service omits one.
            call_id = f"{request.request_id}-{index}"
        name = function.get("name")
        if not isinstance(name, str) or not name:
            raise ProviderProtocolError("provider tool call has no name", provider_id=provider_id)
        tool_calls.append(
            ToolCall(
                call_id=call_id,
                name=name,
                arguments=cast(dict[str, JsonValue], dict(arguments)),
            )
        )
    if not blocks and not tool_calls:
        raise ProviderProtocolError(
            "provider returned an empty assistant response", provider_id=provider_id
        )
    message = Message(role=MessageRole.ASSISTANT, content=blocks, tool_calls=tuple(tool_calls))
    reasoning_content = source_message.get("reasoning_content")
    if isinstance(reasoning_content, str):
        message = message.model_copy(
            update={
                "provider_extensions": {
                    f"{provider_id}.chat": {"reasoning_content": reasoning_content}
                }
            }
        )
    reason = choice.get("finish_reason")
    finish_map = {
        "stop": FinishReason.STOP,
        "tool_calls": FinishReason.TOOL_CALLS,
        "length": FinishReason.LENGTH,
        "content_filter": FinishReason.REFUSAL,
    }
    finish = (
        finish_map.get(reason, FinishReason.UNKNOWN)
        if isinstance(reason, str)
        else FinishReason.UNKNOWN
    )
    usage = usage_from_openai(value.get("usage"), provider_id=provider_id)
    response_id = value.get("id")
    return ModelResponse(
        request_id=request.request_id,
        provider_id=provider_id,
        model_id=str(value.get("model") or model_id or request.model_id),
        message=message,
        finish_reason=finish,
        usage=usage,
        provider_request_id=provider_request_id
        or (response_id if isinstance(response_id, str) else None),
        metadata={
            "system_fingerprint": value.get("system_fingerprint")
            if isinstance(value.get("system_fingerprint"), str)
            else None
        },
    )


def catalog_entries_from_openai(
    value: Mapping[str, Any], *, provider_id: str
) -> tuple[ModelCatalogEntry, ...]:
    data = value.get("data")
    if not isinstance(data, list):
        raise ProviderProtocolError(
            "provider model catalog response was malformed", provider_id=provider_id
        )
    records = cast(list[Any], data)
    entries: list[ModelCatalogEntry] = []
    for item in records:
        if not is_json_object(item) or not isinstance(item.get("id"), str):
            continue
        name = item.get("name")
        entries.append(
            ModelCatalogEntry(
                provider_id=provider_id,
                model_id=item["id"],
                display_name=name if isinstance(name, str) else None,
                context_window_tokens=(
                    item.get("context_length")
                    if isinstance(item.get("context_length"), int)
                    else None
                ),
                metadata={
                    "owned_by": item.get("owned_by")
                    if isinstance(item.get("owned_by"), str)
                    else "unknown"
                },
            )
        )
    return tuple(entries)


def validation_from_error(provider_id: str, error: ProviderError) -> CredentialValidationResult:
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


async def iter_sse_data(response: Any, *, max_stream_bytes: int) -> AsyncIterator[str]:
    """Yield SSE data fields with a total byte ceiling; never buffers the full stream."""
    total = 0
    data_lines: list[str] = []
    async for line in response.aiter_lines():
        total += len(line.encode("utf-8")) + 1
        if total > max_stream_bytes:
            raise ProviderProtocolError("provider stream exceeded configured size limit")
        if line == "":
            if data_lines:
                yield "\n".join(data_lines)
                data_lines.clear()
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if data_lines:
        yield "\n".join(data_lines)
