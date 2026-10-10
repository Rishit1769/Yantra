# ADR 0013: Separate YANTRA and NIRMAAN

- Status: Proposed
- Context: NIRMAAN is a coding-specific application; YANTRA should be independently reusable.
- Decision: NIRMAAN consumes a versioned public SDK and owns repository/business workflows; no dependency from YANTRA and no circular dependency.
- Alternatives: Monorepo coupled runtime; YANTRA owns coding agents.
- Consequences: Independent release and generic scope; consumer compatibility needs tests.
- Tradeoffs: Integration uses public contracts and may require coordinated version ranges.
