# Core Runtime API (YANTRA-001)

**Status:** The YANTRA-001 contract foundation and YANTRA-002 model gateway have local test coverage on macOS/Python 3.12.15. The current repository suite, lint, type check, and package build are verified locally; see session validation rather than treating historical counts below as current. macOS/Windows GitHub Actions and live provider behavior have not been verified. This page does not document a full agent loop, runtime scheduler, tool authorization system, or durable persistence adapter.

## Package and installation

Package import root is `yantra`; source uses `src/yantra`. Development setup: `uv sync --all-groups`. The package requires Python 3.12+ and Pydantic v2. Version is currently `0.1.0`. No package-index release is published, and license selection remains unresolved.

## Agent and budget

`yantra.core.agent.AgentConfig` is a frozen Pydantic model containing `agent_id`, `name`, `description`, `system_instructions`, `provider_id`, `model_id`, `tool_references`, `execution_limits`, and JSON-compatible metadata. IDs are restricted to a bounded identifier syntax. Tool references must be non-empty and unique. Agent configuration is declarative; it cannot start a run.

`yantra.core.budgets.ExecutionBudget` validates finite positive wall time, call/step/token bounds, and optional positive cost. `max_model_calls` cannot exceed `max_steps`. Limits are configuration only; no runtime enforcement exists.

## Messages

`Message` is an immutable Pydantic model with roles `system`, `developer`, `user`, `assistant`, `tool`; `TextContent`; optional typed `ToolCall`/`ToolResult`; UUID, aware timestamp, generic JSON metadata, and explicitly qualified `provider_extensions`. Assistant messages with no visible content/tool calls are allowed only when they carry non-empty provider-namespaced `reasoning_content`; that private reasoning remains metadata, not user-facing text. Extra fields are forbidden. `to_json()` and `from_json()` use Pydantic's JSON serialization/validation. Tool arguments remain untrusted values; parsing them does not authorize anything.

## Providers

`ModelProvider` is an async `Protocol` exposing `provider_id`, explicit `ProviderCapabilities`, and `complete(ModelRequest)`. Streaming is an optional, separate `StreamingModelProvider` protocol; the mock does not implement streaming. Requests carry required capabilities, timeout, messages, optional tool schemas and structured response schema. Responses carry provider/model/request identity, assistant message, finish reason, optional usage, and provider request ID. Unsupported capabilities are not silently inferred.

`MockProvider` consumes a configured ordered sequence of `ModelResponse` or normalized `ProviderError` objects, records submitted requests, raises a typed exhaustion error after the sequence ends, and can synthesize text/tool-call response objects for a supplied request. It performs no I/O and uses no randomness. Usage on a mock response is fixture data, not a measured token count.

```python
from yantra.core.messages import Message, MessageRole, TextContent
from yantra.providers import ModelRequest, MockProvider

request = ModelRequest(
    model_id="mock-small",
    messages=(Message(role=MessageRole.USER, content=(TextContent(text="hello"),)),),
)
provider = MockProvider([MockProvider.text_response(request, "hello back")])
```

The asynchronous call is `await provider.complete(request)`. YANTRA-001's deterministic mock remains a contract test helper; it is not a live adapter.

## Model Gateway (YANTRA-002)

`ModelGateway` wraps an explicit `ProviderRegistry`, resolves `provider/model` references, validates required capabilities, applies `ModelRoutingPolicy`, and returns a `GatewayResponse` with actual route/fallback metadata and available cost information. `complete()` supports a manually selected model by default; automatic routing requires a catalog plus a current digest-bound policy approval. `stream()` yields normalized `ModelStreamEvent` values and will not switch providers after yielding an event. Catalog listing and credential validation are separate from inference entitlement.

Provider adapters exist for OpenAI, Anthropic, Gemini, DeepSeek, Ollama, OpenRouter, OpenCode Zen/Go, and configurable OpenAI Chat Completions-compatible endpoints. Their HTTP behavior is covered by mocked transports only; this does not verify current live API behavior. Cost enforcement is a preflight estimate based on explicit input/output token bounds and provider pricing metadata, not a guaranteed billing cap. Credential smoke tests can incur charges and require explicit opt-in.

## Tools and registry

`ToolDefinition` combines name/description, Pydantic input and optional output model classes, callable, explicit sync/async mode, descriptive required permission scopes, side-effect classification, and optional timeout. It validates input/output without echoing rejected values. `ToolRegistry` implements `register`, `get`, name-sorted `list`, `unregister`, and deterministic `export_provider_schemas`.

```python
from pydantic import BaseModel
from yantra.tools import ExecutionMode, SideEffect, ToolDefinition, ToolRegistry

class EchoInput(BaseModel):
    text: str

def echo(arguments: EchoInput) -> EchoInput:
    return arguments

tool = ToolDefinition(
    name="demo.echo",
    description="Return the validated input",
    input_model=EchoInput,
    output_model=EchoInput,
    executor=echo,
    execution_mode=ExecutionMode.SYNC,
    permission_scopes=frozenset({"demo:read"}),
    side_effect=SideEffect.READ_ONLY,
)
registry = ToolRegistry()
registry.register(tool)
schema = registry.export_provider_schemas()[0]
```

The `permission_scopes` field is metadata only. There is no policy engine or execution dispatcher; registration and model schema export never grant permission. No shell/browser/filesystem tool is included.

## States and events

`RunState` has the ten documented lifecycle values. `validate_transition(current, target)` is pure and raises `InvalidStateTransitionError` for disallowed edges. `transition_state(record, target)` returns a new `RunStateRecord` with version incremented; it does not persist state or schedule work. Terminal states are `COMPLETED`, `FAILED`, `CANCELLED`.

Events have stable names such as `run.created`, `model.request_created`, `tool.execution_completed`, and `run.failed`. Each has schema version, event/session/run IDs, per-run sequence, aware timestamp, and typed event-specific payload. `serialize_event`/`deserialize_event` validate the discriminated union. Consumers must append in sequence; no replay engine or crash recovery is provided.

## Storage

`Storage` is an async protocol for session create/get, message append/list, and event append/list by session/run/cursor. `InMemoryStorage` is process-local and non-durable, uses an async lock, enforces unique sessions/event IDs, run/session association, and contiguous per-run event sequence. It copies values at its boundary so mutating caller-owned messages or returned snapshots cannot silently alter stored data. Missing records and conflicts have typed errors. It has no PostgreSQL, Prisma, file-system, or external-service dependency.

## Errors and logging

Public exceptions derive from `YantraError` and include configuration, provider timeout/capability, tool validation/registration/lookup, state transition, storage conflict/not-found, and budget errors. Error messages redact common key/token/password/secret assignment patterns and bearer strings; callers must still avoid placing sensitive payloads in messages.

`get_logger(name, level=..., **context)` returns a standard-library structured logging facade under `yantra.<name>`. Named fields are attached as `LogRecord` extras. Sensitive field names and common secret patterns are redacted. `exception()` intentionally omits raw tracebacks because exception text may contain secrets. Importing the package does not configure handlers or root logging. This helper is not a substitute for comprehensive secret-aware telemetry review.

## Limitations

No full agent execution loop, tool execution/authorization, skill system, CLI, database integration, Redis, pgvector, distributed coordination, or production support is implemented. Live provider behavior, Windows compatibility, and production network controls are not verified. Future milestones may evolve contracts under the compatibility policy; `0.1.0` is not a stable API promise.
