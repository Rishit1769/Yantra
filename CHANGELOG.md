# Changelog

## Unreleased

- Implemented the YANTRA-001 Python package foundation: typed core contracts, deterministic mock provider, tool registry, runtime state transitions, events, in-memory storage, structured logging, tests, and cross-platform CI configuration.
- Implemented the YANTRA-002 model gateway foundation with provider adapters, normalized streaming, explicit routing, secure credential references, and mocked HTTP tests. Live provider compatibility remains unverified.
- Added the YANTRA-002-V01 `yantra-smoke` developer CLI for offline mocks and opt-in live Ollama/OpenCode gateway checks. It does not execute tools or persist credentials/request data.
- Fixed OpenCode Go smoke requests to include a conversation session ID and use `max_tokens` for Chat Completions; provider errors now expose safe HTTP diagnostics without response bodies.
- Added YANTRA-002-V03 sanitized OpenCode Go request-shape diagnostics for failed inference, including method, endpoint path, body field names, and header names only; no live calls were made.
- Added YANTRA-002-V04 response-shape diagnostics for Chat Completions and preserved valid reasoning-only assistant responses as private provider metadata without fabricating visible text.
- Added Python 3.12+ packaging/tooling, uv lockfile, macOS/Windows CI workflow, and developer/API documentation. CI has not yet run on GitHub.
- Added the initial architecture, contract, security, database, feature, research, and roadmap documentation foundation.
- The agent execution loop, general-purpose CLI, persistent storage, Windows verification, live provider compatibility, and production support remain unimplemented or unverified.
