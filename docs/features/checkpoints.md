# Checkpoints

## Overview
Checkpoints capture a safe, versioned resume boundary for durable runs.
## Motivation
Reduce restart loss without implying arbitrary process snapshots or exactly-once side effects.
## Functional requirements
1. `YANTRA-CHECKPOINT-001`: Snapshot only at declared safe boundaries with schema/runtime version and integrity digest.
2. `YANTRA-CHECKPOINT-002`: Validate compatibility and reconcile in-flight external operations before resume.
3. `YANTRA-CHECKPOINT-003`: Link resumed attempt to prior run and preserve terminal history.
## Non-functional requirements
Security: encrypt/classify content. Performance: bounded snapshot size. Reliability: atomic checkpoint pointer. Scalability: retention. Maintainability: explicit migrations.
## Architecture
Kernel creates snapshot; persistence service commits snapshot with expected state/version; recovery coordinator validates it.
## Data flow
Safe boundary -> serialize allowlisted state -> persist -> restart -> verify digest/schema -> reconcile -> resume linked attempt.
## Interfaces
Checkpoint contract; no Python object/pickle serialization.
## Persistence
PostgreSQL metadata and bounded JSONB or artifact reference.
## Configuration
Checkpoint triggers, size, retention, schema compatibility.
## Security
No secrets/raw credentials; protect prompts and tool data by classification.
## Error handling
Invalid/incompatible checkpoint blocks resume and reports typed error; never silently discard required state.
## Observability
Checkpoint sequence, size, schema, resume decision, reconciliation outcomes.
## Testing
Round trip, corruption, crash windows, old schema, ambiguous side effect recovery.
## Acceptance criteria
Crash tests at every checkpoint boundary produce either a valid resume or explicit blocked recovery; no pickle or secret is present; incompatible versions are rejected.
## Dependencies
Persistence service, events, run state machine.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Snapshot granularity and migration support window.
