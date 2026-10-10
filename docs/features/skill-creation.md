# Skill Creation

## Overview
Developers author skills manually using manifest plus `SKILL.md` and optional static resources.
## Motivation
Make reusable procedures portable and reviewable without coupling them to executable code.
## Functional requirements
1. `YANTRA-SKILLCREATE-001`: Document required metadata, capabilities, permissions, compatibility, resource digest, and instruction sections.
2. `YANTRA-SKILLCREATE-002`: Provide validation before import/publish.
3. `YANTRA-SKILLCREATE-003`: Mark generated content as untrusted until human approval.
## Non-functional requirements
Security: no implicit code. Performance: bounded package. Reliability: deterministic validation. Scalability: reusable package format. Maintainability: manifest evolution.
## Architecture
Authoring files parsed by registry validator; see [manifest](../specifications/skill-manifest.md).
## Data flow
Author -> lint -> validate declared capabilities -> review -> publish immutable version.
## Interfaces
`skill.yaml`, `SKILL.md`, content digest; tooling is future.
## Persistence
Registry stores immutable content/metadata or local files.
## Configuration
Manifest schema/API compatibility and size limits.
## Security
Instructions/resources remain untrusted inputs; executable artifacts rejected by default.
## Error handling
Validation returns field-specific safe diagnostics; malformed package cannot partially publish.
## Observability
Validator version, digest, errors, review state.
## Testing
Schema fixtures, malformed Unicode/path, oversized resources, digest stability.
## Acceptance criteria
Valid package is deterministic across supported platforms; invalid permissions/dependencies fail; no executable content runs during validation.
## Dependencies
Skill manifest and registry.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Whether authoring tooling is CLI-only initially.
