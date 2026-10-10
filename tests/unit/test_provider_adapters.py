import json

import httpx
import pytest
from pydantic import SecretStr

from yantra.core.contracts import ModelCapability
from yantra.core.errors import (
    ProviderAuthenticationError,
    ProviderInvalidRequestError,
    ProviderProtocolError,
    ProviderTimeoutError,
)
from yantra.core.messages import Message, MessageRole, TextContent, ToolResult
from yantra.providers.adapters.anthropic import AnthropicAdapter
from yantra.providers.adapters.deepseek import DeepSeekAdapter
from yantra.providers.adapters.gemini import GeminiAdapter
from yantra.providers.adapters.generic import GenericOpenAICompatibleAdapter
from yantra.providers.adapters.ollama import OllamaAdapter
from yantra.providers.adapters.openai import OpenAIAdapter
from yantra.providers.adapters.opencode import (
    OpenCodeGoAdapter,
    OpenCodeProtocolResolver,
    OpenCodeZenAdapter,
)
from yantra.providers.adapters.openrouter import OpenRouterAdapter
from yantra.providers.base import (
    GenerationSettings,
    ModelProtocol,
    ModelRequest,
    ModelStreamEventType,
)
from yantra.providers.http import validate_endpoint
from yantra.security.credentials import CredentialManager


def request(
    model: str = "test-model", *, metadata: dict[str, object] | None = None
) -> ModelRequest:
    return ModelRequest(
        model_id=model,
        messages=(Message(role=MessageRole.USER, content=(TextContent(text="hello"),)),),
        generation=GenerationSettings(max_output_tokens=32),
        metadata=metadata or {},
    )


def client(base_url: str, handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=base_url)


@pytest.mark.asyncio
async def test_openai_responses_endpoint_normalizes_text_and_usage() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/responses"
        assert req.headers["authorization"] == "Bearer test-openai-key"
        body = json.loads(req.content)
        assert body["model"] == "gpt-test"
        return httpx.Response(
            200,
            headers={"x-request-id": "req-openai"},
            json={
                "id": "resp-1",
                "model": "gpt-test",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "hello from responses"}],
                    }
                ],
                "usage": {
                    "input_tokens": 4,
                    "output_tokens": 3,
                    "total_tokens": 7,
                    "input_tokens_details": {"cached_tokens": 1},
                },
            },
        )

    http = client("https://api.openai.com/v1/", handler)
    adapter = OpenAIAdapter(
        credential_reference="env://OPENAI_TEST_KEY",
        credential_manager=CredentialManager(environment={"OPENAI_TEST_KEY": "test-openai-key"}),
        client=http,
    )
    try:
        response = await adapter.complete(request("gpt-test"))
    finally:
        await http.aclose()

    assert response.message.content[0].text == "hello from responses"
    assert response.usage is not None
    assert response.usage.cached_input_tokens == 1
    assert response.provider_request_id == "req-openai"


@pytest.mark.asyncio
async def test_openai_responses_stream_normalizes_deltas_and_usage() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/responses"
        assert json.loads(req.content)["stream"] is True
        events = [
            {"type": "response.output_text.delta", "delta": "hello"},
            {
                "type": "response.completed",
                "response": {
                    "status": "completed",
                    "model": "gpt-test",
                    "usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "hello"}],
                        }
                    ],
                },
            },
        ]
        body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    http = client("https://api.openai.com/v1/", handler)
    adapter = OpenAIAdapter(client=http, credential_reference=None)
    try:
        events = [event async for event in adapter.stream(request("gpt-test"))]
    finally:
        await http.aclose()
    assert [event.event_type for event in events] == [
        ModelStreamEventType.RESPONSE_STARTED,
        ModelStreamEventType.TEXT_DELTA,
        ModelStreamEventType.USAGE,
        ModelStreamEventType.RESPONSE_COMPLETED,
    ]
    assert events[1].text_delta == "hello"


