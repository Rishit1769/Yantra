# First Agent (YANTRA-003-V01)

The first bounded agent loop is implemented in `yantra.runtime`. It uses the
existing model gateway and an explicit in-process tool registry; it does not
require PostgreSQL, credentials, or live inference. See the [agent execution
engine](../architecture/agent-execution-engine.md) for lifecycle and safety
semantics.

The deterministic offline tests use provider fixtures to cover final text,
sequential tool calls, failures, bounds, usage, and cancellation. The engine
is experimental and not included in the `0.2.0` release candidate.
