# Sandboxing

## Overview
Provides optional isolation for code or high-risk tool execution using constrained workers and OS/container controls.
## Motivation
Host-side tool execution may expose files, network, credentials, and compute.
## Functional requirements
1. `YANTRA-SANDBOX-001`: Use dedicated least-privilege identity, bounded CPU/memory/PIDs/time/storage, and explicit network policy.
2. `YANTRA-SANDBOX-002`: Mount only declared inputs/outputs; never mount host credentials or control sockets.
3. `YANTRA-SANDBOX-003`: Terminate and clean up workers after completion, timeout, cancellation, or crash.
4. `YANTRA-SANDBOX-004`: Document that Docker alone is not a complete hostile-code boundary.
## Non-functional requirements
Security: defense in depth. Performance: bounded startup overhead. Reliability: cleanup and orphan detection. Scalability: worker quotas. Maintainability: replaceable backend.
## Architecture
Tool policy broker -> isolated worker backend -> bounded artifact channel; stronger VM/microVM isolation may be needed for hostile code.
## Data flow
Authorize -> stage declared inputs -> create restricted worker -> execute -> validate outputs -> destroy and audit.
## Interfaces
Sandbox executor contract with resource profile, input refs, and output schema.
## Persistence
Record image/runtime digest, policy, resource use, and artifact refs; no secrets.
## Configuration
Backend, image allowlist, CPU/memory/time/disk/PID/network limits.
## Security
Kernel/container escape, supply-chain, egress and secret exfiltration risks; do not claim complete containment.
## Error handling
Timeout/worker loss yields status and ambiguous side-effect classification; cleanup retries are observable.
## Observability
Worker identity, image digest, resource use, policy denies, cleanup result.
## Testing
Escape-oriented security review, resource exhaustion, network denial, cancellation, orphan cleanup, malicious artifact.
## Acceptance criteria
No undeclared host mounts or secrets; all limits enforced under tests; worker cleanup verified; threat review documents residual risk.
## Dependencies
Tool engine, policy, artifact handling, deployment controls.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Initial backend and threat level supported; Docker is not assumed sufficient.
