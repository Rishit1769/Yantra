# System Design

## Layers

1. **Application:** defines domain agents and invokes the versioned SDK. It owns product logic and user-facing behavior.
2. **SDK/contracts:** typed agent, provider, tool, skill, workflow, event, and persistence-port contracts. Public schemas are versioned.
3. **Python runtime:** asyncio/AnyIO orchestration, context assembly, budgets, transitions, policy enforcement, dispatch, cancellation, and event emission. It must not depend on Prisma or application projects.
4. **Adapters:** provider, persistence, telemetry, browser, sandbox, and external tool implementations. Optional integrations stay optional extras/services.
5. **Persistence service:** TypeScript API, authentication/authorization, Prisma Client, migrations, tenant scoping, and durable records.
6. **Infrastructure:** PostgreSQL; optional pgvector, Redis, containerized workers, and exporters.

## Control and data flow

The runtime owns the run loop and does not yield authority to a provider SDK. It validates provider responses against contracts, independently checks tool permissions, and emits versioned events. A request crosses the persistence boundary only when durable read/write semantics are needed; transient token deltas and local loop bookkeeping should not trigger remote calls. External effects are executed by a tool adapter and recorded as attempts/results, with ambiguous outcomes represented as such.

## Availability modes

- Local: Python process with in-memory session/event adapter and provider selected by the caller.
- Durable single service: Python runtime plus authenticated TypeScript persistence API and PostgreSQL.
- Distributed: workers and coordination are future optional components; Redis is justified only by concrete queue/lease/cache requirements.

No mode is currently implemented or production-supported. See [deployment gates](../roadmap/production-readiness.md).
