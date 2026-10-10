# API Integrations

## Overview
Applications may wrap external APIs as typed tools/adapters with scoped credentials and domain policies.
## Motivation
Model-directed access to external services needs the same validation and audit boundary as built-in tools.
## Functional requirements
1. `YANTRA-API-001`: Declare endpoint, method, schema, permissions, data classification, side effects, timeout, and idempotency semantics.
2. `YANTRA-API-002`: Enforce host allowlists, TLS, request/response bounds, and secret references.
3. `YANTRA-API-003`: Validate provider responses before exposing them to model context.
## Non-functional requirements
Security: SSRF, auth, and exfiltration controls. Performance: per-host pools. Reliability: typed errors and safe retry. Scalability: rate limits. Maintainability: reusable adapter protocol.
## Architecture
HTTPX-based integration adapter invoked through tool authorization.
## Data flow
Validate request -> authorize scope -> resolve credential -> send constrained request -> normalize bounded response -> audit.
## Interfaces
Typed integration tool/provider contracts.
## Persistence
Store integration metadata and call outcome only; no credential material.
## Configuration
Host/method allowlist, secret reference, deadlines, budgets, retry/idempotency.
## Security
Restrict DNS/IP and redirects, prevent credential forwarding, redact headers/bodies.
## Error handling
Map auth, rate-limit, timeout, invalid response, unavailable, ambiguous side effect.
## Observability
Integration ID, host class, status, latency, bytes, retries; no secret values.
## Testing
SSRF, redirect, secret leakage, malformed responses, retries, idempotency, outage.
## Acceptance criteria
Unlisted hosts/methods denied; credentials never appear in output; retries occur only for classified safe operations; response limits enforced.
## Dependencies
HTTPX, tool engine, secret source, network policy.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Generic connector scope versus application-authored adapters.
