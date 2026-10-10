from __future__ import annotations

import pytest

from yantra.core.contracts import ProviderCapabilities
from yantra.core.messages import Message, MessageRole, TextContent
from yantra.devtools.smoke import _print_response, run_cli
from yantra.providers.adapters.anthropic import AnthropicAdapter
from yantra.providers.adapters.ollama import OllamaAdapter
from yantra.providers.adapters.opencode import OpenCodeZenAdapter
from yantra.providers.base import FinishReason, ModelRequest, ModelResponse
from yantra.providers.catalog import ModelCatalogEntry
from yantra.providers.gateway import GatewayResponse
from yantra.routing.policy import RoutingDecision, RoutingMode


def test_offline_completion_is_explicit_and_never_uses_a_provider(capsys) -> None:
    assert run_cli(["offline"]) == 0

    output = capsys.readouterr().out
    assert "OFFLINE MOCK TEST" in output
    assert "no provider or network request" in output
    assert "offline mock response" in output
    assert "fixture usage: input=5, output=4, total=9" in output


def test_offline_stream_and_tool_proposal_do_not_execute_tools(capsys) -> None:
    assert run_cli(["offline", "--stream", "--tool-call"]) == 0

    output = capsys.readouterr().out
    assert "normalized streamed response" in output
    assert "smoke_echo" in output
    assert '"text": "offline mock"' in output
    assert "no tools were executed" in output


def test_provider_listing_never_prints_environment_credential(monkeypatch, capsys) -> None:
    secret = "local-test-key-do-not-display"
    monkeypatch.setenv("OPENCODE_ZEN_API_KEY", secret)

    assert run_cli(["providers"]) == 0

    output = capsys.readouterr().out
    assert "ollama: local endpoint; credentials not required" in output
    assert "opencode-zen: credential available (value hidden)" in output
    assert secret not in output


def test_normalized_response_redacts_credential_canary(capsys) -> None:
    secret = "response-secret-canary"
    response = ModelResponse(
        request_id="8c5727a7-9c89-4358-9032-6618bdd184ac",
        provider_id="ollama",
        model_id="llama3.2",
        message=Message(
            role=MessageRole.ASSISTANT,
            content=(TextContent(text=f"echo {secret}"),),
        ),
        finish_reason=FinishReason.STOP,
    )
    result = GatewayResponse(
        response=response,
        selected_model="ollama/llama3.2",
        routing_decision=RoutingDecision(
            selected_model="ollama/llama3.2",
            mode=RoutingMode.MANUAL,
            reason="test",
        ),
    )

    _print_response(result, elapsed_ms=1, secrets=(secret,))

    output = capsys.readouterr().out
    assert secret not in output
    assert "[REDACTED]" in output


def test_raw_key_is_not_echoed_as_invalid_credential_reference(capsys) -> None:
    secret = "not-a-reference-secret"
    with pytest.raises(SystemExit) as exit_info:
        run_cli(["--zen-credential-ref", secret, "providers"])

    assert exit_info.value.code == 2
    assert secret not in capsys.readouterr().err


def test_live_opencode_inference_requires_billable_opt_in_before_runtime(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        run_cli(["complete", "opencode-zen/claude-test"])

    assert exit_info.value.code == 2
    assert "explicit --allow-billable opt-in" in capsys.readouterr().err


def test_live_opencode_smoke_uses_reference_and_redacts_response(monkeypatch, capsys) -> None:
    secret = "opencode-live-test-canary"
    monkeypatch.setenv("OPENCODE_ZEN_API_KEY", secret)

    async def list_models(_: OpenCodeZenAdapter) -> tuple[ModelCatalogEntry, ...]:
        return (
            ModelCatalogEntry(
                provider_id="opencode-zen",
                model_id="claude-test",
                protocol="anthropic_messages",
                capabilities=ProviderCapabilities(streaming=True),
            ),
        )

    async def complete(_: AnthropicAdapter, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            request_id=request.request_id,
            provider_id="opencode-zen",
            model_id=request.model_id,
            message=Message(
                role=MessageRole.ASSISTANT,
                content=(TextContent(text=f"echo {secret}"),),
            ),
            finish_reason=FinishReason.STOP,
        )

    monkeypatch.setattr(OpenCodeZenAdapter, "list_models", list_models)
    monkeypatch.setattr(AnthropicAdapter, "complete", complete)

    assert run_cli(["complete", "opencode-zen/claude-test", "--allow-billable"]) == 0

    output = capsys.readouterr().out
    assert "LIVE INFERENCE TEST" in output
    assert "Billing opt-in: confirmed" in output
    assert "[REDACTED]" in output
    assert secret not in output


def test_models_command_uses_live_catalog_without_inference(monkeypatch, capsys) -> None:
    async def list_models(_: OllamaAdapter) -> tuple[ModelCatalogEntry, ...]:
        return (
            ModelCatalogEntry(
                provider_id="ollama",
                model_id="llama3.2",
                protocol="ollama_chat",
            ),
        )

    monkeypatch.setattr(OllamaAdapter, "list_models", list_models)

    status = run_cli(["models", "ollama"])

    assert status == 0
    output = capsys.readouterr().out
    assert "LIVE MODEL CATALOG for ollama (no inference request)" in output
    assert "ollama/llama3.2 | protocol=ollama_chat" in output
