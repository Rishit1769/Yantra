# YANTRA-004 Engineering Closure (V05)

**Decision: PASS — accepted for engineering completion; not released.** This record closes the planned YANTRA-004 engineering work on the feature branch. It is not a release approval, public compatibility claim, or production readiness statement. Package version remains `0.2.0`.

This V05 closure preserves the evidence available at that milestone. Later
packaging, Python-version, and hosted matrix results are recorded in the
[RR-004 release-readiness audit](yantra-release-readiness-rr004.md); those
results do not change the scope or limitations stated below.

## 1. Milestone objective

Provide an explicit, model-independent secure tool path: per-run name allowlisting, exact permission scopes, trusted invocation-specific approval, engine-controlled dispatch authorization, and opt-in restricted subprocess execution, with clear failure handling and offline developer examples.

## 2. V01–V05 summary

- **V01 — permission policy:** immutable exact-match scopes, deny precedence, risk metadata, fail-closed evaluation, explicit tool-name allowlists, and legacy unscoped compatibility.
- **V02 — trusted approval:** host-injected providers, request/context binding, expiry, revocation, atomic process-local single-use consumption, and sanitized lifecycle traces.
- **V03 — restricted execution:** fixed worker entry point, statically registered worker IDs, strict versioned JSON IPC, bounded payloads, diagnostics, execution time, and concurrency; direct-child cancellation and timeout cleanup.
- **V04 — hardening:** removed executor key binding, made standalone public executors fail closed, engine-wrapped supplied executors, hardened startup and repeated-cancellation cleanup, and corrected source/example type errors.
- **V05 — acceptance:** reviewed the complete model-to-handler path, added regression coverage for changed arguments, run IDs, and substituted definitions against signed dispatch authority, assessed public APIs, examples, packaging and platform evidence, and recorded this closure.

No new runtime subsystem or convenience API was added.

## 3. Final public API surface

The supported composition is `ModelGateway` + `ToolRegistry` (or an existing `ToolExecutor`) + `AgentExecutionEngine.run(AgentRunConfig)`. A tool is declared with `ToolDefinition`, including its Pydantic input/output models, executor or trusted `worker_handler_id`, `permission_scopes`, risk/side-effect metadata, execution boundary, and optional timeout. `AgentRunConfig` carries the explicit `tool_names` allowlist, trusted host-provided `permission_context`, run limits, and optional token/cost accounting limits. The engine accepts an optional host-injected `ApprovalProvider`, `ApprovalStore`, and `ExecutionLimits`/`SubprocessExecutionBoundary`. Results are `AgentRunResult`/`ToolResult`; use typed fields or `format_run_result` for sanitized human-readable diagnostics.

Public exports live in `yantra.runtime` and `yantra.tools`. Internal dispatch signing, verification-key binding, and `_EngineToolExecutor` are not supported public interfaces. Standalone public `ToolExecutor.execute` cannot authorize itself. Examples of the APIs are in the [agent quickstart](../guides/agent-quickstart.md) and [secure runtime guide](../security/secure-tool-runtime.md).

## 4–5. Security architecture and trust boundaries

The model, proposed call name/arguments, and model-authored claims are untrusted. The application host, per-run grants, policy evaluator, registry, approval provider, registered Python handlers, and the host process are trusted. Before dispatch, the engine independently checks the name allowlist, required exact scopes and explicit denials; then it obtains trusted approval where policy requires it, revalidates policy/registry identity, signs the exact run/call/tool/definition/arguments/decision/approval claims, and verifies and consumes that authority once in the executor.

Approval is invocation-bound consent, not permission expansion. Process isolation means execution in a separate OS process; it is not sandboxing. The fixed worker receives bounded JSON and a registered handler ID, not signing or approval secrets. It runs with the same user authority; there are no OS-enforced filesystem/network restrictions or CPU/memory/disk quotas. The design does not defend against hostile same-process Python or a compromised host.

## 6. Security findings and resolutions

| Finding | Severity / component | Reproduction and root cause | Threat-model exploitability | Minimal fix, regression, and resolution |
|---|---|---|---|---|
| V02 callable authority issuer. | High — public `ToolExecutor` | Hold the executor, call its exposed private issuer directly, then invoke with the returned authority; issuance was not restricted to the engine policy/approval path. | Reproducible through an ordinary executor object; high-severity authorization bypass within supported API use. | V03 removed the issuer and required engine-held HMAC dispatch authority. Tests reject public ALLOW-only and caller-minted claims. Resolved. |
| V03 caller-selected verifier key. | High — executor key binding | Bind a caller-controlled key, mint matching authority, and invoke the executor; the executor accepted the caller's trust root. | Reproducible through ordinary direct executor methods; high-severity authorization bypass within supported API use. | V04 removed key binding; standalone public executors fail closed and engine construction supplies its own verifier. Regression tests cover caller-owned authority and engine wrapping. Resolved. |
| Changed dispatch arguments, run, or definition could reuse signed authority. | No vulnerability reproduced — dispatch authorization | V05 explicitly substitutes each claim independently against the same signed token. The pre-existing implementation rejects all attempts; the gap was missing direct regression coverage. | Not exploitable through tested APIs; exact values are included in signed claims and verified before dispatch. | Added V05 test asserting each substitution returns `tool_not_permitted`. No runtime fix was needed; coverage gap resolved. |
| Approval denial, expiry, cancellation, replay, or registry mutation could dispatch. | No issue found — engine and approval store | Reviewed approval request binding/expiry/revocation/atomic consumption and dispatch revalidation; no bypass reproduced. | Model-supplied approval claims are untrusted; trusted provider is host-injected. | Existing tests cover fail-closed results, late response after cancellation, request/digest/run binding, atomic consumption, and registry revalidation. No fix required. |
| Worker input could choose executable code or ambiguous protocol data. | No issue found — worker boundary | Reviewed the fixed entrypoint, static handler map, strict JSON schemas, duplicate-key rejection, limits, and error normalization; no bypass reproduced. | Model-selected executable/module/shell input is unavailable through the worker protocol. | Existing worker protocol and lifecycle tests cover malformed/duplicate data, bounded payloads, crashes, timeout, cancellation, and direct-child cleanup. No fix required. |

