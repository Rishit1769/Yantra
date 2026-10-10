# OpenAI Integration (Design)

Candidate provider adapter only; no integration is implemented. The adapter must query/configure deployment-specific capabilities, normalize streaming/tool calls/structured output and usage, enforce HTTPX deadlines, use secret references, and map provider errors. Feature availability and semantics may change by API/model; tests should use captured non-secret fixtures and optional live tests isolated from CI. Fallback is explicit and policy constrained. See [provider contract](../specifications/model-provider-contract.md).
