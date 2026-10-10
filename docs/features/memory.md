# Memory

## Overview
Supports working and persistent records distinct from conversation history, with optional semantic retrieval.
## Motivation
Cross-run continuity should be explicit, scoped, and deletable rather than inferred from chat logs.
## Functional requirements
1. `YANTRA-MEMORY-001`: Namespace every record by owner/tenant and applicable session/agent scope.
2. `YANTRA-MEMORY-002`: Attach provenance, sensitivity, retention, and source timestamp to writes.
3. `YANTRA-MEMORY-003`: Support metadata/keyword retrieval without pgvector; vector search remains optional.
4. `YANTRA-MEMORY-004`: Implement deletion across primary, embedding, and derived indexes.
## Non-functional requirements
Security: isolation and sensitive-data controls. Performance: bounded retrieval. Reliability: deletion propagation. Scalability: indexes/retention. Maintainability: backend-neutral contract.
## Architecture
Memory engine over PostgreSQL adapter and optional pgvector adapter.
## Data flow
Explicit write decision -> validation/classification -> persist -> scoped query -> rank -> provenance-bearing context.
## Interfaces
Proposed `Memory.store/search/delete` APIs with namespace and filters.
## Persistence
Relational memory metadata/content; optional embeddings with model identity.
## Configuration
Retention, allowed namespaces, retrieval count/token ceiling, embedding backend opt-in.
## Security
No cross-tenant retrieval; consent and data minimization; sensitive content excluded from embeddings by default.
## Error handling
Vector outage falls back to keyword only if policy permits; deletion failure remains visible and retried.
## Observability
Retrieval IDs/rank scores, latency, deletion status; avoid content logging.
## Testing
Isolation, deletion, retention, relevance fixtures, vector-off mode, failure injection.
## Acceptance criteria
All reads are namespace-scoped; deletion tests cover vector derivations; baseline works with extension absent; retrieval returns source provenance.
## Dependencies
Persistence, context engine; optional embedding adapter/pgvector.
## Priority
P2.
## Implementation status
Proposed.
## Open questions
Consent model and whether memory writes are user-initiated or policy-triggered.
