# Skill Versioning

## Overview
Versions are immutable, compatibility-constrained, and resolvable/rollbackable by digest.
## Motivation
Reproducibility and safe updates require avoiding silent content mutation.
## Functional requirements
1. `YANTRA-SKILLVER-001`: Publish a new immutable semantic version and content digest for any content/permission change.
2. `YANTRA-SKILLVER-002`: Resolve dependencies against declared API ranges and reject cycles/conflicts.
3. `YANTRA-SKILLVER-003`: Support revocation and selecting a prior approved version for new runs.
## Non-functional requirements
Security: permission changes require review. Performance: indexed resolution. Reliability: stable historical pins. Scalability: dependency graph bounds. Maintainability: compatibility policy.
## Architecture
Immutable version records plus mutable catalog status/approval events.
## Data flow
Build digest -> validate semver/dependencies -> review -> publish -> pin -> revoke or choose prior version.
## Interfaces
Semver and digest references in manifest and run provenance.
## Persistence
SkillVersion, dependencies, permissions, content refs, audit history.
## Configuration
API compatibility range, allowed version policy, dependency depth.
## Security
Rollback cannot restore revoked vulnerability without explicit reviewed reapproval.
## Error handling
Ambiguous range resolution fails in reproducible mode; incompatibility blocks load.
## Observability
Version/digest/dependency resolution and rollback events.
## Testing
Semver boundaries, digest changes, dependency cycles, revocation, rollback.
## Acceptance criteria
Published content cannot be modified in place; pinned runs resolve same digest; incompatible dependencies fail deterministically.
## Dependencies
Skill registry, manifest, compatibility policy.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Semver policy for instruction-only changes.
