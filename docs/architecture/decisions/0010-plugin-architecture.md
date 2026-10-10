# ADR 0010: Plugin-Based Architecture

- Status: Proposed
- Context: Integrations must be replaceable without making every component core.
- Decision: Use explicit versioned manifests, allowlisting, and narrow registration APIs; isolate executable untrusted plugins where feasible.
- Alternatives: Static-only integrations; arbitrary dynamic imports.
- Consequences: Extensibility with validation burden; trust and API compatibility are explicit.
- Tradeoffs: Plugin UX is more constrained; in-process plugin code remains trusted code.
