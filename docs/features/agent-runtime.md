# Agent Runtime

## Overview
The Python async kernel coordinates a bounded model-driven execution loop, tool policy, context, state, and events.
## Motivation
Applications need explicit ownership of execution semantics instead of vendor SDK loops with hidden policies.
## Functional requirements
1. `YANTRA-RUNTIME-001`: Validate immutable agent definition, identity context, and finite budgets before creating a run.
2. `YANTRA-RUNTIME-002`: Enforce the state machine and single-writer/version invariant for every transition.
3. `YANTRA-RUNTIME-003`: Normalize model/tool observations and terminate or suspend deterministically on final output, approval, cancellation, failure, or budget exhaustion.
4. `YANTRA-RUNTIME-004`: Expose async result and event-stream APIs with bounded backpressure.
## Non-functional requirements
Security: runtime alone authorizes actions. Performance: stream without blocking the event loop. Reliability: distinguish unknown outcomes and recoverable states. Scalability: isolate runs/tasks and cap concurrency. Maintainability: typed public contracts and deterministic tests.
## Architecture
Use the [runtime kernel](../architecture/runtime-kernel.md), gateway, tool engine, and transition coordinator.
## Data flow
Validate -> allocate IDs -> assemble context -> provider call -> validate response -> authorize/execute tools -> emit observations -> terminal/suspended result.
## Interfaces
Proposed `Runtime.run/stream/cancel/resume`; see [runtime contract](../specifications/runtime-contract.md).
## Persistence
Optional adapter persists run, events, safe checkpoints, and attempt records; memory mode is non-durable.
## Configuration
Finite step, deadline, token/cost, model-call, tool-call, concurrency, and output limits.
## Security
Untrusted model/provider outputs; policy independent from model; redact and scope tenant identity.
## Error handling
Typed failures; partial/ambiguous tool outcome retained; no unsafe automatic retry.
## Observability
Run/task correlation, transitions, model/tool spans, usage, budgets, and redacted errors.
## Testing
State/property tests, provider/tool mocks, async cancellation/race tests, persistence integration, crash/failure injection.
## Acceptance criteria
All legal transitions pass and illegal transitions are rejected; concurrent stale writers cannot overwrite state; cancellation terminates local waits within configured deadline; budget exhaustion always produces a terminal/suspended result; replay tests issue no external calls.
## Dependencies
Typed contracts, provider gateway, policy/tool interfaces.
## Priority
P0.
## Implementation status
YANTRA-003 implements a bounded local execution loop. YANTRA-004-V01 adds
focused logical tool-scope enforcement; a general scheduler, persistence
integration, approval workflow, OS sandbox, and durable recovery are not
implemented.
## Open questions
Identifier format, public stream backpressure API, and whether run resume creates a linked new run or recovery attempt.
