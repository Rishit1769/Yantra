# Skill Registry

## Overview
Stores and resolves local or shared immutable skill versions.
## Motivation
Reusable capabilities need provenance, review, compatibility, and rollback.
## Functional requirements
1. `YANTRA-SKILLREG-001`: Support confined local directories and optional PostgreSQL-backed shared catalog.
2. `YANTRA-SKILLREG-002`: Validate manifest, digest, dependencies, permission declarations, and compatibility before resolution.
3. `YANTRA-SKILLREG-003`: Keep approval/trust state distinct from package self-description.
## Non-functional requirements
Security: untrusted by default. Performance: indexed metadata lookup. Reliability: immutable digest. Scalability: pagination/cache invalidation. Maintainability: schema versioning.
## Architecture
Registry port with filesystem and persistence-service adapters.
## Data flow
Import -> quarantine -> validate/review -> approve -> immutable publish -> version resolve -> revoke/rollback.
## Interfaces
Manifest in [skill specification](../specifications/skill-manifest.md).
## Persistence
Skill/version/dependency/permission rows; resources by bounded artifact reference.
## Configuration
Sources, trust roots, allowed publishers, size limits, compatibility policy.
## Security
Path traversal, malicious instructions/code, dependency risks, tenant isolation.
## Error handling
Invalid/incompatible versions are not loadable; revocation blocks new resolution.
## Observability
Digest, source, validation, approval, resolution and revocation events.
## Testing
Manifest fuzzing, digest mismatch, traversal, dependency cycles, revocation, tenant access.
## Acceptance criteria
Unapproved import cannot load into runtime; immutable versions resolve by exact digest; revoked version is rejected for new runs.
## Dependencies
Persistence, skill validation/security, context engine.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Local registry trust workflow and global catalog governance.