@pytest.mark.asyncio
async def test_openai_responses_normalizes_function_call_id_and_arguments() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "resp-tool",
                "model": "gpt-test",
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call-provider-42",
                        "name": "demo.echo",
                        "arguments": '{"text":"hello"}',
                    }
                ],
            },
        )

    http = client("https://api.openai.com/v1/", handler)
    adapter = OpenAIAdapter(client=http, credential_reference=None)
    try:
        response = await adapter.complete(request("gpt-test"))
    finally:
        await http.aclose()
    call = response.message.tool_calls[0]
    assert (call.call_id, call.name, call.arguments) == (
        "call-provider-42",
        "demo.echo",
        {"text": "hello"},
    )


@pytest.mark.asyncio
async def test_openai_auth_failure_is_normalized_and_body_is_not_exposed() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key=secret-must-not-leak"})

    http = client("https://api.openai.com/v1/", handler)
    adapter = OpenAIAdapter(
        credential_reference="env://OPENAI_TEST_KEY",
        credential_manager=CredentialManager(environment={"OPENAI_TEST_KEY": "invalid-key"}),
        client=http,
    )
    try:
        with pytest.raises(ProviderAuthenticationError) as error:
            await adapter.complete(request("gpt-test"))
    finally:
        await http.aclose()
    assert "secret-must-not-leak" not in str(error.value)


@pytest.mark.asyncio
async def test_openai_connect_timeout_is_normalized() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    http = client("https://api.openai.com/v1/", handler)
    adapter = OpenAIAdapter(client=http, credential_reference=None)
    try:
        with pytest.raises(ProviderTimeoutError):
            await adapter.complete(request("gpt-test"))
    finally:
        await http.aclose()


@pytest.mark.asyncio
async def test_anthropic_messages_preserves_tool_use_id_and_system_separation() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/messages"
        assert req.headers["x-api-key"] == "test-anthropic-key"
        body = json.loads(req.content)
        assert body["system"][0]["text"] == "be concise"
        assert all(message["role"] != "system" for message in body["messages"])
        assert body["tools"][0]["name"] == "demo.echo"
        return httpx.Response(
            200,
            headers={"request-id": "msg-request"},
            json={
                "id": "msg-1",
                "model": "claude-test",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu-preserved",
                        "name": "demo.echo",
                        "input": {"text": "hi"},
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 4, "output_tokens": 2},
            },
        )

    http = client("https://api.anthropic.com/v1/", handler)
    adapter = AnthropicAdapter(
        credential_reference="env://ANTHROPIC_TEST_KEY",
        credential_manager=CredentialManager(
            environment={"ANTHROPIC_TEST_KEY": "test-anthropic-key"}
        ),
        client=http,
    )
    input_model = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    from yantra.core.tools_schema import ProviderToolSchema

    model_request = ModelRequest(
        model_id="claude-test",
        messages=(
            Message(role=MessageRole.SYSTEM, content=(TextContent(text="be concise"),)),
            Message(role=MessageRole.USER, content=(TextContent(text="say hi"),)),
        ),
        tools=(ProviderToolSchema(name="demo.echo", description="Echo", parameters=input_model),),
        required_capabilities=frozenset({ModelCapability.TOOL_CALLING}),
        generation=GenerationSettings(max_output_tokens=128),
    )
    try:
        response = await adapter.complete(model_request)
    finally:
        await http.aclose()

    assert response.message.tool_calls[0].call_id == "toolu-preserved"
    tool_result = ToolResult(call_id="toolu-preserved", name="demo.echo", result={"text": "hi"})
    next_request = model_request.model_copy(
        update={
            "messages": model_request.messages
            + (Message(role=MessageRole.TOOL, tool_result=tool_result),)
        }
    )
    assert next_request.messages[-1].tool_result.call_id == "toolu-preserved"


@pytest.mark.asyncio
async def test_anthropic_stream_maps_text_usage_and_stop_reason() -> None:
    events = [
        {
            "type": "message_start",
            "message": {"model": "claude-test", "usage": {"input_tokens": 2, "output_tokens": 0}},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "hello"},
        },
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 1},
        },
        {"type": "message_stop"},
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        body = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    http = client("https://api.anthropic.com/v1/", handler)
    adapter = AnthropicAdapter(client=http, credential_reference=None)
    try:
        output = [event async for event in adapter.stream(request("claude-test"))]
    finally:
        await http.aclose()
    assert output[0].event_type == ModelStreamEventType.RESPONSE_STARTED
    assert any(event.text_delta == "hello" for event in output)
    assert output[-1].event_type == ModelStreamEventType.RESPONSE_COMPLETED


