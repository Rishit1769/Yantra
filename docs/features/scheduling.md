# Scheduling

## Overview
Schedules bounded tasks/workflows locally or through future distributed workers.
## Motivation
Long-running and concurrent work needs backpressure and explicit resource allocation.
## Functional requirements
1. `YANTRA-SCHED-001`: Enforce queue, worker, tenant, and global concurrency limits.
2. `YANTRA-SCHED-002`: Use expiring leases and fencing tokens for distributed ownership.
3. `YANTRA-SCHED-003`: Propagate deadline/cancellation and recover expired leases without duplicate untracked effects.
## Non-functional requirements
Security: tenant-aware fairness. Performance: measured queue overhead. Reliability: lease recovery. Scalability: bounded backlog. Maintainability: interchangeable local/distributed scheduler.
## Architecture
Local asyncio scheduler first; future worker queue with PostgreSQL/Redis only if justified.
## Data flow
Enqueue -> validate budget -> fair dispatch -> lease -> execute -> acknowledge state -> recover expired lease.
## Interfaces
Scheduler port with enqueue/acquire/renew/complete/cancel operations.
## Persistence
Durable task state and lease/fencing metadata; transient queue may be rebuilt.
## Configuration
Concurrency, queue size, lease duration, fairness, retry ceilings.
## Security
Authenticate worker identity and scope task payload; no secrets in queue metadata.
## Error handling
Expired lease triggers reconciliation; poison task quarantined; backpressure visible.
## Observability
Queue depth, wait, lease churn, worker availability, retries.
## Testing
Worker loss, duplicate delivery, fencing, starvation, backpressure, cancellation.
## Acceptance criteria
Stale lease holder cannot commit; configured concurrency never exceeded; backlog is bounded or admission rejected; recovery is auditable.
## Dependencies
Runtime, durable persistence; optional distributed coordination.
## Priority
P2.
## Implementation status
Proposed.
## Open questions
Redis vs PostgreSQL lease/queue mechanism after workload evidence.
