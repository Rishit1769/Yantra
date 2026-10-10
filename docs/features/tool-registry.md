# Tool Registry

## Overview
Registry manages versioned typed tool metadata and resolves only registered capabilities.
## Motivation
Prevent model-generated names/arguments from selecting arbitrary code paths.
## Functional requirements
1. `YANTRA-TOOLREG-001`: Register unique namespace/name/version with input/output schemas and executor metadata.
2. `YANTRA-TOOLREG-002`: Publish only tools visible to the current principal and model capability.
3. `YANTRA-TOOLREG-003`: Reject ambiguous, undeclared, or incompatible registrations.
## Non-functional requirements
Security: allowlist and immutable version resolution. Performance: local indexed lookup. Reliability: deterministic duplicate handling. Scalability: tenant-scoped registries. Maintainability: API-version conformance.
## Architecture
In-memory core registry with optional plugin/remote catalog adapter.
## Data flow
Registration validation -> policy binding -> filtered discovery -> exact version lookup at invocation.
## Interfaces
`ToolDefinition`, `ToolRegistry.register/resolve/list`; JSON Schema contract in [tool spec](../specifications/tool-contract.md).
## Persistence
Definitions may be packaged in app or persisted in plugin/catalog services; run records pin tool version.
## Configuration
Namespaces, allowed versions, discovery filters, conflict policy.
## Security
Registry metadata is not authorization; execution rechecks policy.
## Error handling
Unknown/ambiguous/incompatible tool fails closed with typed error.
## Observability
Registration provenance/version and lookup outcomes; no secret metadata.
## Testing
Schema, duplicate, tenant visibility, version resolution, and race tests.
## Acceptance criteria
Unknown tool proposals never execute; resolution is deterministic under concurrent registration; schema incompatibility is rejected before model exposure.
## Dependencies
Tool contract and permission system.
## Priority
P0.
## Implementation status
In Development. Local registration, exact lookup, deterministic listing, unregister, schema export, and Pydantic input/output validation are implemented. Policy authorization, tenant scope, remote catalogs, and tool execution remain out of scope.
## Open questions
Whether dynamic registration is allowed during a run (default should be no).
