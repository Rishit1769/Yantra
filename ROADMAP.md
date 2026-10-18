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

**Engineering verification: PASS. Public release: NO-GO.** Local macOS/Python 3.12 checks passed (229 tests, quality checks, examples, and security regression files). Static inspection found the existing ignored `0.2.0` wheel and sdist do not match the current checkout; Hatchling/build frontend are unavailable, preventing a fresh build and clean install. Python 3.13/3.14 environments lack project dependencies, Windows is unavailable, and hosted CI remains blocked. See the [RR-001 release-readiness evidence](docs/development/yantra-release-readiness-rr001.md) for exact statuses and corrective actions.

## YANTRA-RR-002 Packaging and Python Compatibility

**Engineering verification: PASS. Public release: NO-GO.** Fresh `0.2.0` wheel and sdist builds match current source; separate builds were byte-identical, and a wheel rebuilt from the sdist matched the direct wheel. Clean wheel installs passed on Python 3.12/3.13/3.14, clean sdist install passed on Python 3.12, and all 229 tests plus four offline examples passed on each interpreter. Windows runtime, hosted CI, and maintainer release approval remain outstanding. See the [RR-002 release-readiness evidence](docs/development/yantra-release-readiness-rr002.md) for artifact hashes and exact validation scope.

## YANTRA-RR-003 Windows CI Hang

**Engineering verification: INCOMPLETE. Windows CI: INCOMPLETE.** Existing Actions logs identify a brittle 50 ms timeout race and unbounded event wait in the test `test_timeout_racing_completed_worker_has_deterministic_timeout_result`. The regression now uses an immediate deterministic boundary result; pytest also emits a faulthandler stack after 120 seconds, with a 15-minute job limit. The corrected suite passes locally on macOS/Python 3.12–3.14, but the fix branch has not run on Windows because no push or workflow trigger was authorized. See the [RR-003 Windows CI hang report](docs/development/yantra-rr003-windows-ci-test-hang.md).
