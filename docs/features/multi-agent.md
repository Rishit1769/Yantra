# Multi-Agent

## Overview
Coordinates bounded child agent tasks and validated result aggregation.
## Motivation
Some work decomposes into independent tasks but spawning and communication must be predictable.
## Functional requirements
1. `YANTRA-MULTI-001`: Enforce maximum depth, children, concurrency, deadline, and aggregate budget.
2. `YANTRA-MULTI-002`: Require structured task inputs/outputs and explicit shared-context grants.
3. `YANTRA-MULTI-003`: Define failure, cancellation, aggregation, and human-intervention policy per parent.
4. `YANTRA-MULTI-004`: Reject cyclic dependencies and prevent unbounded spawning.
## Non-functional requirements
Security: child receives least privilege. Performance: bounded scheduler overhead. Reliability: lease/recovery-aware tasks. Scalability: queue backpressure. Maintainability: deterministic scheduler contract.
## Architecture
Parent run, task graph, scheduler, isolated child contexts and result aggregator.
## Data flow
Decompose -> validate graph/budgets -> schedule ready nodes -> collect typed results -> aggregate -> parent continuation.
## Interfaces
Task graph and delegation API; see [workflow schema](../specifications/workflow-schema.md).
## Persistence
Parent/child edges, budgets, statuses, messages, outcomes, and events.
## Configuration
Depth, fanout, concurrency, total tokens/cost/deadline, failure strategy.
## Security
No implicit shared secret/context; child tool grants cannot exceed parent policy.
## Error handling
Explicit fail-fast/collect/compensate/human policies; cancellation propagates.
## Observability
Task DAG, queue time, resource allocation, parent-child correlation.
## Testing
Deadlock/cycle, budget conservation, worker loss, cancellation, partial results, tenant boundaries.
## Acceptance criteria
Configured limits cannot be exceeded under concurrent adversarial delegation; static cycles rejected; every child has parent and bounded budget; cancellation reaches all descendants or marks unresolved.
## Dependencies
Runtime state machine, persistence, policy, scheduler.
## Priority
P2.
## Implementation status
Proposed.
## Open questions
Whether child agents have separate sessions or task-scoped context by default.
