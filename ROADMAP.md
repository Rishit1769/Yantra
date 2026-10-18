# YANTRA Roadmap

This roadmap is a proposed sequence, not a delivery-date promise. YANTRA-001 implemented the package/contract foundation. YANTRA-002 implemented a model gateway foundation with mocked adapter coverage; live provider compatibility is unverified. Execution and integration milestones remain incomplete.

1. **Foundation:** packaging, typed contracts, provider-neutral gateway, async agent runtime/state machine, controlled tool registry/execution, basic tracing, CLI, unit tests. Package/contracts/mock/registry/state/storage/logging/tests and YANTRA-002 gateway/adapters with mocked HTTP tests are in place. YANTRA-003 adds a bounded local execution loop, explicit per-run tool-name authorization, usage/limit handling, and sanitized diagnostics. A general authorization/scope policy engine, live provider verification, tracing backend, and general-purpose agent CLI remain unimplemented.
2. **Persistence and reliability:** PostgreSQL schema, TypeScript Prisma service, Python adapter, sessions, events, checkpoints, crash recovery, idempotency.
3. **Skills and tools:** skill registry/loading/validation, HTTP scraping, optional browser automation, plugins, sandboxed execution.
4. **Advanced orchestration:** bounded multi-agent execution, workflows, memory, optional pgvector, MCP, skill discovery.
5. **Developer platform:** optional inspector, distributed workers, deployment support, evaluations, skill builder, release automation.

Research extensions (adaptive context/routing, evidence-guided recovery, skill learning) remain experimental and are not prerequisites for baseline usability. Phase dependencies, acceptance conditions, and release gates are in [milestones](docs/roadmap/milestones.md), [feature dependencies](docs/roadmap/feature-dependencies.md), and [production readiness](docs/roadmap/production-readiness.md). Feature completion does not itself mean production-ready.

## YANTRA-004 Secure Tool Runtime — V05 Engineering Closure

**Decision: PASS — accepted for engineering completion; not released.** V01–V04 provide exact-scope policy, trusted invocation-bound approval, engine-owned single-use dispatch authorization, and opt-in fixed-handler subprocess execution. V04 removed the public executor key-binding bypass and hardened startup/cancellation cleanup. V05 reviewed the full model-to-handler path and added dispatch-claim substitution regression coverage. Final local evidence is 229 passing offline tests, passing Ruff and Pyright checks, passing `uv lock --check`, and four successful deterministic examples on macOS 26.5.1/arm64/Python 3.12.15. Windows, Python 3.13/3.14, hosted CI, and a fresh package build remain release blockers. Subprocess execution is not a sandbox; package version remains `0.2.0`. See the [engineering closure](docs/development/yantra-004-engineering-closure.md) for findings, trust boundaries, API, limitations, and evidence.

## YANTRA-RR-001 Release Readiness

**RR-001 historical decision: engineering verification PASS; release NO-GO at that time.** Its 229-test macOS/Python 3.12 run and packaging/hosted blockers are preserved in the [RR-001 evidence](docs/development/yantra-release-readiness-rr001.md); later RR-002/RR-003/RR-004 evidence supersedes those point-in-time blockers.

## YANTRA-RR-002 Packaging and Python Compatibility

**RR-002 historical decision: engineering verification PASS; release NO-GO at that time.** It verified reproducible package artifacts, clean installs, and Python 3.12–3.14 on macOS. Its then-pending Windows/hosted status was superseded by RR-003; retain the original [RR-002 evidence](docs/development/yantra-release-readiness-rr002.md) for exact scope.

## YANTRA-RR-003 Windows CI Hang

**Engineering verification: PASS for the tested matrix.** RR-003's [Actions run 39114896871](https://github.com/Rishit1769/Yantra/actions/runs/39114896871) passed all nine Ubuntu/macOS/Windows × Python 3.12/3.13/3.14 jobs on commit `2f07ec9`, closing the Windows test hang. The earlier canceled evidence and diagnosis remain recorded in the [RR-003 report](docs/development/yantra-rr003-windows-ci-test-hang.md); the report's final closure section records the successful run.

## YANTRA-RR-004 Developer-Preview Readiness

**Recommendation: NO-GO for release from this audit branch.** RR-004 freshly built reproducible `0.2.0` artifacts, installed wheel and sdist outside the checkout, completed an external public-API model/tool/model cycle, passed 233 local tests on Python 3.12/3.13/3.14, corrected stale current documentation, and added retry regressions. The exact RR-004 final commit has not run hosted CI; the RR-003 result does not include its added tests. No live provider calls, push, tag, or publication occurred. See the [RR-004 report](docs/development/yantra-release-readiness-rr004.md) for area-level findings and exact release gates.
