# Introduction

YANTRA provides an installable Python package with typed core contracts, a model gateway and adapters, a bounded asynchronous agent loop, a tool registry, exact-scope authorization, trusted host-injected approvals, optional restricted worker subprocess execution, in-memory storage, and structured logging. Provider protocol tests use mocked HTTP; they do not prove broad live provider/model compatibility. The package has a focused `yantra-smoke` CLI, not a general-purpose agent CLI, and has no durable persistence adapter.

The initial user is a Python developer who needs a controlled model/tool loop and wants to choose providers. The core should run in process with an in-memory adapter; durability, browser automation, vector search, and distributed workers are opt-in subsystems.

Use the [core contracts quickstart](quickstart.md) or [offline agent quickstart](../guides/agent-quickstart.md) for no-network examples. Hosted CI passed the configured nine-job Ubuntu/macOS/Windows and Python 3.12–3.14 matrix; the current [RR-004 audit](../development/yantra-release-readiness-rr004.md) records fresh local release-candidate checks and remaining gates. Live provider verification remains model/account-specific. See [milestones](../roadmap/milestones.md).
