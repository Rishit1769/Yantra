# Recovery

## Overview
Reconciles persisted execution facts after process, worker, provider, or persistence failure and resumes only from compatible safe boundaries.
## Motivation
Durability is useful only if uncertainty and partial effects are represented accurately.
## Functional requirements
1. `YANTRA-RECOVERY-001`: Recover state using checkpoint schema, state version, event sequence, and worker fencing token.
2. `YANTRA-RECOVERY-002`: Mark calls with unknown outcome as ambiguous and require tool-specific reconciliation before retry.
3. `YANTRA-RECOVERY-003`: Link recovery attempt to prior run and never mutate a terminal record into active state.
## Non-functional requirements
Security: recovery actor audited. Performance: bounded scans. Reliability: idempotent reconciliation. Scalability: lease recovery. Maintainability: explicit migration compatibility.
## Architecture
Recovery coordinator reads durable run/event/checkpoint and queries idempotency/reconciliation ports.
## Data flow
Detect abandoned lease -> compare versions -> classify in-flight work -> reconcile -> resume/hold/fail with audit.
## Interfaces
Recovery policy and tool reconciliation protocol.
## Persistence
Checkpoint, state, events, attempt records, leases, linked recovery IDs.
## Configuration
Lease expiry, scan interval, retry ceiling, manual-review thresholds.
## Security
No automatic credential escalation or unsafe rerun; cross-tenant scope enforced.
## Error handling
Incompatible checkpoint or unresolved irreversible effect pauses for operator decision.
## Observability
Recovery reason, reconciliation decision, lease/fencing IDs, elapsed time.
## Testing
Crash windows, stale workers, service outage, ambiguous effect, duplicate delivery.
## Acceptance criteria
Injected crash at each operation boundary never reports an unknown effect as confirmed; stale worker writes fail; recovery produces bounded and auditable resolution.
## Dependencies
Persistence, checkpoint, idempotency, distributed lease if workers enabled.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Automatic recovery policy for read-only provider/tool calls.
