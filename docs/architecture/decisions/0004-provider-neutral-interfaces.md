# ADR 0004: Provider-Neutral Interfaces

- Status: Proposed
- Context: Provider capabilities and semantics differ; vendor-specific SDKs change.
- Decision: Define a normalized provider contract with explicit per-deployment capabilities and typed unsupported errors.
- Alternatives: Common-denominator-only API; provider objects exposed to applications.
- Consequences: Applications gain portability with capability negotiation; adapters must maintain mappings and conformance fixtures.
- Tradeoffs: Abstraction cannot erase semantic differences; fallback remains explicit.
