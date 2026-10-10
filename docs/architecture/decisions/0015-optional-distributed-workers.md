# ADR 0015: Optional Distributed Workers

- Status: Proposed
- Context: Distributed execution may be needed for scale/recovery but adds queue, lease, and duplicate-delivery complexity.
- Decision: Start with local execution; add workers only when justified, with bounded queues, leases, fencing and at-least-once semantics. Redis is optional.
- Alternatives: Distributed workers from initial release; single-process forever.
- Consequences: Simpler local adoption and later horizontal path; recovery/idempotency must be designed before distribution.
- Tradeoffs: No distributed scaling guarantee in initial phases; exactly-once external effect is not promised.
