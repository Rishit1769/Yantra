# ADR 0003: Async Execution

- Status: Proposed
- Context: Provider, persistence, browser, and tool IO are concurrent and deadline/cancellation-sensitive.
- Decision: Async-first runtime using asyncio/AnyIO; blocking adapters use bounded worker execution.
- Alternatives: Synchronous core; callback/event framework.
- Consequences: Efficient IO concurrency and cancellation model; developers must understand async and adapters must honor cancellation.
- Tradeoffs: Sync ergonomics may require wrappers; no unbounded task spawning.
