"""Small developer smoke runner for offline mocks and live YANTRA-002 providers."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import NoReturn, cast
from uuid import uuid4

from pydantic import JsonValue

from yantra.core.contracts import ModelCapability, ProviderCapabilities, TokenUsage
from yantra.core.errors import (
    CredentialUnavailableError,
    ProviderError,
    SecureStorageUnavailableError,
    YantraError,
)
from yantra.core.messages import Message, MessageRole, TextContent, ToolCall
from yantra.core.tools_schema import ProviderToolSchema
from yantra.providers import (
    GatewayResponse,
    MockProvider,
    ModelGateway,
    ModelRequest,
    ProviderRegistry,
)
from yantra.providers.adapters import OllamaAdapter, OpenCodeGoAdapter, OpenCodeZenAdapter
from yantra.providers.base import (
    FinishReason,
    GenerationSettings,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    ToolCallDelta,
)
from yantra.providers.catalog import ModelCatalog
from yantra.security.credentials import CredentialManager, CredentialReference

_SMOKE_TOOL = ProviderToolSchema(
    name="smoke_echo",
    description="Return the supplied text. This proposal is displayed, never executed.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
)


@dataclass(slots=True)
class _SmokeRuntime:
    credential_manager: CredentialManager
    registry: ProviderRegistry
    catalog: ModelCatalog
    gateway: ModelGateway
    adapters: tuple[OllamaAdapter | OpenCodeZenAdapter | OpenCodeGoAdapter, ...]


class _OfflineProvider(MockProvider):
    """Local deterministic provider that supports the same stream display path."""

    def __init__(self, response: ModelResponse, *, tool_call: bool) -> None:
        super().__init__(
            [response],
            provider_id="mock",
            capabilities=ProviderCapabilities(
                tool_calling=True,
                streaming=True,
                token_usage=True,
                cancellation=True,
            ),
        )
        self._tool_call = tool_call

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        yield ModelStreamEvent(
            event_type=ModelStreamEventType.RESPONSE_STARTED,
            request_id=request.request_id,
            provider_id=self.provider_id,
            model_id=request.model_id,
        )
        if self._tool_call:
            yield ModelStreamEvent(
                event_type=ModelStreamEventType.TOOL_CALL_DELTA,
                request_id=request.request_id,
                provider_id=self.provider_id,
                model_id=request.model_id,
                tool_call_delta=ToolCallDelta(
                    index=0,
                    call_id="mock-tool-call",
                    name_delta="smoke_echo",
                    arguments_delta='{"text":"offline mock"}',
                ),
            )
        else:
            yield ModelStreamEvent(
                event_type=ModelStreamEventType.TEXT_DELTA,
                request_id=request.request_id,
                provider_id=self.provider_id,
                model_id=request.model_id,
                text_delta="offline mock response",
            )
        yield ModelStreamEvent(
            event_type=ModelStreamEventType.USAGE,
            request_id=request.request_id,
            provider_id=self.provider_id,
            model_id=request.model_id,
            usage=TokenUsage(input_tokens=5, output_tokens=4, total_tokens=9),
        )
        yield ModelStreamEvent(
            event_type=ModelStreamEventType.RESPONSE_COMPLETED,
            request_id=request.request_id,
            provider_id=self.provider_id,
            model_id=request.model_id,
            finish_reason=FinishReason.STOP,
        )


def _credential_reference(value: str) -> str:
    try:
        return str(CredentialReference.parse(value))
    except YantraError:
        raise argparse.ArgumentTypeError(
            "expected an env:// or keyring:// credential reference"
        ) from None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yantra-smoke",
        description="Exercise the YANTRA-002 gateway without creating an agent or storing data.",
    )
    parser.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434", help="local Ollama endpoint"
    )
    parser.add_argument(
        "--zen-credential-ref",
        type=_credential_reference,
        default="env://OPENCODE_ZEN_API_KEY",
        help="secret reference for OpenCode Zen, never a raw key",
    )
    parser.add_argument(
        "--go-credential-ref",
        type=_credential_reference,
        default="env://OPENCODE_GO_API_KEY",
        help="secret reference for OpenCode Go, never a raw key",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("providers", help="list configured provider references without network I/O")

    models = commands.add_parser(
        "models", help="fetch a live provider model catalog (no inference)"
    )
    models.add_argument("provider", choices=("ollama", "opencode-zen", "opencode-go"))

    offline = commands.add_parser("offline", help="run a deterministic no-network mock test")
    offline.add_argument("--stream", action="store_true", help="exercise normalized mock streaming")
    offline.add_argument(
        "--tool-call", action="store_true", help="show a normalized mock tool proposal"
    )

    complete = commands.add_parser(
        "complete", help="run a live request against a manually selected provider/model"
    )
    complete.add_argument("model", help="provider/model reference from the live model catalog")
    complete.add_argument("--stream", action="store_true", help="test normalized live streaming")
    complete.add_argument(
        "--tool-call", action="store_true", help="test tool-call normalization; never executes it"
    )
    complete.add_argument(
        "--allow-billable",
        action="store_true",
        help="confirm this live inference request may incur charges",
    )
    complete.add_argument("--max-output-tokens", type=int, default=128)
    return parser


def _create_runtime(args: argparse.Namespace) -> _SmokeRuntime:
    credentials = CredentialManager()
    ollama = OllamaAdapter(base_url=args.ollama_url)
    zen = OpenCodeZenAdapter(
        credential_reference=args.zen_credential_ref, credential_manager=credentials
    )
    go = OpenCodeGoAdapter(
        credential_reference=args.go_credential_ref, credential_manager=credentials
    )
    registry = ProviderRegistry()
    registry.register(ollama, is_local=True, description="Local loopback Ollama server")
    registry.register(zen, description="OpenCode Zen gateway")
    registry.register(go, description="OpenCode Go gateway")
    catalog = ModelCatalog(registry)
    return _SmokeRuntime(
        credential_manager=credentials,
        registry=registry,
        catalog=catalog,
        gateway=ModelGateway(registry, catalog=catalog, credential_manager=credentials),
        adapters=(ollama, zen, go),
    )


def _redact(text: str, secrets: Sequence[str] = ()) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _provider_error_summary(error: ProviderError, secrets: Sequence[str] = ()) -> str:
    diagnostics = [f"code={error.code}"]
    if error.http_status is not None:
        diagnostics.append(f"http_status={error.http_status}")
    if error.provider_error_code is not None:
        diagnostics.append(f"provider_code={error.provider_error_code}")
    if error.provider_request_id is not None:
        diagnostics.append(f"request_id={error.provider_request_id}")
    if error.request_method is not None:
        diagnostics.append(f"method={error.request_method}")
    if error.endpoint_path is not None:
        diagnostics.append(f"path={error.endpoint_path}")
    if error.request_body_fields:
        diagnostics.append(f"body_fields={','.join(error.request_body_fields)}")
    if error.request_header_names:
        diagnostics.append(f"header_names={','.join(error.request_header_names)}")
    message = f"{error.message} ({', '.join(diagnostics)})"
    return _redact(message, secrets)


def _configured_status(runtime: _SmokeRuntime, provider_id: str) -> str:
    if provider_id == "ollama":
        return "local endpoint; credentials not required"
    adapter = runtime.registry.get(provider_id).adapter
    try:
        runtime.credential_manager.resolve(adapter.credential_reference)
    except SecureStorageUnavailableError:
        return "credential unavailable; secure OS keyring backend is not available"
    except CredentialUnavailableError:
        return "credential reference is not currently resolvable"
    return "credential available (value hidden)"


def _print_providers(runtime: _SmokeRuntime) -> None:
    print("Configured smoke-test providers (no network requests):")
    for registration in runtime.registry.list():
        provider_id = registration.metadata.provider_id
        print(f"- {provider_id}: {_configured_status(runtime, provider_id)}")


def _format_usage(usage: TokenUsage | None, *, fixture: bool = False) -> str:
    if usage is None:
        return "usage: unavailable"
    label = "fixture usage" if fixture else "usage"
    summary = (
        f"{label}: input={usage.input_tokens}, output={usage.output_tokens}, "
        f"total={usage.total_tokens}"
    )
    if usage.cached_input_tokens is not None:
        summary += f", cached_input={usage.cached_input_tokens}"
    if usage.reasoning_tokens is not None:
        summary += f", reasoning={usage.reasoning_tokens}"
    if usage.provider_reported_cost_usd is not None and not fixture:
        summary += f", provider_cost_usd={usage.provider_reported_cost_usd}"
    return summary


def _print_tool_calls(calls: Sequence[ToolCall], secrets: Sequence[str] = ()) -> None:
    if not calls:
        print("tool proposals: none returned")
        return
    print("tool proposals (normalized only; no tools were executed):")
    for call in calls:
        arguments = json.dumps(call.arguments, sort_keys=True, ensure_ascii=True)
        print(f"- {_redact(call.name, secrets)}({_redact(arguments, secrets)})")


def _print_response(
    result: GatewayResponse,
    *,
    elapsed_ms: float,
    secrets: Sequence[str] = (),
    fixture: bool = False,
) -> None:
    response = result.response
    print(f"selected model: {_redact(result.selected_model, secrets)}")
    print(f"provider model: {_redact(response.model_id, secrets)}")
    print(f"finish reason: {response.finish_reason.value}")
    text = "".join(part.text for part in response.message.content)
    if text:
        print("normalized text:")
        print(_redact(text, secrets))
    _print_tool_calls(response.message.tool_calls, secrets)
    print(_format_usage(response.usage, fixture=fixture))
    print(f"latency: {elapsed_ms:.1f} ms")


def _offline_response(request: ModelRequest, *, tool_call: bool) -> ModelResponse:
    if tool_call:
        return MockProvider.tool_call_response(
            request,
            "smoke_echo",
            {"text": "offline mock"},
            call_id="mock-tool-call",
            provider_id="mock",
            usage=TokenUsage(input_tokens=5, output_tokens=4, total_tokens=9),
        )
    return MockProvider.text_response(
        request,
        "offline mock response",
        provider_id="mock",
        usage=TokenUsage(input_tokens=5, output_tokens=4, total_tokens=9),
    )


async def _run_offline(args: argparse.Namespace) -> int:
    request = ModelRequest(
        model_id="smoke-test",
        messages=(
            Message(
                role=MessageRole.USER,
                content=(
                    TextContent(
                        text=(
                            "Propose a smoke_echo tool call with text 'offline mock'."
                            if args.tool_call
                            else "Reply briefly to the offline YANTRA smoke test."
                        ),
                    ),
                ),
            ),
        ),
        tools=(_SMOKE_TOOL,) if args.tool_call else (),
        required_capabilities=(
            frozenset({ModelCapability.TOOL_CALLING}) if args.tool_call else frozenset()
        ),
        generation=GenerationSettings(max_output_tokens=16),
    )
    provider = _OfflineProvider(
        _offline_response(request, tool_call=args.tool_call), tool_call=args.tool_call
    )
    registry = ProviderRegistry()
    registry.register(provider, is_local=True)
    gateway = ModelGateway(registry, default_model="mock/smoke-test")
    print("OFFLINE MOCK TEST: no provider or network request will be made")
    started = time.perf_counter()
    if args.stream:
        return await _print_stream(gateway, request, "mock/smoke-test", started, fixture=True)
    result = await gateway.complete(request)
    _print_response(result, elapsed_ms=(time.perf_counter() - started) * 1000, fixture=True)
    return 0


async def _print_stream(
    gateway: ModelGateway,
    request: ModelRequest,
    model: str,
    started: float,
    *,
    secrets: Sequence[str] = (),
    fixture: bool = False,
) -> int:
    text_parts: list[str] = []
    tool_calls: dict[int, dict[str, str | None]] = {}
    usage: TokenUsage | None = None
    finish_reason: FinishReason | None = None
    async for event in gateway.stream(request, model=model):
        if event.event_type == ModelStreamEventType.TEXT_DELTA and event.text_delta is not None:
            text_parts.append(event.text_delta)
        elif event.event_type == ModelStreamEventType.TOOL_CALL_DELTA:
            delta = event.tool_call_delta
            if delta is not None:
                call = tool_calls.setdefault(
                    delta.index, {"call_id": None, "name": "", "arguments": ""}
                )
                if delta.call_id:
                    call["call_id"] = delta.call_id
                if delta.name_delta:
                    call["name"] = (call["name"] or "") + delta.name_delta
                call["arguments"] = (call["arguments"] or "") + delta.arguments_delta
        elif event.event_type == ModelStreamEventType.USAGE:
            usage = event.usage or usage
        elif event.event_type == ModelStreamEventType.RESPONSE_COMPLETED:
            finish_reason = event.finish_reason
        elif event.event_type == ModelStreamEventType.RESPONSE_FAILED:
            error_code = _redact(event.error_code or "provider_error", secrets)
            print(f"ERROR: normalized stream failed ({error_code})")
            return 1

    elapsed_ms = (time.perf_counter() - started) * 1000
    print("normalized streamed response:")
    text = "".join(text_parts)
    if text:
        print(_redact(text, secrets))
    normalized_calls: list[ToolCall] = []
    for index, call in sorted(tool_calls.items()):
        try:
            raw_arguments = json.loads(call["arguments"] or "{}")
            if not isinstance(raw_arguments, dict):
                continue
            normalized_calls.append(
                ToolCall(
                    call_id=call["call_id"] or f"stream-call-{index}",
                    name=call["name"] or "unknown",
                    arguments=cast(dict[str, JsonValue], raw_arguments),
                )
            )
        except (json.JSONDecodeError, ValueError):
            print("tool proposal arguments: incomplete or invalid JSON")
    _print_tool_calls(normalized_calls, secrets)
    print(f"finish reason: {finish_reason.value if finish_reason else 'unknown'}")
    print(_format_usage(usage, fixture=fixture))
    print(f"latency: {elapsed_ms:.1f} ms")
    return 0


async def _execute(args: argparse.Namespace) -> int:
    runtime: _SmokeRuntime | None = None
    secrets: list[str] = []
    try:
        runtime = _create_runtime(args)
        if args.command == "providers":
            _print_providers(runtime)
            return 0
        if args.command == "offline":
            return await _run_offline(args)
        if args.command == "models":
            print(f"LIVE MODEL CATALOG for {args.provider} (no inference request)")
            if args.provider in {"opencode-zen", "opencode-go"}:
                adapter = runtime.registry.get(args.provider).adapter
                credential = runtime.credential_manager.resolve(adapter.credential_reference)
                secrets.append(credential.get_secret_value())
            entries = await runtime.catalog.list_models(args.provider)
            if not entries:
                print("No models were returned.")
            for entry in entries:
                protocol = entry.protocol or "unknown protocol"
                tool_calling = entry.capabilities.status(ModelCapability.TOOL_CALLING).value
                streaming = entry.capabilities.status(ModelCapability.STREAMING).value
                print(
                    f"- {_redact(entry.reference, secrets)} "
                    f"| protocol={_redact(protocol, secrets)} "
                    f"| tool_calling={tool_calling} | streaming={streaming}"
                )
            return 0

        provider_id, _, model_id = args.model.partition("/")
        if provider_id in {"opencode-zen", "opencode-go"}:
            adapter = runtime.registry.get(provider_id).adapter
            credential = runtime.credential_manager.resolve(adapter.credential_reference)
            secrets.append(credential.get_secret_value())
        catalog_entry = await runtime.catalog.get(args.model)
        if catalog_entry is None:
            raise YantraError("selected model was not found in the provider's live catalog")
        request_metadata: dict[str, JsonValue] = (
            {"session_id": str(uuid4())} if provider_id == "opencode-go" else {}
        )
        request = ModelRequest(
            model_id=model_id,
            messages=(
                Message(
                    role=MessageRole.USER,
                    content=(
                        TextContent(
                            text=(
                                "Call smoke_echo with text exactly 'YANTRA smoke test'. "
                                "Do not execute or describe it."
                                if args.tool_call
                                else "Reply briefly to the YANTRA developer smoke test."
                            ),
                        ),
                    ),
                ),
            ),
            tools=(_SMOKE_TOOL,) if args.tool_call else (),
            required_capabilities=(
                frozenset({ModelCapability.TOOL_CALLING}) if args.tool_call else frozenset()
            ),
            generation=GenerationSettings(max_output_tokens=args.max_output_tokens),
            metadata=request_metadata,
        )
        protocol = catalog_entry.protocol or "unknown protocol"
        print(
            f"LIVE INFERENCE TEST: {_redact(args.model, secrets)} "
            f"(protocol={_redact(protocol, secrets)})"
        )
        if args.allow_billable:
            print("Billing opt-in: confirmed by --allow-billable")
        started = time.perf_counter()
        if args.stream:
            return await _print_stream(
                runtime.gateway,
                request,
                args.model,
                started,
                secrets=secrets,
            )
        result = await runtime.gateway.complete(request, model=args.model)
        _print_response(
            result,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            secrets=secrets,
        )
        return 0
    except ProviderError as exc:
        print(f"ERROR: {_provider_error_summary(exc, secrets)}", file=sys.stderr)
        return 1
    except YantraError as exc:
        print(f"ERROR: {_redact(exc.message, secrets)}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: smoke test failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    finally:
        if runtime is not None:
            for adapter in runtime.adapters:
                try:
                    await adapter.aclose()
                except Exception:
                    pass


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Run the smoke CLI and return a process exit status."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "complete":
        provider_id, separator, model_id = args.model.partition("/")
        if not separator or not provider_id or not model_id:
            parser.error("complete requires a provider/model reference")
        if provider_id not in {"ollama", "opencode-zen", "opencode-go"}:
            parser.error("this smoke runner supports ollama, opencode-zen, and opencode-go")
        if not 1 <= args.max_output_tokens <= 4096:
            parser.error("--max-output-tokens must be between 1 and 4096")
        if provider_id != "ollama" and not args.allow_billable:
            parser.error("OpenCode inference requires explicit --allow-billable opt-in")
    return asyncio.run(_execute(args))


def main() -> NoReturn:
    """Console-script entry point."""
    raise SystemExit(run_cli())
