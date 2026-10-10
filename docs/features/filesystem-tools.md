# Filesystem Tools

## Overview
Optional tools expose narrowly scoped file read/write/list operations inside declared roots.
## Motivation
Applications need controlled local artifacts without giving models ambient host filesystem access.
## Functional requirements
1. `YANTRA-FS-001`: Resolve paths beneath an allowlisted root and prevent traversal, symlink, race, and special-file escapes.
2. `YANTRA-FS-002`: Declare read/write/delete permissions and enforce byte/count limits.
3. `YANTRA-FS-003`: Require approval for destructive or broad changes by policy.
## Non-functional requirements
Security: deny ambient host access. Performance: bounded streaming IO. Reliability: atomic writes where supported. Scalability: per-run quotas. Maintainability: platform-specific tests.
## Architecture
Filesystem tool adapter with directory capability handles and sandbox option.
## Data flow
Authorize root/scope -> canonical safe open -> bounded operation -> validate result -> audit.
## Interfaces
Schema-based tools; paths are untrusted input.
## Persistence
Artifacts stored by application policy; tool output metadata only by default.
## Configuration
Roots, operations, symlink policy, size/count limits, approval rules.
## Security
No arbitrary paths, credentials, device files, or parent traversal; mitigate TOCTOU using safe APIs.
## Error handling
Permission/path/race/size errors normalized without disclosing host paths unnecessarily.
## Observability
Root identifier, operation, bytes, result category; omit file content.
## Testing
Traversal, symlink races, hard links, platform path forms, permissions, large files, concurrent writes.
## Acceptance criteria
Adversarial paths cannot access outside roots; configured size/operation limits hold; destructive action policy is enforced.
## Dependencies
Tool engine, OS safe-open support, optional sandbox.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Portable safe-open baseline across supported operating systems.