@pytest.mark.asyncio
async def test_gemini_uses_key_header_and_model_specific_rest_path() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1beta/models/gemini-test:generateContent"
        assert req.headers["x-goog-api-key"] == "test-gemini-key"
        assert "key=" not in str(req.url)
        return httpx.Response(
            200,
            json={
                "modelVersion": "gemini-test",
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "gemini hello"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 2,
                    "candidatesTokenCount": 2,
                    "totalTokenCount": 4,
                },
            },
        )

    http = client("https://generativelanguage.googleapis.com/v1beta/", handler)
    adapter = GeminiAdapter(
        credential_reference="env://GEMINI_TEST_KEY",
        credential_manager=CredentialManager(environment={"GEMINI_TEST_KEY": "test-gemini-key"}),
        client=http,
    )
    try:
        response = await adapter.complete(request("gemini-test"))
    finally:
        await http.aclose()
    assert response.message.content[0].text == "gemini hello"
    assert response.usage.total_tokens == 4


@pytest.mark.asyncio
async def test_gemini_stream_maps_text_and_completion() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        data = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "gemini stream"}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 2,
                "candidatesTokenCount": 2,
                "totalTokenCount": 4,
            },
        }
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=f"data: {json.dumps(data)}\n\n",
        )

    http = client("https://generativelanguage.googleapis.com/v1beta/", handler)
    adapter = GeminiAdapter(client=http, credential_reference=None)
    try:
        with adapter.use_credential(SecretStr("test-gemini-key")):
            events = [event async for event in adapter.stream(request("gemini-test"))]
    finally:
        await http.aclose()
    assert any(event.text_delta == "gemini stream" for event in events)
    assert events[-1].event_type == ModelStreamEventType.RESPONSE_COMPLETED


@pytest.mark.asyncio
async def test_deepseek_uses_official_chat_path_and_model_id() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/chat/completions"
        body = json.loads(req.content)
        assert body["model"] == "deepseek-v4-pro"
        assert body["max_tokens"] == 64
        assert "max_completion_tokens" not in body
        return httpx.Response(
            200,
            json={
                "id": "ds-1",
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "deepseek"},
                    }
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            },
        )

    http = client("https://api.deepseek.com/", handler)
    adapter = DeepSeekAdapter(
        credential_reference="env://DEEPSEEK_TEST_KEY",
        credential_manager=CredentialManager(
            environment={"DEEPSEEK_TEST_KEY": "test-deepseek-key"}
        ),
        client=http,
    )
    model_request = request("deepseek-v4-pro").model_copy(
        update={"generation": GenerationSettings(max_output_tokens=64)}
    )
    try:
        response = await adapter.complete(model_request)
    finally:
        await http.aclose()
    assert response.message.content[0].text == "deepseek"


@pytest.mark.asyncio
async def test_deepseek_stream_preserves_tool_call_identifier() -> None:
    chunks = [
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call-ds",
                                "type": "function",
                                "function": {"name": "demo.echo", "arguments": ""},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ]
        },
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [{"index": 0, "function": {"arguments": '{"text":"hi"}'}}]
                    },
                    "finish_reason": None,
                }
            ]
        },
        {
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
        },
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    http = client("https://api.deepseek.com/", handler)
    adapter = DeepSeekAdapter(client=http, credential_reference=None)
    try:
        events = [event async for event in adapter.stream(request("deepseek-v4-pro"))]
    finally:
        await http.aclose()
    calls = [event.tool_call_delta for event in events if event.tool_call_delta is not None]
    assert calls[0].call_id == "call-ds"
    assert calls[-1].arguments_delta == '{"text":"hi"}'


@pytest.mark.asyncio
async def test_openrouter_preserves_slashes_and_disables_upstream_fallback() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v1/chat/completions"
        body = json.loads(req.content)
        assert body["model"] == "anthropic/claude-sonnet-5-5"
        assert body["provider"]["allow_fallbacks"] is False
        return httpx.Response(
            200,
            json={
                "id": "or-1",
                "model": "anthropic/claude-sonnet-5-5",
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "router"}}
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    http = client("https://openrouter.ai/api/v1/", handler)
    adapter = OpenRouterAdapter(
        credential_reference="env://OPENROUTER_TEST_KEY",
        credential_manager=CredentialManager(
            environment={"OPENROUTER_TEST_KEY": "test-openrouter-key"}
        ),
        client=http,
    )
    try:
        response = await adapter.complete(request("anthropic/claude-sonnet-5-5"))
    finally:
        await http.aclose()
    assert response.model_id == "anthropic/claude-sonnet-5-5"


