# Python SDK

## Overview
Public typed Python interfaces expose agents, runtime, tools, skills, providers, sessions, workflows, memory, persistence, and execution results.
## Motivation
Applications should integrate through stable public contracts rather than internal modules.
## Functional requirements
1. `YANTRA-SDK-001`: Provide documented async APIs with typed inputs/results and explicit cancellation.
2. `YANTRA-SDK-002`: Keep infrastructure adapters optional and support an in-memory local path.
3. `YANTRA-SDK-003`: Version public APIs and expose no Prisma dependency.
## Non-functional requirements
Security: validated configuration. Performance: bounded async resources. Reliability: stable errors. Scalability: adapter boundaries. Maintainability: public/private module policy.
## Architecture
Package facade over runtime/contracts and optional extras.
## Data flow
Application definitions -> SDK validation -> runtime -> adapters -> typed result/events.
## Interfaces
Conceptual `Agent`, `Runtime`, `Tool`, `Skill`, `Provider`, `Session`, `Workflow`, `Memory`, `Persistence`, `ExecutionResult`; API is not implemented.
## Persistence
Injected port; SDK has no direct Prisma/database driver requirement.
## Configuration
Typed config object and secret references.
## Security
No implicit network/tool capability and no credential serialization.
## Error handling
Stable error taxonomy and cancellation semantics.
## Observability
Context manager hooks and event stream.
## Testing
Public API tests, typing checks with Pyright, packaging/import tests, compatibility suite.
## Acceptance criteria
Clean installation artifact supports a documented async example; Pyright and API contract tests pass; Python dependency graph has no Prisma/SQLAlchemy/Alembic.
## Dependencies
Runtime and provider/tool contracts.
## Priority
P0.
## Implementation status
Proposed.
## Open questions
Package namespace and API stability window.
