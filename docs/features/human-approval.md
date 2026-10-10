# Human Approval

## Overview
Suspends a run for a human decision before a policy-designated action.
## Motivation
High-impact or uncertain side effects need a review boundary.
## Functional requirements
1. `YANTRA-APPROVAL-001`: Bind approval to exact tool/version, argument digest, principal, policy version, and expiry.
2. `YANTRA-APPROVAL-002`: Revalidate authorization and budgets after approval before execution.
3. `YANTRA-APPROVAL-003`: Record approver, decision, reason, time, and audit event; reject stale/replayed approvals.
## Non-functional requirements
Security: authenticated approver and least privilege. Performance: bounded pending queue. Reliability: durable expiry and idempotent decision. Scalability: tenant queues. Maintainability: channel-independent API.
## Architecture
Policy emits approval request; runtime enters WAITING_FOR_APPROVAL; UI/CLI is a separate client.
## Data flow
Request -> persist pending -> notify -> authenticated decision -> binding check -> reauthorize -> queue or cancel.
## Interfaces
Approval request/decision contract with opaque ID and content-safe summary.
## Persistence
Approval request and audit event; bounded summary and digest, not unnecessary raw secret arguments.
## Configuration
Tool/effect thresholds, approver groups, expiry, rejection behavior.
## Security
Prevent confused deputy, request substitution, replay, and approver data leakage.
## Error handling
Expiry/rejection cancels or fails by declared policy; service outage leaves action unexecuted.
## Observability
Wait duration, decision outcome, stale/replay rejection; no sensitive content.
## Testing
Forged/stale approval, concurrent decisions, expiry, tenant isolation, outage.
## Acceptance criteria
Modified arguments invalidate approval; double decision has one winner; no tool runs without valid bound approval; expiry behavior is deterministic.
## Dependencies
Policy engine, durable persistence, authentication.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Notification transport and emergency override governance.
