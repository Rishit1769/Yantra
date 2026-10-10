# Sessions

## Overview
Sessions group runs and selected conversation history with owner/tenant scope.
## Motivation
Support continuity while distinguishing interaction history from long-term memory.
## Functional requirements
1. `YANTRA-SESSION-001`: Create opaque session IDs bound to authenticated owner/tenant.
2. `YANTRA-SESSION-002`: Append immutable messages with run linkage and schema version.
3. `YANTRA-SESSION-003`: Enforce retention, export, and deletion policy.
## Non-functional requirements
Security: tenant isolation. Performance: paged history. Reliability: versioned writes. Scalability: retention/partition strategy. Maintainability: history schema migrations.
## Architecture
Runtime session port with in-memory and durable adapters.
## Data flow
Create session -> append run observations -> select history under context budget -> expire/export/delete.
## Interfaces
Session ID and persistence contract operations; messages per [schema](../specifications/message-schema.md).
## Persistence
PostgreSQL session/message or event-backed history; exact projection unresolved.
## Configuration
Retention, history selection, max items/bytes, ownership.
## Security
Every query scoped by authenticated tenant; content minimized/redacted.
## Error handling
Stale version, not found, retention/deletion, persistence unavailable are explicit.
## Observability
Session/run correlation and access audit, not content by default.
## Testing
Tenant isolation, concurrent append, retention/deletion, pagination, version conflicts.
## Acceptance criteria
Cross-tenant access tests fail closed; concurrent appends preserve order/unique sequence; deleted content is unavailable through primary APIs and documented backup policy.
## Dependencies
Persistence port, message schema.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Whether message history is stored as events only or separate projection.
