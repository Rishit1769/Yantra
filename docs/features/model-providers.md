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
YANTRA-002 implements the normalized provider protocol and HTTPX adapters for OpenAI, Anthropic, Gemini, DeepSeek, Ollama, OpenRouter, OpenCode Zen/Go, and configurable OpenAI Chat Completions-compatible endpoints. Completion, streaming normalization, catalog discovery where supported, credential validation, typed errors with bounded HTTP diagnostics, and mocked HTTP fixtures are present. OpenCode Go model listings do not report per-model tool capabilities, so tool calling remains unknown and fails closed unless an integrating application supplies an explicit model-scoped declaration. Its Chat Completions route forwards tool fields, but V06 found no official model-specific confirmation for `deepseek-v4.1-flash`; the smoke CLI has no capability override. Tests use mock transports only: live provider compatibility, current model catalogs, account entitlements, and paid inference are not verified. OpenCode protocol support can require operator overrides; unknown capabilities fail closed. This is not a production-readiness claim.
## Open questions
Live compatibility matrix and ongoing protocol-version verification; provider-specific structured-output semantics and capability metadata may vary by model/deployment.
