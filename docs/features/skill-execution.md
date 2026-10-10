# Skill Execution

## Overview
Resolves and loads approved skill instructions/resources into a run context; it does not execute skill code by default.
## Motivation
Reusable procedures should be bounded, traceable, and distinct from tools.
## Functional requirements
1. `YANTRA-SKILLEXEC-001`: Pin immutable skill version/digest for the run.
2. `YANTRA-SKILLEXEC-002`: Load only approved, compatible content and declared resources under context budget.
3. `YANTRA-SKILLEXEC-003`: Keep permissions enforced by tool policy; skill declarations cannot escalate.
## Non-functional requirements
Security: untrusted content labels and injection controls. Performance: bounded load/cache. Reliability: digest verification. Scalability: cache invalidation on revocation. Maintainability: deterministic loader.
## Architecture
Skill resolver and validator feed provenance-bearing context engine.
## Data flow
Resolve -> check approval/compatibility -> verify digest -> filter resource access -> load -> annotate context -> audit.
## Interfaces
Skill reference with exact version or explicit range resolved to immutable version.
## Persistence
Run pins skill digest and load metadata; content retention governed separately.
## Configuration
Allowed skills, version constraints, token/resource limits, trust policy.
## Security
Instructions are data, not system policy; no automatic executable code or privilege escalation.
## Error handling
Digest/compatibility/revocation failure blocks load; missing optional resource is explicit.
## Observability
Skill/version/digest, content size, resolution decision, omitted resources.
## Testing
Tampering, revocation, token limits, malicious instructions, cache invalidation.
## Acceptance criteria
Run provenance pins exact digest; revoked/unapproved skill cannot load; loaded content respects token ceiling and is labeled untrusted.
## Dependencies
Registry, context engine, policy.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
How skill updates affect long-lived sessions (default: pinned per run).
