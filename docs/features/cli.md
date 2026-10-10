# CLI

## Overview
Typer/Rich CLI is a developer convenience over public SDK/service APIs.
## Motivation
Project bootstrap, local execution, validation, inspection, and evaluation should be reproducible.
## Functional requirements
1. `YANTRA-CLI-001`: Proposed commands include project init, run agent, providers list, skills list/validate, sessions inspect, traces view, eval run, config check.
2. `YANTRA-CLI-002`: Clearly distinguish local non-durable mode from configured durable service.
3. `YANTRA-CLI-003`: Never print secrets; require confirmation for destructive operations.
## Non-functional requirements
Security: safe output and auth. Performance: streaming output. Reliability: actionable exit codes. Scalability: paginated results. Maintainability: CLI calls public APIs only.
## Architecture
Typer command layer, Rich presentation, SDK/client services.
## Data flow
Parse -> validate config/auth -> invoke API -> render redacted result/events -> exit code.
## Interfaces
Command names are concepts only; none currently work.
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
Each released command has help and tests; proposed commands are not documented as operational until implemented; secret canaries absent from terminal output.
## Dependencies
SDK; optional service client.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Configuration profile format and command compatibility policy.
