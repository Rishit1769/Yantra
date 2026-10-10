# Terminal Tools

## Overview
Proposed command execution is restricted to explicitly configured executables/arguments in a sandbox or isolated worker.
## Motivation
Some developer workflows require process execution, but model-generated shell commands are arbitrary code.
## Functional requirements
1. `YANTRA-TERM-001`: Never execute a model string through an implicit shell by default.
2. `YANTRA-TERM-002`: Enforce executable allowlist, argument schema, cwd, environment, timeout, output, process-tree, and network limits.
3. `YANTRA-TERM-003`: Require approval for high-risk command classes and audit exact executable/argument digest.
## Non-functional requirements
Security: sandbox/OS controls and no inherited secrets. Performance: bounded process slots. Reliability: terminate process tree. Scalability: quotas. Maintainability: platform-specific executor.
## Architecture
Policy broker invokes an isolated process backend; direct host execution is disabled by default.
## Data flow
Validate structured argv -> authorize -> stage workspace -> launch constrained process -> capture bounded output -> terminate/cleanup.
## Interfaces
Typed argv, environment allowlist, workspace handle, resource profile; no unrestricted shell text interface.
## Persistence
Command metadata, exit status, redacted bounded output/artifacts.
## Configuration
Executable/image allowlist, workspace, environment, limits, network and approval policy.
## Security
Prompt-generated shell is untrusted; prevent injection, secret inheritance, path escape, fork bomb, egress, and sandbox escape. Docker alone is insufficient.
## Error handling
Timeout/termination failure and uncertain external effects are explicit; cleanup failure escalates.
## Observability
Executable identity/digest, duration, resource use, exit code, policy/approval result.
## Testing
Shell metacharacters, env leakage, process trees, resource exhaustion, filesystem/network boundaries, cancellation.
## Acceptance criteria
No shell invocation from raw model text; all process/resource/network boundaries have tests; secrets absent; worker termination verified.
## Dependencies
Sandbox, tool policy, filesystem workspace, approval.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Whether any host-local mode should ever be supported.