@pytest.mark.asyncio
async def test_opencode_zen_dispatches_to_protocol_specific_responses_endpoint() -> None:
    seen = False

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal seen
        if req.url.path == "/zen/v1/responses":
            seen = True
            assert req.headers["authorization"] == "Bearer zen-test-key"
            assert json.loads(req.content)["model"] == "gpt-6-luna"
            return httpx.Response(
                200,
                json={
                    "id": "resp-zen",
                    "model": "gpt-6-luna",
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "zen"}],
                        }
                    ],
                },
            )
        return httpx.Response(404)

    http = client("https://opencode.ai/zen/v1/", handler)
    adapter = OpenCodeZenAdapter(
        credential_manager=CredentialManager(environment={"OPENCODE_ZEN_API_KEY": "zen-test-key"}),
        client=http,
    )
    try:
        response = await adapter.complete(request("gpt-6-luna"))
    finally:
        await http.aclose()
    assert seen
    assert response.provider_id == "opencode-zen"
    assert response.message.content[0].text == "zen"


@pytest.mark.asyncio
async def test_opencode_go_gpt_luna_responses_request_uses_session_header() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/zen/go/v1/responses"
        assert req.headers["authorization"] == "Bearer go-test-key"
        assert req.headers["x-opencode-session"] == "session-gpt"
        assert req.headers["user-agent"] == "yantra/0.2.0"
        assert json.loads(req.content) == {
            "model": "gpt-6-luna",
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hello"}],
                }
            ],
            "max_output_tokens": 32,
        }
        return httpx.Response(
            200,
            json={
                "id": "go-gpt-response",
                "model": "gpt-6-luna",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "go response"}],
                    }
                ],
            },
        )

    http = client("https://opencode.ai/zen/go/v1/", handler)
    adapter = OpenCodeGoAdapter(
        credential_manager=CredentialManager(environment={"OPENCODE_GO_API_KEY": "go-test-key"}),
        client=http,
    )
    try:
        response = await adapter.complete(
            request("gpt-6-luna", metadata={"session_id": "session-gpt"})
        )
    finally:
        await http.aclose()
    assert response.message.content[0].text == "go response"


@pytest.mark.asyncio
async def test_opencode_go_uses_separate_endpoint_key_and_session_header() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"] == "Bearer go-test-key"
        if req.method == "GET":
            assert req.url.path == "/zen/go/v1/models"
            return httpx.Response(
                200,
                json={"data": [{"id": "deepseek-flash", "name": "DeepSeek Flash"}]},
            )
        assert req.headers["x-opencode-session"] == "session-123"
        assert req.url.path == "/zen/go/v1/chat/completions"
        assert json.loads(req.content) == {
            "model": "deepseek-flash",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 32,
        }
        return httpx.Response(
            200,
            json={
                "id": "go-1",
                "model": "deepseek-flash",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "go"},
                    }
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            },
        )

    http = client("https://opencode.ai/zen/go/v1/", handler)
    adapter = OpenCodeGoAdapter(
        credential_manager=CredentialManager(environment={"OPENCODE_GO_API_KEY": "go-test-key"}),
        client=http,
    )
    try:
        models = await adapter.list_models()
        response = await adapter.complete(
            request("deepseek-flash", metadata={"session_id": "session-123"})
        )
    finally:
        await http.aclose()
    assert response.provider_id == "opencode-go"
    assert models[0].model_id == "deepseek-flash"


