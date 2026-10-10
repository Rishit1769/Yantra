# Workflows

## Overview
Runs versioned deterministic DAGs containing tools, agent tasks, branches, joins, approval, and compensation nodes.
## Motivation
Repeatable process control should not depend on an agent choosing each next step.
## Functional requirements
1. `YANTRA-WORKFLOW-001`: Validate acyclic graph, schemas, bounded retries, and budget before execution.
2. `YANTRA-WORKFLOW-002`: Pin immutable workflow version for each execution.
3. `YANTRA-WORKFLOW-003`: Persist node outcomes/checkpoints and support safe resume.
4. `YANTRA-WORKFLOW-004`: Execute declared compensation only under explicit policy and record outcome.
## Non-functional requirements
Security: per-node permissions. Performance: bounded parallelism. Reliability: resumable node state. Scalability: backpressure. Maintainability: schema versioning.
## Architecture
Workflow scheduler invokes deterministic nodes and bounded agent runs; model loop is one node type, not the workflow controller.
## Data flow
Validate graph -> schedule ready nodes -> record outputs -> branch/join -> pause/compensate/complete.
## Interfaces
Versioned [workflow schema](../specifications/workflow-schema.md) and async engine API.
## Persistence
Definition version, execution, node state, retries, checkpoints, events, compensation.
## Configuration
Concurrency, retries, deadlines, budgets, approval, resume and retention.
## Security
No model-controlled graph mutation; every node's effect checked.
## Error handling
Node failure follows declared policy; retries bounded; compensation is best-effort and not rollback guarantee.
## Observability
Graph timeline, node states, retries, branch decisions, approval and compensation events.
## Testing
Graph validation, determinism, crash/resume, retries, compensation failure, concurrency.
## Acceptance criteria
Cycle and unbounded policies fail validation; fixed inputs/pinned versions produce same scheduling decisions; crash tests resume without rerunning confirmed completed nodes; ambiguous effects are surfaced.
## Dependencies
Runtime, task scheduler, persistence, approval and checkpoint contracts.
## Priority
P2.
## Implementation status
Proposed.
## Open questions
Workflow DSL encoding and compensation semantics.
