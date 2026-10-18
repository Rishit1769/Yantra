# Changelog

## v0.2.0 (unreleased candidate)

- RR-003 verified the configured Ubuntu/macOS/Windows × Python 3.12/3.13/3.14 Actions matrix (all nine jobs passed on commit `2f07ec9`; run 39114896871). RR-004 adds fresh packaging, clean installation, external-consumer, and local compatibility evidence; see the current [RR-004 audit](docs/development/yantra-release-readiness-rr004.md) for the release recommendation and remaining exact-commit gate.
- Adopted Apache License 2.0 for the project, declared the SPDX license expression, and included the license in Python distributions.
- Resolved the audited pytest development-dependency advisory, aligned provider User-Agent versions with installed package metadata, removed the unverified OS-independent classifier, and clarified that the generic endpoint supports OpenAI Chat Completions compatibility rather than arbitrary protocols.
- Implemented the YANTRA-001 Python package foundation: typed core contracts, deterministic mock provider, tool registry, runtime state transitions, events, in-memory storage, structured logging, tests, and cross-platform CI configuration.
- Implemented the YANTRA-002 model gateway foundation with provider adapters, normalized streaming, explicit routing, secure credential references, and mocked HTTP tests. Live provider compatibility remains unverified.
- Implemented the YANTRA-003 bounded asynchronous agent execution loop with validated model/tool cycles, per-run allowlists, cancellation, usage/cost accounting, and sanitized diagnostics. Budgets are not hard spending ceilings.
- Implemented the YANTRA-004 secure tool path with exact-scope authorization, trusted host-injected approvals, engine-bound single-use dispatch authorization, and opt-in fixed-handler worker subprocesses. The subprocess is not an OS sandbox; see the security guide for the full trust boundary.
- Added the YANTRA-002-V01 `yantra-smoke` developer CLI for offline mocks and opt-in live Ollama/OpenCode gateway checks. It does not execute tools or persist credentials/request data.
- Fixed OpenCode Go smoke requests to include a conversation session ID and use `max_tokens` for Chat Completions; provider errors now expose safe HTTP diagnostics without response bodies.
- Added YANTRA-002-V03 sanitized OpenCode Go request-shape diagnostics for failed inference, including method, endpoint path, body field names, and header names only; no live calls were made.
- Added YANTRA-002-V04 response-shape diagnostics for Chat Completions and preserved valid reasoning-only assistant responses as private provider metadata without fabricating visible text.
- Added YANTRA-002-V05 smoke output-token budget controls, truncation-aware outcome classification, and provider-specific budget display without automatic retries.
- Investigated YANTRA-002-V06 OpenCode Go tool calling; retained the capability gate because official evidence does not establish per-model tool support for `deepseek-v4.1-flash`. Added mocked gate, wire-format, and normalization coverage.
- Added Python 3.12+ packaging/tooling, uv lockfile, cross-platform CI configuration, and developer/API documentation. Hosted CI passed for all nine configured OS/Python combinations in RR-003; see RR-004 for evidence applicable to the current candidate.
- Added the initial architecture, contract, security, database, feature, research, and roadmap documentation foundation.
- General-purpose agent CLI, durable storage, skills runtime, and production deployment remain unimplemented. Live provider/model compatibility remains limited to the exact evidence in the provider matrix; mocked adapter tests do not establish broad live support.
