# Core Runtime API (YANTRA-001–YANTRA-004-V01)

**Status:** YANTRA-001 contracts and the YANTRA-002 model gateway have local test coverage on macOS. This page also documents the experimental YANTRA-003 bounded execution API, engineering-accepted on its feature branch but not included in the unreleased `0.2.0` package. YANTRA-003 authorizes tools through an explicit per-run name allowlist (empty means deny all); YANTRA-004-V01 adds a focused exact-match scope policy for declared requirements on its feature branch. That addition is not included in `0.2.0`, is not a general policy language or sandbox, and does not imply release approval. Usage and cost limits are best-effort accounting, not a hard spending ceiling. The configured 3-OS/3-Python GitHub Actions matrix has not run on hosted CI. Live provider evidence is limited to user-reported OpenCode Go results for one model and was not rerun for v0.2.0. Durable persistence and a runtime scheduler are not provided.

## Package and installation

Package import root is `yantra`; source uses `src/yantra`. Development setup: `uv sync --all-groups`. The package requires Python 3.12+ and Pydantic v2. The release-candidate version is `0.2.0`, sourced from `src/yantra/_version.py`. No package-index release is published. YANTRA is licensed under Apache-2.0; see [LICENSE](../../LICENSE).

## Agent and budget

`yantra.core.agent.AgentConfig` is a frozen Pydantic model containing `agent_id`, `name`, `description`, `system_instructions`, `provider_id`, `model_id`, `tool_references`, `execution_limits`, and JSON-compatible metadata. IDs are restricted to a bounded identifier syntax. Tool references must be non-empty and unique. Agent configuration is declarative; it cannot start a run.

`yantra.core.budgets.ExecutionBudget` validates finite positive wall time, call/step/token bounds, and optional positive cost. `max_model_calls` cannot exceed `max_steps`. The YANTRA-003 runtime uses equivalent finite limits through `yantra.runtime.AgentRunConfig` and enforces them for each run.

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

Provider adapters are implemented for OpenAI, Anthropic, Gemini, DeepSeek, Ollama, OpenRouter, OpenCode Zen/Go, and a configurable OpenAI Chat Completions-compatible subset. Automated protocol tests use mocked transports. The only reported live evidence is narrowly scoped to OpenCode Go `deepseek-v4.1-flash`; see the [provider verification matrix](../features/provider-verification.md). Cost enforcement is a preflight estimate based on explicit input/output token bounds and provider pricing metadata, not a guaranteed billing cap. Credential smoke tests can incur charges and require explicit opt-in.

## Tools and registry

