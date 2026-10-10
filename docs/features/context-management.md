# Context Management

## Overview
Builds a bounded model input from instructions, messages, skills, observations, and retrieval with provenance.
## Motivation
Finite model windows and untrusted mixed-origin content require explicit selection and compaction.
## Functional requirements
1. `YANTRA-CONTEXT-001`: Label every segment with source, trust, sensitivity, and selection rationale.
2. `YANTRA-CONTEXT-002`: Enforce provider-specific token/context ceilings with response reserve.
3. `YANTRA-CONTEXT-003`: Preserve original history and mark compacted/omitted sources explicitly.
## Non-functional requirements
Security: retrieved text never gains instruction privilege. Performance: bounded assembly. Reliability: deterministic fallback. Scalability: retrieval budgets. Maintainability: strategy interface.
## Architecture
Context engine consumes session, skill, memory, and tool observation ports.
## Data flow
Collect candidates -> authorize/filter -> rank/order -> estimate tokens -> compact/truncate -> emit provenance-bearing request.
## Interfaces
`ContextSegment`, assembler strategy, tokenizer estimator.
## Persistence
Persist source references and optional compaction metadata, not necessarily assembled prompt.
## Configuration
Token budget, reserves, priorities, history limits, retrieval policy.
## Security
Prompt-injection labels, sensitive data policy, provider routing constraints.
## Error handling
Too-large mandatory instructions fail explicitly; optional sources may be omitted with event.
## Observability
Token estimate, included/excluded source IDs and reason, compaction metrics; no content by default.
## Testing
Token boundaries, deterministic selection, malicious retrieved content, tokenizer mismatch, redaction.
## Acceptance criteria
Output never exceeds configured conservative budget; all included sources have provenance; truncation is observable and history remains unchanged.
## Dependencies
Agent, message, skill, memory contracts.
## Priority
P1.
## Implementation status
Proposed.
## Open questions
Default ranking and tokenizer strategy across providers.
