# YANTRA Roadmap

This roadmap is a proposed sequence, not a delivery-date promise. No listed runtime capability is implemented in this repository.

1. **Foundation:** packaging, typed contracts, provider-neutral gateway, async agent runtime/state machine, tool registry/policy, basic tracing, CLI, unit tests.
2. **Persistence and reliability:** PostgreSQL schema, TypeScript Prisma service, Python adapter, sessions, events, checkpoints, crash recovery, idempotency.
3. **Skills and tools:** skill registry/loading/validation, HTTP scraping, optional browser automation, plugins, sandboxed execution.
4. **Advanced orchestration:** bounded multi-agent execution, workflows, memory, optional pgvector, MCP, skill discovery.
5. **Developer platform:** optional inspector, distributed workers, deployment support, evaluations, skill builder, release automation.

Research extensions (adaptive context/routing, evidence-guided recovery, skill learning) remain experimental and are not prerequisites for baseline usability. Phase dependencies, acceptance conditions, and release gates are in [milestones](docs/roadmap/milestones.md), [feature dependencies](docs/roadmap/feature-dependencies.md), and [production readiness](docs/roadmap/production-readiness.md). Feature completion does not itself mean production-ready.
