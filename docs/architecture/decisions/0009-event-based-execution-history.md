# ADR 0009: Event-Based Execution History

- Status: Proposed
- Context: Debugging, recovery, audit, and future inspector need chronological execution facts.
- Decision: Emit immutable versioned events with per-run sequence; durable persistence is optional by mode.
- Alternatives: Mutable status snapshots only; logs as source of truth.
- Consequences: Better reconstruction and consumer decoupling; schema/retention/volume need governance.
- Tradeoffs: Events are observations, not exactly-once effects; replay never dispatches tools by default.
