# Skill Learning

## Overview
Experimental pipeline proposes candidate reusable skills from successful traces; it does not automatically publish or execute them.
## Motivation
Repeated validated procedures may be distilled into reviewed reusable instructions.
## Functional requirements
1. `YANTRA-SKILLLEARN-001`: Generate candidates only from consented, policy-eligible, redacted traces.
2. `YANTRA-SKILLLEARN-002`: Validate candidate against independent tasks, permissions, provenance, and reproducibility before human review.
3. `YANTRA-SKILLLEARN-003`: Never grant permissions, publish, or activate a candidate automatically.
## Non-functional requirements
Security: data governance and injection resistance. Performance: bounded offline jobs. Reliability: provenance. Scalability: evaluation queue. Maintainability: experimental isolation.
## Architecture
Offline candidate generator -> lint/evaluation -> reviewer -> ordinary registry publication pipeline.
## Data flow
Eligible traces -> redact/generalize -> draft instructions/manifest -> test -> review -> optional publish.
## Interfaces
Candidate artifact only; not runtime API.
## Persistence
Restricted trace references, candidate digest and evaluation results with retention.
## Configuration
Consent, eligible event types, redaction, dataset limits, review policy.
## Security
Prevent secret memorization, tenant leakage, malicious trace instructions and permission escalation.
## Error handling
Insufficient evidence rejects candidate; pipeline failures never affect runtime.
## Observability
Source lineage, transformations, evaluation and review decision.
## Testing
Leakage canaries, cross-tenant probes, harmful instruction tests, held-out utility evaluation.
## Acceptance criteria
No candidate becomes active without human approval and normal validation; test suite detects planted secrets and cross-tenant content; utility is reported against baseline.
## Dependencies
Events, evaluation framework, skill registry.
## Priority
P3.
## Implementation status
Proposed (experimental).
## Open questions
Consent, trace eligibility, and utility threshold.