@pytest.mark.asyncio
async def test_provider_http_error_exposes_only_safe_diagnostic_fields() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            headers={"x-request-id": "go_req_123"},
            json={
                "error": {
                    "code": "unsupported_parameter",
                    "message": "sensitive-response-body-canary",
                }
            },
        )

    http = client("https://opencode.ai/zen/go/v1/", handler)
    adapter = OpenCodeGoAdapter(
        credential_manager=CredentialManager(environment={"OPENCODE_GO_API_KEY": "go-test-key"}),
        client=http,
    )
    try:
        with pytest.raises(ProviderInvalidRequestError) as exc_info:
            await adapter.complete(request("gpt-6-luna", metadata={"session_id": "session-123"}))
    finally:
        await http.aclose()

    error = exc_info.value
    assert error.http_status == 400
    assert error.code == "provider_invalid_request"
    assert error.provider_error_code == "unsupported_parameter"
    assert error.provider_request_id == "go_req_123"
    assert "sensitive-response-body-canary" not in str(error)


@pytest.mark.asyncio
async def test_opencode_unknown_protocol_fails_before_network_request() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    http = client("https://opencode.ai/zen/v1/", handler)
    adapter = OpenCodeZenAdapter(client=http, credential_reference=None)
    try:
        with pytest.raises(ProviderProtocolError, match="no trusted protocol"):
            await adapter.complete(request("unmapped-model"))
    finally:
        await http.aclose()
    assert calls == 0


@pytest.mark.asyncio
async def test_ollama_local_chat_needs_no_key_and_does_not_download_models() -> None:
    seen_paths: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_paths.append(req.url.path)
        assert "authorization" not in req.headers
        if req.url.path == "/api/chat":
            return httpx.Response(
                200,
                json={
                    "model": "llama3.2:latest",
                    "message": {"role": "assistant", "content": "local"},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 3,
                    "eval_count": 2,
                },
            )
        if req.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "llama3.2:latest", "details": {"family": "llama"}}]}
            )
        if req.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion", "tools"]})
        return httpx.Response(404)

    http = client("http://127.0.0.1:11434/", handler)
    adapter = OllamaAdapter(client=http)
    try:
        models = await adapter.list_models()
        response = await adapter.complete(request("llama3.2:latest"))
    finally:
        await http.aclose()
    assert models[0].is_local
    assert models[0].capabilities.tool_calling is True
    assert response.message.content[0].text == "local"
    assert "/api/pull" not in seen_paths


@pytest.mark.parametrize("provider_id", ["opencode-zen", "opencode-go"])
def test_opencode_protocol_resolver_uses_distinct_official_endpoint_tables(
    provider_id: str,
) -> None:
    resolver = OpenCodeProtocolResolver(provider_id)
    if provider_id == "opencode-zen":
        assert resolver.resolve("gpt-6-luna") == ModelProtocol.OPENAI_RESPONSES
        assert resolver.resolve("claude-sonnet-5-5") == ModelProtocol.ANTHROPIC_MESSAGES
        assert resolver.resolve("gemini-3.8-flash") == ModelProtocol.GEMINI_CONTENT
    else:
        assert resolver.resolve("gpt-6-luna") == ModelProtocol.OPENAI_RESPONSES
        assert resolver.resolve("minimax-m3") == ModelProtocol.ANTHROPIC_MESSAGES
        assert resolver.resolve("glm-5.3") == ModelProtocol.OPENAI_CHAT
    assert resolver.resolve("future-model-protocol-unknown") is None


def test_custom_compatible_endpoint_requires_explicit_trusted_host() -> None:
    with pytest.raises(ValueError, match="trusted host allowlist"):
        GenericOpenAICompatibleAdapter(
            "custom-local",
            "https://inference.example/v1",
            trusted_hosts=frozenset(),
        )
    with pytest.raises(ValueError, match="allowlist"):
        GenericOpenAICompatibleAdapter(
            "custom",
            "https://untrusted.example/v1",
            trusted_hosts=frozenset({"approved.example"}),
        )
    with pytest.raises(ValueError, match="loopback"):
        validate_endpoint(
            "http://inference.example/v1", trusted_hosts=frozenset({"inference.example"})
        )


def test_zen_and_go_have_distinct_urls_and_credential_references() -> None:
    zen = OpenCodeZenAdapter()
    go = OpenCodeGoAdapter()
    assert zen.base_url == "https://opencode.ai/zen/v1/"
    assert go.base_url == "https://opencode.ai/zen/go/v1/"
    assert zen.provider_id != go.provider_id
    assert zen.credential_reference != go.credential_reference
