# Skill Sharing

## Overview
Supports package import/export and future trusted registry distribution.
## Motivation
Portable skills enable reuse while maintaining provenance and review.
## Functional requirements
1. `YANTRA-SKILLSHARE-001`: Export immutable manifest/content with digest and license/provenance metadata when known.
2. `YANTRA-SKILLSHARE-002`: Import into quarantine and validate before approval.
3. `YANTRA-SKILLSHARE-003`: Preserve publisher identity and dependency references; never trust imported permissions.
## Non-functional requirements
Security: supply-chain and archive path protections. Performance: package size bounds. Reliability: atomic import. Scalability: registry pagination. Maintainability: portable format.
## Architecture
Archive/local package exchange first; future remote registry transport.
## Data flow
Export pinned version -> verify digest -> import quarantine -> scan/validate -> human review -> publish locally.
## Interfaces
Manifest and resource package; registry protocol future.
## Persistence
Source provenance, digest, import decision and review audit.
## Configuration
Trusted publisher keys, size limits, allowed content types.
## Security
No package code execution; defend archive traversal, malicious content and dependency confusion.
## Error handling
Partial imports roll back/quarantine; digest/signature failures reject.
## Observability
Publisher, digest, scanner/validator versions, decision.
## Testing
Archive traversal, tampering, malicious metadata, signature failure, oversized packages.
## Acceptance criteria
Imported package cannot activate before review; tampering is detected; unknown license is not represented as permissive.
## Dependencies
Skill registry, manifest, provenance/signature policy.
## Priority
P3.
## Implementation status
Proposed.
## Open questions
Registry governance, signing root, and license metadata policy.
