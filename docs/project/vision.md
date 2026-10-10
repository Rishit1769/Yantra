# Vision

YANTRA (यन्त्र) is intended to be reusable infrastructure for building, executing, orchestrating, securing, debugging, and deploying AI agents with developer-chosen models. Its mission is to make execution behavior inspectable and controllable rather than hiding it behind vendor- or application-specific abstractions.

The harness owns the control loop, context assembly, budgets, policy enforcement, tool dispatch, state transitions, events, and recovery boundaries. Providers own inference. Applications own domain-specific workflows and user experience. The design targets Python 3.12+ and an optional PostgreSQL-backed service, with local in-memory use possible.

YANTRA is independent from NIRMAAN and PROMETHEUS. NIRMAAN may consume the public SDK for software-engineering work; neither project is a dependency of YANTRA. PROMETHEUS remains a separate developer-intelligence platform.

Everything in this document is a direction, not a claim of current implementation. License selection remains unresolved and must be decided by maintainers before distribution under an open-source license.
