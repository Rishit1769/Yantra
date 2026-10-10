# Introduction

YANTRA-001 provides an installable Python package with typed core contracts, a deterministic mock provider, tool registry, state transitions, events, in-memory storage, and structured logging. YANTRA-002 adds a model gateway and provider adapters with mocked HTTP tests. It does not yet execute an agent loop and has no CLI or persistent storage adapter; live provider behavior is not verified.

The initial user is a Python developer who needs a controlled model/tool loop and wants to choose providers. The core should run in process with an in-memory adapter; durability, browser automation, vector search, and distributed workers are opt-in subsystems.

Use the [core contracts quickstart](quickstart.md) for a no-network example. The broader Phase 1 milestone still requires the agent execution loop, tool authorization policy, CLI, live provider verification, and CI verification. See [milestones](../roadmap/milestones.md).
