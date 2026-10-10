# Tool Execution

## Overview
Executes validated tool requests under independent authorization, deadlines, budgets, and output controls.
## Motivation
Model tool calls cause external effects and require a trusted enforcement point.
## Functional requirements
1. `YANTRA-TOOLEXEC-001`: Treat every model-generated argument as untrusted and validate against exact registered schema/version.
2. `YANTRA-TOOLEXEC-002`: Authorize principal, scope, side-effect class, and approval policy before dispatch.
3. `YANTRA-TOOLEXEC-003`: Enforce timeout, concurrency, input/output size, and cancellation limits.
4. `YANTRA-TOOLEXEC-004`: Record attempt, result classification, audit event, and idempotency semantics.
## Non-functional requirements
Security: least privilege. Performance: async-first, blocking work isolated. Reliability: distinguish started/completed/ambiguous. Scalability: per-tool concurrency quotas. Maintainability: executor protocol and error taxonomy.
## Architecture
Registry -> validation -> policy -> approval if needed -> executor/worker -> result validation.
## Data flow
Proposal -> validate -> authorize -> optionally approve -> dispatch -> bound/validate result -> event/context.
## Interfaces
Async executor protocol; sync adapter runs in bounded worker. See [tool contract](../specifications/tool-contract.md).
## Persistence
Attempt metadata and outcome; sensitive arguments/results minimized or referenced.
## Configuration
Allow/deny scopes, approval rules, timeout, resource/output limits, retries, concurrency.
## Security
No bypass around policy; output treated as untrusted; shell/network/filesystem tools separately restricted.
## Error handling
Typed validation, policy, timeout, cancellation, resource, executor, and ambiguous-effect errors.
## Observability
Execution IDs, duration, policy decision, effect class, result size, error category; redaction.
## Testing
Unit/schema tests, policy bypass tests, malicious args/output, concurrency, cancellation, fault injection.
## Acceptance criteria
Denied tools have zero executor invocations; every invocation has authorization record; time/output bounds hold under hostile inputs; ambiguous effects are never automatically labeled success.
## Dependencies
Tool registry, runtime state machine, policy, audit/event system.
## Priority
P0.
## Implementation status
Proposed.
## Open questions
Out-of-process execution baseline and permission vocabulary.
