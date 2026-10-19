# First Agent (YANTRA-003-V01)

The first bounded agent loop is implemented in `yantra.runtime`. It uses the
existing model gateway and an explicit in-process tool registry; it does not
require PostgreSQL, credentials, or live inference. See the [agent execution
engine](../architecture/agent-execution-engine.md) for lifecycle and safety
semantics.

The deterministic offline tests use provider fixtures to cover final text,
sequential tool calls, failures, bounds, usage, and cancellation. The API is
experimental and pre-1.0; it is present in the unreleased `0.2.0` candidate.

To try the bounded model/tool/model cycle from an installed distribution,
run `yantra quickstart`. This installed-package demo needs no API key, network,
database, or source checkout. See the [CLI reference](../features/cli.md) and
[installation guide](installation.md).
