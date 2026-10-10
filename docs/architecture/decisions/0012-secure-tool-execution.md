# ADR 0012: Secure Tool Execution

- Status: Proposed
- Context: Model-proposed tool calls can produce external side effects.
- Decision: Validate untrusted arguments, resolve exact registered tool, independently authorize, require approval as policy dictates, enforce limits, and audit before/after execution.
- Alternatives: Trust provider tool calls; tool self-authorizes; unrestricted shell.
- Consequences: Explicit enforcement and traceability; tool adapters need schemas, policy integration, and idempotency classification.
- Tradeoffs: Added latency and developer setup; no exactly-once guarantee for arbitrary effects.