No unresolved critical or high-severity vulnerability was identified within the documented threat model. Same-process hostile introspection remains explicitly outside that boundary.

## 7–8. Test, analysis, and offline example evidence

At the V05 revision, the complete offline test suite passed **229 tests** (the 228-test V04 baseline plus one V05 dispatch-binding regression). Ruff lint and format checks passed; Pyright passed for `src` and `examples`; `uv lock --check` passed. All four deterministic examples passed: `agent_loop_offline.py`, `secure_tool_policy.py`, `secure_tool_approval.py`, and `secure_tool_boundaries.py`. They use offline/mock model providers and safe in-memory handlers; no live inference or real credentials were used.

The integrated paths are covered across the agent-engine and execution-boundary tests and examples: scoped allow/deny, approval allow/deny/replay, in-process and subprocess dispatch, correlation, timeout/cancellation, fail-closed public ALLOW and standalone executor, forged/replayed authority, late approval after cancellation, and changed dispatch claims. The final local commands and results were:

```text
uv lock --check                                      PASS
uv run --offline --no-sync ruff check .              PASS
uv run --offline --no-sync ruff format --check .     PASS (85 files)
uv run --offline --no-sync pyright src examples      PASS (0 diagnostics)
uv run --offline --no-sync pytest -q -p no:cacheprovider  PASS (229 tests)
python examples/agent_loop_offline.py                PASS
python examples/secure_tool_policy.py                PASS
python examples/secure_tool_approval.py              PASS
python examples/secure_tool_boundaries.py            PASS
local Markdown target scan                            PASS (175 files)
git diff --check                                     PASS
```

In this sandbox, the commands were run with the existing project environment and a writable temporary uv cache; no dependencies were installed. No hosted CI was triggered.

## 9–10. Platform and interpreter matrix

| Environment | Status | Evidence |
|---|---|---|
| macOS 26.5.1, arm64, Python 3.12.15 | Verified locally | 229 offline tests, lint, format, Pyright, lock check, and all examples passed. |
| Windows | Pending | No Windows runtime was available; no compatibility claim is made. Use the [offline platform procedure](secure-tool-platform-validation.md). |
| Python 3.13.15 | Pending | Interpreter exists, but Pydantic/pytest are absent from its environment; dependencies were not installed. |
| Python 3.14.7 | Pending | Interpreter exists, but Pydantic/pytest are absent from its environment; dependencies were not installed. |
| Hosted CI | Pending | Not run; the known billing block remains. |

Project metadata declares Python `>=3.12` and classifiers for 3.12–3.14. That metadata is not runtime verification for each interpreter or operating system.

## 11. Packaging readiness

Metadata is internally consistent at version `0.2.0`, Python `>=3.12`, Apache-2.0, and the repository README/license paths. Version is sourced from `src/yantra/_version.py`; the wheel target includes `src/yantra`; the source distribution configuration includes source, tests, docs, README, project metadata, and license. `keyring` remains an optional credentials extra; the only declared console entry point is `yantra-smoke`.

`uv lock --check` passed. A fresh wheel/sdist build and artifact inspection are **pending** because Hatchling is not present in the existing offline environment. Dependencies were not installed and existing `dist/` artifacts were not treated as fresh V05 build evidence.

## 12–13. Known limitations and compatibility

- Approval state and replay protection are in-memory and process-local; there is no durable approval recovery or replay protection across restarts.
- Approval is consumed before dispatch. External effects are not rolled back; exactly-once external effects are not promised.
- Subprocess cleanup covers the direct child only, not descendants. No OS sandbox, resource quotas, filesystem/network restrictions, or side-effect rollback are implemented.
- In-process synchronous handlers run in a thread and cannot be forcibly stopped by Python.
- YANTRA-004 retains `allow_legacy_unscoped_tools=True` for compatibility. Such tools still require explicit name allowlisting but do not require scope grants. A future major/minor migration should emit a deprecation path, let applications inventory and add scopes, then consider defaulting to strict mode only with an explicit compatibility decision; V05 does not change the default.
- Run token/cost accounting is post-response and is not a hard spending cap.

## 14–15. Release blockers and future work

This engineering acceptance does not clear release verification. Fresh wheel and source-distribution builds, Windows execution, Python 3.13/3.14 suite runs (interpreters are present but their environments are not provisioned with project dependencies), hosted CI, and a separate maintainer release decision remain outstanding. Process-tree cleanup, OS-level sandboxing/resource enforcement, and durable approval/recovery require separate designs and platform evidence; they are not implied by this milestone.

## 16. Engineering acceptance decision

**PASS — YANTRA-004 is accepted for engineering completion, not released.** The local acceptance criteria pass, no supported-threat-model critical/high finding remains unresolved, and unavailable platform/package/hosted evidence is explicitly retained as release blockers. The version remains `0.2.0`. This decision does not declare YANTRA-004 or `v0.4.0` publicly released or production-ready.
