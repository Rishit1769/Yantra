# Model Providers

## Overview
Adapters normalize distinct inference APIs into provider-neutral requests, responses, streams, capabilities, usage, and errors.
## Motivation
Avoid vendor lock-in without pretending provider capabilities are identical.
## Functional requirements
1. `YANTRA-PROVIDER-001`: Each adapter declares deployment-level capability support and provenance.
2. `YANTRA-PROVIDER-002`: Normalize streaming, tool proposals, structured output, usage, and typed errors without fabricating absent fields.
3. `YANTRA-PROVIDER-003`: Resolve credentials from secret sources and redact them from every output channel.
4. `YANTRA-PROVIDER-004`: Enforce deadlines, cancellation, and retry classification.
## Non-functional requirements
Security: TLS and secret isolation. Performance: bounded streaming buffers. Reliability: normalized transient/permanent errors. Scalability: adapter connection limits. Maintainability: contract conformance suite.
## Architecture
Provider adapter behind the [gateway](../architecture/model-gateway.md); candidate OpenAI, Anthropic, Gemini, DeepSeek, Ollama and compatible endpoints.
## Data flow
Capability check -> auth resolution -> normalized request -> provider call -> stream/result normalization -> usage/error event.
## Interfaces
Async `ModelProvider` Protocol; see [contract](../specifications/model-provider-contract.md).
## Persistence
Persist provider/model identity and usage metadata only as configured; no API keys or raw payload by default.
## Configuration
Endpoint, model, secret reference, capability requirements, timeout, rate limits, and optional pricing metadata.
## Security
Provider is an external trust boundary; minimize transmitted context and enforce approved endpoints/data residency.
## Error handling
Authentication, rate-limit, unavailable, timeout, invalid request, refusal, unsupported capability, unknown; fallback explicit.
## Observability
Provider/model IDs, latency, request IDs, token usage when returned, retries and route decisions; redact content.
## Testing
Adapter contract tests, mocked wire fixtures, malformed stream/error tests, timeout/cancel tests, optional live tests separated.
## Acceptance criteria
Each released adapter passes shared fixtures; unsupported capability fails before network call; missing usage remains null; secret canary is absent from logs/traces/errors.
## Dependencies
HTTPX, runtime contracts, secret source.
## Priority
P0.
## Implementation status
YANTRA-002 implements HTTPX adapters for OpenAI, Anthropic, Gemini, DeepSeek, Ollama, OpenRouter, OpenCode Zen/Go, and a configurable OpenAI Chat Completions-compatible subset. Automated protocol tests use mocked transports. The only reported live evidence is specific to OpenCode Go `deepseek-v4.1-flash` and is not independently rerun; its live tool-call support remains unknown and fail-closed. See the [provider verification matrix](provider-verification.md) for per-capability evidence. Adapter implementation does not imply provider/model entitlement or parity. This is not a production-readiness claim.
## Open questions
Live compatibility matrix and ongoing protocol-version verification; provider-specific structured-output semantics and capability metadata may vary by model/deployment.
