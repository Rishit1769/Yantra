# Milestones

All dates are intentionally omitted; sequence depends on maintainers, funding, and implementation evidence. Completion of a checklist is not equivalent to production readiness.

## Phase 1 — Foundation
- Dependencies: repository governance and license decision; API review.
- Deliverables: package structure, typed contracts, model gateway with one conformance-tested adapter, agent runtime/state machine, tool registry/policy, basic tracing, CLI, unit/property tests.
- Current progress: YANTRA-001 implements packaging, contracts, mock provider, tool registry, state transitions, events, in-memory storage, logging, tests, and CI configuration. YANTRA-002 adds the model gateway and provider adapters with mocked HTTP coverage; YANTRA-002-V01 adds a limited developer smoke CLI. YANTRA-003 provides an experimental bounded local agent loop and a deny-by-default per-run tool-name allowlist; a general scope/policy engine, live provider compatibility, tracing backend, general-purpose CLI, and hosted cross-platform CI execution remain unverified or unimplemented.
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

## YANTRA-003 Engineering Closure

**Decision: ACCEPTED for engineering completion; not released.** The bounded execution engine composes the existing model gateway and tool registry, supports per-run name allowlists with deny-by-default behavior, bounded run controls, normalized failure/cancellation handling, and sanitized diagnostics. Tool registration alone does not authorize execution. Declared permission scopes are descriptive; no general authorization-policy engine is implemented. Usage/cost checks are best-effort accounting and do not guarantee a strict spending ceiling.

**Acceptance evidence:** The independent R05 audit recorded 184 passing tests, passing Ruff and Pyright checks, and a successful repeatable offline agent demonstration; it also verified the configured CI matrix but did not have hosted job results. R05 reported the security and cost-accounting findings addressed by R01/R04 as remediated. This R06 change corrects the contradictory API status statement and reconciles milestone documentation; it does not represent a fresh full-suite, build, or hosted-CI run.

**Residual limitations:** No general scope/policy engine or isolated execution sandbox; synchronous tool work may outlive cancellation; no durable run recovery or exactly-once external effects; token/cost accounting is not a hard ceiling. A fresh `0.3.0` package build and hosted macOS/Windows CI results remain unverified.

**Release disposition:** Package version remains `0.2.0`; YANTRA-003 is experimental, is not included in that package, and has no public release approval. Release readiness remains **NOT READY / NO-GO** pending fresh release-artifact verification, hosted CI evidence, and a separate maintainer release decision. Engineering acceptance does not authorize publishing, tagging, merging, or deployment.

## YANTRA-004-V01 Secure Tool Runtime Foundation

**Status: Implemented and locally verified on `feat/yantra-004-secure-tools`; not released.** V01 adds validated exact-match permission scopes, tool risk labels, immutable policy request/context/decision contracts, and a deterministic evaluator. The engine enforces the existing name allowlist independently, requires all declared scopes, gives explicit scope denials precedence, treats approval-required as non-executable, and fails closed on evaluator errors. The executor requires an explicit ALLOW decision. Legacy unscoped tools preserve the prior name-allowlist behavior only when `allow_legacy_unscoped_tools` is enabled; scoped tools cannot use this compatibility path.

**Verification evidence:** 208 offline tests passed, including 24 new policy and handler-non-execution tests; Ruff, formatting, Pyright, and `uv lock --check` passed. Both scoped allow/deny and the existing legacy offline demonstrations completed without network or credential access. This local macOS run does not establish Windows behavior or hosted CI. MkDocs was not installed in the locked environment; edited Markdown links were checked directly.

**Boundary:** V01 supplies logical in-process authorization, not an OS sandbox, side-effect enforcement backend, general policy language, approval workflow, durable recovery, or exactly-once effects. The feature remains experimental, is not included in package version `0.2.0`, and does not constitute release approval.

## YANTRA-004-V02 Trusted Tool Approvals and Side-Effect Boundaries

**Status: Implemented for local verification on `feat/yantra-004-secure-tools`; not released.** V02 adds host-injected approval providers, immutable request/decision contracts, canonical SHA-256 argument and authorization binding, request expiry, atomic in-memory single-use consumption, cancellation revocation, policy/registry revalidation, sanitized approval trace categories, and private executor-instance capabilities. Tools requiring approval are advertised only when a trusted provider is configured. The provider cannot expand name or scope authority.

**Verification evidence:** 214 offline tests passed, including concurrent consumption, cancellation, provider failure, forged public ALLOW, binding, and registry-mutation cases. Ruff lint/format and Pyright passed; `uv lock --check` passed; the approval and V01 offline examples completed. This is a local macOS run only; Windows and hosted CI remain unverified. Package build was not run because `hatchling` is absent from the existing environment and the milestone forbids installing dependencies.

**Boundary:** The store is process-local and non-durable. Consumption occurs before dispatch, so a failed dispatch spends approval; external side effects are not rolled back and exactly-once behavior is not promised. No process isolation, OS sandbox, or protection from hostile in-process Python is provided. The exact commit is recorded in the engineering completion report.

## YANTRA-004-V03 Restricted Execution Boundaries and Cancellation Hardening

**Status: Implemented and locally verified on `feat/yantra-004-secure-tools`; not released.** V03 adds an opt-in, fixed-entrypoint subprocess boundary with statically allowlisted handler IDs, versioned strict JSON IPC, request/response/diagnostic limits, bounded worker concurrency and execution deadlines. Authorization and approval remain in the parent; signed authorization is bound to the exact run, call, tool definition, arguments, decision and approval state, and is consumed once before dispatch. Cancellation and timeout terminate, wait for, and if necessary kill/reap the direct child. Safe worker failure categories are exposed without raw worker diagnostics.

**Security review disposition:** The review confirmed V01/V02 name/scope/approval enforcement and identified the V02 executor capability-issuer method as a confirmed authorization defect: a caller holding the executor could invoke the private issuer without engine policy/approval flow. V03 removes that issuer and replaces dispatch with engine HMAC authorization verification and single-use consumption; forged, stale/replayed, wrong-argument, and public-ALLOW-only calls are rejected. The signer/verifier remains an in-process trust boundary, not a defense against hostile Python introspection or code in the host process. Subprocess mode is restricted execution, **not an OS sandbox**: it does not constrain filesystem/network/user authority, impose OS CPU/memory/disk quotas, track/kill descendants, or roll back effects. In-process synchronous handlers remain non-killable.

**Verification evidence:** 222 offline tests passed, including new policy-before-dispatch, approval gating, token forgery/replay, subprocess protocol/error/limit, timeout/cancellation, and cleanup tests. Ruff lint and formatting passed; Pyright passed for `src` and the new V03 example; `uv lock --check` passed. The V01, V02, and V03 offline examples completed. Package build was not run because `hatchling` is absent and dependencies were not installed. Local macOS only; Windows and hosted CI remain unverified. Pyright across all examples still reports five existing errors in the V01/V02 examples; the changed runtime and V03 example are clean.

**Disposition:** Package version remains `0.2.0`; no package release, push, tag, merge, or deployment was performed. Engineering completion does not constitute release approval.
