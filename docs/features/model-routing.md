# Model Routing

## Overview
Optional policy selects among eligible models using required capabilities, operator constraints, and measured cost/latency/performance.
## Motivation
Allow deliberate tradeoffs without silently reducing capability or violating data constraints.
## Functional requirements
1. `YANTRA-ROUTE-001`: Filter candidates by capability, context, region, privacy, and policy before scoring.
2. `YANTRA-ROUTE-002`: Record route rationale, candidate set, policy/model metadata, and fallback.
3. `YANTRA-ROUTE-003`: Never fallback to a model violating required capability or data policy.
## Non-functional requirements
Security: endpoint allowlist. Performance: bounded deterministic routing overhead. Reliability: explicit no-eligible-provider error. Scalability: cache only versioned capability metadata. Maintainability: pluggable scoring policy.
## Architecture
Router is optional above gateway adapters; adaptive policy is research-only.
## Data flow
Requirements -> eligible set -> deterministic policy -> route record -> adapter call -> outcome feedback.
## Interfaces
`ModelRoutingPolicy` defaults to manual selection. Automatic model order, fallback chains, retries beyond one attempt, local-to-cloud routing, and configured cost limits require an approval digest bound to the exact policy settings. Automatic selection filters by known capabilities, allowlists, locality, and available pricing; it follows operator-specified order rather than optimizing quality. Gateway responses and metadata-only events record the selected model and route decision.
## Persistence
Persist route decision metadata for reproducibility, not credentials.
## Configuration
Allowed providers/models, capability constraints, cost/latency weights, privacy constraints, fallback policy.
## Security
Do not transmit sensitive context to an unapproved provider; no user input controls allowlist.
## Error handling
No eligible model is explicit; avoid infinite failover; bounded attempts and circuit state.
## Observability
Candidate count, selected route, reason code, latency/cost if known, fallback count.
## Testing
Deterministic selection, incompatible candidates, outages, stale capability metadata, privacy constraints.
## Acceptance criteria
Same inputs/policy version produce same deterministic route; prohibited candidates are never called; all fallback decisions are traceable.
## Dependencies
Model gateway and capability registry.
## Priority
P2.
## Implementation status
YANTRA-002 implements manual-first routing, opt-in deterministic candidate ordering, explicit bounded fallback/retry policy, local-only and local-to-cloud controls, allowlists, cost preflight, and metadata-only route events. Cost enforcement requires known pricing and token bounds and is an estimate, not a hard provider billing cap. Adaptive/quality-based routing, latency learning, and persistent route history are not implemented.
## Open questions
Pricing source and whether routing belongs in core or optional package.
