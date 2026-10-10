# OpenAI Integration (YANTRA-002)

An OpenAI Responses API adapter is implemented with normalized completion, streaming, tool calls, usage, model listing, credential validation, and typed HTTP errors. Current protocol tests use mocked HTTP only; live API/model compatibility and account access are unverified. Capability declarations may be overridden per model; unknown support is not assumed. Fallback is explicit and policy constrained. See [provider contract](../specifications/model-provider-contract.md).
