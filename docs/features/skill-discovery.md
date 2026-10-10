# Skill Discovery

## Overview
Find eligible skills by metadata, keywords, capabilities, tags, and optionally semantic similarity.
## Motivation
Large catalogs require transparent filtering and relevance.
## Functional requirements
1. `YANTRA-SKILLDISC-001`: Filter by compatibility, trust/approval, tenant visibility, and declared capabilities before ranking.
2. `YANTRA-SKILLDISC-002`: Provide deterministic metadata/keyword baseline.
3. `YANTRA-SKILLDISC-003`: Make semantic search optional and return provenance/rationale.
## Non-functional requirements
Security: no unapproved skill exposure. Performance: bounded query/top-k. Reliability: baseline works without vectors. Scalability: indexed catalog. Maintainability: ranking version recorded.
## Architecture
Catalog filter -> keyword index -> optional pgvector -> rank merge -> authorized results.
## Data flow
Query -> scope filters -> eligibility filters -> rank -> bounded result list -> explicit selection.
## Interfaces
Search API accepts query, capability constraints, namespace and limit.
## Persistence
Metadata/tags relational; optional embeddings tied to immutable digest.
## Configuration
Allowed sources, result limit, ranking strategy, vector opt-in.
## Security
Semantic result cannot auto-grant permission; prompt injection labels retained.
## Error handling
Vector failure may use keyword fallback and is reported; catalog outage is explicit.
## Observability
Filters, ranking version, result IDs, latency; query redaction.
## Testing
Tenant filters, relevance sets, stale vector, disabled pgvector, unapproved results.
## Acceptance criteria
Ineligible skills never appear; vector-off search works; every result has digest/trust/version; evaluation reports ranking quality.
## Dependencies
Skill registry; optional pgvector/embedding provider.
## Priority
P2.
## Implementation status
Proposed.
## Open questions
Evaluation relevance judgments and semantic ranking threshold.
