# Milestones

All dates are intentionally omitted; sequence depends on maintainers, funding, and implementation evidence. Completion of a checklist is not equivalent to production readiness.

## Phase 1 — Foundation
- Dependencies: repository governance and license decision; API review.
- Deliverables: package structure, typed contracts, model gateway with one conformance-tested adapter, agent runtime/state machine, tool registry/policy, basic tracing, CLI, unit/property tests.
- Acceptance: clean artifact build/install; Python 3.12 support; legal/illegal state tests; denied tools never execute; provider capability mismatch fails clearly; secret canary absent from telemetry; runnable documented quickstart verified.
- Release gate: API/status review and dependency/security scan. Alpha only; no production claim.

## Phase 2 — Persistence and reliability
- Dependencies: Phase 1 contracts; TypeScript service implementation and PostgreSQL supported-version decision.
- Deliverables: Prisma schema/migrations, persistence API/adapter, durable sessions/events/checkpoints, crash recovery, idempotency/reconciliation.
- Acceptance: migration from empty and previous schema; atomic transition+event CAS; tenant isolation tests; crash-window injection; restore drill design; ambiguous effects never reported as exactly-once.
- Release gate: migration and recovery review; persistence outage behavior demonstrated.

## Phase 3 — Skills and tools
- Dependencies: policy, registry, artifact and worker boundaries.
- Deliverables: skill registry/loading/validation, HTTP scraping, optional Playwright, plugin interfaces, sandboxed execution.
- Acceptance: untrusted skill quarantine, SSRF and permission-bypass security suites, browser cleanup, worker resource limits and residual-risk review.
- Release gate: security review and supported threat model.

## Phase 4 — Advanced orchestration
- Dependencies: durable tasks/checkpoints, scheduler and budgets.
- Deliverables: bounded multi-agent execution, deterministic workflow engine, memory, optional pgvector, MCP, skill discovery.
- Acceptance: budget conservation, deadlock/cycle prevention, tenant-safe memory, workflow recovery, vector-off baseline, protocol compatibility suite.
- Release gate: concurrency/failure testing and evaluation protocol.

## Phase 5 — Developer platform
- Dependencies: stable APIs/events, authentication, deployment operations.
- Deliverables: optional inspector, distributed workers, deployment artifacts, evaluation suite, skill builder, release automation.
- Acceptance: headless SDK independent of UI; worker fencing/duplicate tests; reproducible evaluation reports; release artifacts verifiable; backup/restore evidence.
- Release gate: production-readiness criteria in [production readiness](production-readiness.md) all have recorded evidence.

## Research extensions
Adaptive context, adaptive routing, evidence-guided recovery, and skill learning proceed as isolated experiments with baselines, ablations, reproducibility manifests, privacy reviews, and no default behavior change until evidence and safety review support adoption.