`ToolDefinition` combines name/description, Pydantic input and optional output model classes, callable, explicit sync/async mode, validated required permission scopes, risk classification, side-effect classification, and optional timeout. It validates input/output without echoing rejected values. `ToolRegistry` implements `register`, `get`, name-sorted `list`, `unregister`, and deterministic `export_provider_schemas`.

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
    permission_scopes=frozenset({"demo.read"}),
    side_effect=SideEffect.READ_ONLY,
)
registry = ToolRegistry()
registry.register(tool)
schema = registry.export_provider_schemas()[0]
```

`ToolDefinition.permission_scopes` declares required logical scopes evaluated by the YANTRA-004-V01 tool policy layer. Scoped tools require explicit per-run scope grants in addition to the independent `tool_names` allowlist. Existing unscoped tools retain the explicit `allow_legacy_unscoped_tools` compatibility mode, which does not bypass the name allowlist. Registration and schema export never grant permission. These checks are in-process logical authorization, not a sandbox or OS-level filesystem/network enforcement. See [secure tool runtime](../security/secure-tool-runtime.md).

## States and events

`RunState` has the ten documented lifecycle values. `validate_transition(current, target)` is pure and raises `InvalidStateTransitionError` for disallowed edges. `transition_state(record, target)` returns a new `RunStateRecord` with version incremented; it does not persist state or schedule work. Terminal states are `COMPLETED`, `FAILED`, `CANCELLED`.

Events have stable names such as `run.created`, `model.request_created`, `tool.execution_completed`, and `run.failed`. Each has schema version, event/session/run IDs, per-run sequence, aware timestamp, and typed event-specific payload. `serialize_event`/`deserialize_event` validate the discriminated union. Consumers must append in sequence; no replay engine or crash recovery is provided.

## Storage

`Storage` is an async protocol for session create/get, message append/list, and event append/list by session/run/cursor. `InMemoryStorage` is process-local and non-durable, uses an async lock, enforces unique sessions/event IDs, run/session association, and contiguous per-run event sequence. It copies values at its boundary so mutating caller-owned messages or returned snapshots cannot silently alter stored data. Missing records and conflicts have typed errors. It has no PostgreSQL, Prisma, file-system, or external-service dependency.

## Errors and logging

Public exceptions derive from `YantraError` and include configuration, provider timeout/capability, tool validation/registration/lookup, state transition, storage conflict/not-found, and budget errors. Error messages redact common key/token/password/secret assignment patterns and bearer strings; callers must still avoid placing sensitive payloads in messages.

`get_logger(name, level=..., **context)` returns a standard-library structured logging facade under `yantra.<name>`. Named fields are attached as `LogRecord` extras. Sensitive field names and common secret patterns are redacted. `exception()` intentionally omits raw tracebacks because exception text may contain secrets. Importing the package does not configure handlers or root logging. This helper is not a substitute for comprehensive secret-aware telemetry review.

## YANTRA-003/004-V01 agent execution and tool policy

`yantra.runtime.AgentExecutionEngine` accepts an existing `ModelGateway` and
`ToolRegistry`, then runs a bounded asynchronous model/tool loop. It preserves
message order and call IDs, executes registered tools sequentially, and returns
an immutable `AgentRunResult` with terminal state, termination reason, ordered
steps, tool observations, known usage/cost, and sanitized trace entries.

`CancellationToken` provides explicit cooperative cancellation. External task
cancellation propagates as normal `asyncio.CancelledError`. Tool failures are
structured observations; duplicate call IDs and malformed empty responses fail
the run. Tool proposals are processed sequentially, allowlists are enforced
when advertising schemas and independently at execution, and an empty allowlist
denies all tools. Unknown allowlist names do not grant access. Over-budget
batches are rejected atomically. When a `PolicyContext` is provided, each
declared permission scope is enforced as an exact-match grant requirement.
Unscoped tools follow the explicit legacy compatibility mode described in the
[secure tool runtime](../security/secure-tool-runtime.md). Token budgets pass the remaining budget as
the provider output-token limit where supported, then use actual post-response
usage to stop subsequent work. This does not cap total tokens: prompt tokens
are not estimated and provider behavior can vary. Cost budgets use
post-response accounting; gateway routing policy may separately preflight when
pricing and token bounds are available, but there is no guaranteed per-run
billing ceiling. An admitted request may exceed the configured budget before
usage is observed. Missing required accounting fails closed before further
work, but only after the response reveals the missing data. Gateway and tool
timeouts preserve completed progress. Sync tool
work uses a worker thread and cannot be forcibly stopped by asyncio
cancellation. The engine does not add shell, filesystem, browser, MCP,
persistence, or authorization-policy capabilities. See [agent execution engine](../architecture/agent-execution-engine.md).
`yantra.runtime.format_run_result(result)` formats the summary and sanitized
trace for display without including conversation bodies, raw model-supplied
tool names or call IDs, tool arguments, result payloads, exception text, or
provider reasoning. Tool results use local `tool[n]` indices. Recognized
structured error categories are shown; malformed or unrecognized categories
are omitted. Structured result and trace objects retain correlation IDs. The
complete deterministic example is in the [agent runtime
quickstart](../guides/agent-quickstart.md).

## Limitations

YANTRA-003 provides a local bounded loop and controlled registry executor, but
there is no durable persistence, general-purpose authorization policy engine, skill system,
general-purpose CLI, Redis, pgvector, distributed coordination, or production
support. Hosted CI execution, Windows compatibility, and production deployment
controls are not verified. YANTRA is pre-1.0; `0.2.0` does not promise a stable
API. See the [release audit](../releases/v0.2.0-release-audit.md).
