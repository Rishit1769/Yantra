# CLI

## Overview
The initial developer CLI is a small standard-library `argparse` smoke runner over public YANTRA-002 gateway APIs. A broader Typer/Rich CLI remains a future possibility, not a dependency of this feature.
## Motivation
Project bootstrap, local execution, validation, inspection, and evaluation should be reproducible.
## Functional requirements
1. `YANTRA-CLI-001`: `yantra-smoke` provides explicit offline mock, provider listing, live catalog, and manually selected completion/stream commands. Broader project/runtime commands remain proposed.
2. `YANTRA-CLI-002`: Clearly distinguish local non-durable mode from configured durable service.
3. `YANTRA-CLI-003`: Never print secrets; require confirmation for destructive operations.
## Non-functional requirements
Security: safe output and auth. Performance: streaming output. Reliability: actionable exit codes. Scalability: paginated results. Maintainability: CLI calls public APIs only.
## Architecture
Standard-library `argparse`, public provider registry/catalog/gateway, normalized output.
## Data flow
Parse -> validate config/auth -> invoke API -> render redacted result/events -> exit code.
## Interfaces
See the [gateway smoke-test guide](../development/smoke-testing.md) for commands and platform instructions. The smoke CLI is implemented; other command concepts in this page are not.
## Persistence
CLI itself does not own database state.
## Configuration
Explicit profile/config location and environment secret references.
## Security
Redaction, least privilege, confirmation and path confinement.
## Error handling
Stable nonzero exit codes, no stack trace by default, correlation ID for diagnostics.
## Observability
Command operation IDs and optional debug logs with redaction.
## Testing
CLI runner tests, secret-canary output, destructive confirmation, exit-code contract.
## Acceptance criteria
The implemented smoke commands have help and tests; live inference is explicitly opted into; proposed commands are not operational; secret canaries are absent from terminal output.
## Dependencies
Python SDK APIs; no additional runtime dependency.
## Priority
P1.
## Implementation status
YANTRA-002-V01 implements `yantra-smoke` with `argparse`, offline mock completion/stream/tool proposals, provider status, live model catalogs, and live completion/stream/tool-call normalization for Ollama and OpenCode Zen/Go. OpenCode inference requires `--allow-billable`. The CLI reads credential references through `CredentialManager`, writes no credentials or request data, and redacts known credential values before output. Broader agent, skills, session, trace, and evaluation commands remain unimplemented.
## Open questions
Configuration profile format and command compatibility policy.
