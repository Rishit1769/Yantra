# Plugins

## Overview
Optional manifest-driven extensions add adapters and capabilities without changing core contracts.
## Motivation
Third-party integrations need discoverability and replaceability with explicit trust boundaries.
## Functional requirements
1. `YANTRA-PLUGIN-001`: Validate manifest, API range, integrity, provenance, dependencies, and permissions before activation.
2. `YANTRA-PLUGIN-002`: Require explicit allowlisting; in-process executable plugins are treated as trusted code.
3. `YANTRA-PLUGIN-003`: Prevent plugins from mutating core policy, tenant scope, or database migrations.
## Non-functional requirements
Security: least privilege and isolation. Performance: bounded startup. Reliability: activation rollback. Scalability: tenant-aware registry. Maintainability: stable manifest.
## Architecture
Plugin loader for declarative registrations; isolated worker for untrusted executable components.
## Data flow
Discover -> validate -> review/allowlist -> activate -> register capabilities -> audit/deactivate.
## Interfaces
See [plugin manifest](../specifications/plugin-manifest.md).
## Persistence
Optional metadata, integrity digest, enablement, and audit; no secrets.
## Configuration
Allowed IDs/versions, trust roots, execution mode, capability scopes.
## Security
Supply chain, dependency confusion, malicious code, and secret access risks.
## Error handling
Incompatible plugin quarantined; failure does not disable core runtime.
## Observability
Plugin identity/version, activation, permission, resource use, failure.
## Testing
Manifest fuzzing, malicious dependency, tenant isolation, worker containment, upgrade rollback.
## Acceptance criteria
Unapproved plugin never activates; compatibility and digest are checked; core runs without plugin subsystem.
## Dependencies
Plugin contract, tool/skill registries, sandbox.
## Priority
P2.
## Implementation status
Proposed.
## Open questions
Signature trust model and registry distribution.
