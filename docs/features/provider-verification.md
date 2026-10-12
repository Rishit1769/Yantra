# Provider Verification Matrix (YANTRA-002)

This matrix reports evidence for the adapter paths in the current registry. A capability being implemented does not mean a provider account, model, or deployment supports it.

## Status Definitions

- **IMPLEMENTED:** Adapter code for the path exists; this does not by itself imply a passing protocol test.
- **MOCK VERIFIED:** The adapter path has test coverage with fixtures or mocked transports. This does not prove upstream acceptance or entitlement.
- **LIVE VERIFIED:** A non-mock provider request was reported as successful for the exact scope listed. Evidence labeled user-reported was not independently repeated for this release candidate.
- **UNKNOWN:** Available evidence does not establish support or account/model access. The gateway does not infer support from protocol similarity.
- **UNSUPPORTED:** The adapter rejects or does not provide the capability in the stated configuration.

## Capability Evidence

| Provider / scope | Catalog | Non-streaming completion | Streaming completion | Tool proposal serialization / normalization | Structured output | Credential / access check | Usage | Reasoning metadata |
|---|---|---|---|---|---|---|---|---|
| OpenAI Responses | MOCK VERIFIED | MOCK VERIFIED | MOCK VERIFIED | MOCK VERIFIED | IMPLEMENTED; model declaration / live support UNKNOWN | MOCK VERIFIED; live key and model access UNKNOWN | MOCK VERIFIED | UNKNOWN; reasoning request options do not prove a normalized user-facing result |
| Anthropic Messages | IMPLEMENTED; mocked adapter paths | MOCK VERIFIED | MOCK VERIFIED | MOCK VERIFIED | IMPLEMENTED; model capability and live support UNKNOWN | MOCK VERIFIED; live key and model access UNKNOWN | MOCK VERIFIED | IMPLEMENTED for private provider blocks / thinking deltas; live behavior UNKNOWN |
| Google Gemini | MOCK VERIFIED | MOCK VERIFIED | MOCK VERIFIED | MOCK VERIFIED | IMPLEMENTED; model capability and live support UNKNOWN | MOCK VERIFIED; live key and model access UNKNOWN | MOCK VERIFIED | IMPLEMENTED as provider-qualified thought metadata; live behavior UNKNOWN |
| DeepSeek Chat Completions | IMPLEMENTED; mocked adapter paths | MOCK VERIFIED | MOCK VERIFIED | MOCK VERIFIED | UNSUPPORTED by default adapter configuration | MOCK VERIFIED; live key and model access UNKNOWN | MOCK VERIFIED | MOCK VERIFIED for `reasoning_content`; model-specific live behavior UNKNOWN |
| Ollama | MOCK VERIFIED | MOCK VERIFIED | MOCK VERIFIED | MOCK VERIFIED; gateway capability gate applies | IMPLEMENTED; per-model support UNKNOWN unless declared | MOCK VERIFIED; no key required for standard local Ollama; live server access UNKNOWN | MOCK VERIFIED | UNKNOWN |
| OpenRouter | MOCK VERIFIED | MOCK VERIFIED | MOCK VERIFIED | MOCK VERIFIED; model support UNKNOWN | IMPLEMENTED; catalog/model support UNKNOWN | MOCK VERIFIED for key endpoint behavior; live key/model access UNKNOWN | MOCK VERIFIED | UNKNOWN; upstream/model-dependent |
| OpenCode Zen | MOCK VERIFIED | MOCK VERIFIED through protocol delegates | MOCK VERIFIED through protocol delegates | MOCK VERIFIED in delegate wire handling; model capability UNKNOWN absent declaration | UNKNOWN absent a positive model declaration | Public catalog success does not validate the credential; live access UNKNOWN | MOCK VERIFIED through delegates | UNKNOWN outside the specific Go evidence below |
| OpenCode Go, general | MOCK VERIFIED | MOCK VERIFIED through protocol delegates | MOCK VERIFIED through protocol delegates | MOCK VERIFIED for serialization/normalization; model capability UNKNOWN | UNKNOWN absent a positive model declaration | Public catalog success does not validate key, workspace, region, or entitlement | MOCK VERIFIED through delegates | Protocol/model-dependent; general live behavior UNKNOWN |
| OpenCode Go `deepseek-v4.1-flash` | IMPLEMENTED; live catalog result not reported | LIVE VERIFIED (user-reported; not rerun) | LIVE VERIFIED with visible text (user-reported; not rerun) | MOCK VERIFIED for serialization, response normalization, and stream deltas; live model tool-call support UNKNOWN | UNKNOWN | LIVE VERIFIED: requests were accepted at the reported time (user-reported; not rerun); no future entitlement guarantee | LIVE VERIFIED (user-reported; not rerun) | LIVE VERIFIED (user-reported preservation as private metadata; not rerun) |
| Generic OpenAI Chat Completions-compatible endpoint | MOCK VERIFIED for the tested catalog shape | MOCK VERIFIED | MOCK VERIFIED | MOCK VERIFIED for the tested compatible subset; server/model support UNKNOWN | IMPLEMENTED as configurable `json_schema` mapping; endpoint support UNKNOWN | MOCK VERIFIED for credential request paths; live key/access UNKNOWN | MOCK VERIFIED when returned by fixtures; endpoint support UNKNOWN | UNKNOWN unless endpoint fields are explicitly normalized |

All live evidence in this matrix is restricted to the exact OpenCode Go model row and is user-reported. No live catalog lookup, provider request, or billable inference was made during YANTRA-002-R03. Tool-call support for `opencode-go/deepseek-v4.1-flash` remains **UNKNOWN**; the capability gate remains fail-closed. Wire-format handling is not live model eligibility.

The provider registry is explicit and empty by default; applications register adapter instances themselves. The smoke CLI registers only Ollama and OpenCode Zen/Go. The matrix describes adapters available from `yantra.providers.adapters`, not providers automatically configured by a new `ModelGateway`.

## Limits

- Catalog parsing and a successful catalog response do not establish account access or inference entitlement.
- Credential validation methods vary. In particular, a public OpenCode catalog is not an authenticated key check.
- Capability declarations are deployment/model-specific. Missing values remain unknown; an application override must be explicit and scoped.
- Generic compatibility means the tested OpenAI Chat Completions subset, not arbitrary protocols or full OpenAI API parity.
- Tool outputs are proposals. YANTRA does not execute them in the provider adapter or smoke CLI.
- Tests use mocked transports. The matrix does not claim production readiness, provider parity, or cross-platform verification.

See the [provider contract](../specifications/model-provider-contract.md), [gateway architecture](../architecture/model-gateway.md), and [tests](../../tests/unit/test_provider_adapters.py) for implementation details.
