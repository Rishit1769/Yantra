# YANTRA RR-004: Developer-Preview Release Readiness Audit

**Audit date:** 2026-10-18

**Package version:** `0.2.0` (unreleased candidate; version unchanged)

**Recommendation:** **TECHNICAL GO for RR-004 engineering acceptance**, based on the exact-SHA CI and dependency-audit evidence supplied for final closure below. GitHub could not be reached from this Codex session for independent live revalidation; no new workflow was triggered in this session.

This recommendation is an evidence-based release gate, not a statement that
the code is unsafe or that publication has been authorized. No unresolved
critical/high-severity defect was identified in the reviewed scope. No package
was published, tag/release created, version changed, branch merged, or remote
updated.

## 1. Executive summary

The source package builds reproducibly as a wheel and sdist; both install in
fresh Python 3.12 environments outside the repository. Their installed CLI
works offline, and an external script using installed public APIs completed a
mock model → tool → model cycle and returned the expected answer. The full
local suite passes on macOS with Python 3.12, 3.13, and 3.14. Provider and
security regressions, all four offline examples, Ruff, formatting, Pyright,
lock consistency, and the dependency advisory check pass.

The audit corrected stale current documentation that denied the implemented
agent loop/approval support or described Windows and hosted CI as unverified.
Historical RR-001/RR-002/RR-003 reports remain intact and are explicitly
superseded where their point-in-time status is no longer current. Four
deterministic gateway retry tests were added because that existing behavior
had no focused regression coverage.

The configured hosted matrix did pass all nine jobs in RR-003 run
[39114896871](https://github.com/Rishit1769/Yantra/actions/runs/39114896871)
on commit `2f07ec92d550f7734f844c8caaa4bd725d8b26fc`. That run predates the
RR-004 retry tests and documentation changes. Under the repository release
procedure, the exact final candidate commit still needs a passing matrix.

## 2. Scope and methodology

Reviewed repository metadata, source layout/public exports, README and
first-run guides, provider verification matrix, release notes/changelog,
security documentation, release process, CI workflow, and RR-001, RR-002,
RR-003, and YANTRA-004 engineering evidence. Inspected gateway retry/routing,
budget code/tests, provider adapter tests, tool-policy tests, execution-boundary
tests, and installed package behavior. No live provider, credential, keychain,
or billable inference request was made.

Validation used fresh local builds, two independent build output directories,
new wheel/sdist environments under `/tmp`, and an external consumer run from
`/private/tmp` with `PYTHONPATH` unset. Disposable Python 3.13/3.14 environments
were kept under `/tmp`; the repository `.venv` was not replaced. Historical
hosted CI is reported separately from current local validation.

## 3. Repository and environment

| Item | Evidence |
|---|---|
| Working branch | `audit/yantra-rr004-developer-preview` |
| Starting commit | `df951c46076a7cb85198cf0682724e4e3ab55e9b` |
| Starting worktree | Clean |
| Host | macOS 26.5.1, arm64 |
| Project/tool environment | CPython 3.12.15; uv 0.13.0 |
| Additional Python | CPython 3.13.15 and 3.14.7, isolated environments |
| Package version | `0.2.0`, from `src/yantra/_version.py` |
| Lockfile | 35 resolved packages; unchanged |

The task instructions and repository `AGENTS.md` were followed; `AGENTS.md`
was not modified. Artifacts and fresh environments were written under `/tmp`.

## 4. Packaging and installation — PASS

**Evidence and checks**

- `uv sync --locked --all-extras` succeeded. Separate locked development
  environments were also synchronized for Python 3.13 and 3.14.
- `uv build --out-dir /tmp/yantra-rr004-final-dist` built
  `yantra-0.2.0-py3-none-any.whl` and `yantra-0.2.0.tar.gz`; a second build to
  `/tmp/yantra-rr004-repeat-dist` produced byte-identical wheel and sdist.
- The wheel has 65 entries; the sdist has 251. The wheel includes the package,
  `py.typed`, root Apache license, metadata, and `yantra-smoke` entry point.
  Metadata reports `Name: yantra`, `Version: 0.2.0`,
  `Requires-Python: >=3.12`, and `License-Expression: Apache-2.0`.
- All 59 Python modules in each distribution are present and byte-identical
  to the checkout. All 64 hashed wheel `RECORD` entries validated. The fresh
  wheel SHA-256 is
  `b260465b056f785db2518f4ceceac0cc3542bede38a8f60ea224a5557a3d6984`;
  two wheel builds and two sdist builds were byte-identical. (The sdist
  includes this report, so its digest is intentionally not embedded in itself.)
- Runtime dependencies are `httpcore`, `httpx`, and `pydantic`; optional
  `keyring` remains in the `credentials` extra. Build requirements remain
  isolated to Hatchling; developer/test dependencies are not runtime
  requirements. Python support metadata is `>=3.12`, with classifiers for
  3.12, 3.13, and 3.14.
- Archive review found no `.env`, `.git` internals, `__pycache__`, `.pyc`, or
  log files. The `yantra/security/credentials.py` entry is ordinary source
  code, not a credential file. No lockfile or dependency change was needed.
- Fresh wheel and sdist installs each resolved 12 packages in distinct
  Python 3.12.15 environments outside the checkout. Both imported from their
  own `site-packages` (`yantra.__file__` and installed metadata version
  `0.2.0` were checked), and `yantra-smoke --help`, `offline`, and `providers`
  passed without network provider requests. Clean installs resolved Pydantic
  2.14.1 within the declared range; locked test environments use 2.14.0.
- `uv audit --locked` found no known vulnerabilities or adverse project
  statuses in 34 packages. The uv audit command identifies itself as
  experimental; this is advisory evidence, not a comprehensive security scan.

**Findings / remaining work:** No packaging blocker found. RR-004 local build
and install evidence is on macOS/Python 3.12. The hosted RR-003 workflow also
builds and tests installed-wheel CLI behavior across its nine matrix jobs and
sdist CLI behavior on Ubuntu/Python 3.12. The exact RR-004 commit's hosted
build/install matrix remains **NOT VERIFIED**.

## 5. Developer experience — PASS

**Evidence and checks**

- Updated README and installation/quickstart documentation to identify
  `0.2.0` as unpublished and show the locked source setup plus the runnable
  offline agent command and expected final answer.
- Updated current docs to describe the implemented bounded agent loop and
  trusted host-injected approval path. Clarified that the smoke CLI is not a
  general-purpose agent runner and that examples are not included in
  distributions.
- In a fresh wheel environment, from `/private/tmp` and with `PYTHONPATH`
  removed, a standalone Python script imported the installed gateway, mock
  provider contract, agent engine/configuration, and tool registry. It
  registered a typed calculator, executed a complete model-tool-model cycle,
  and asserted `The sum is 42.` and one tool result. It did not use editable
  installation, repository imports, private runtime APIs, credentials, or
  network access.
- The fresh sdist environment independently passed package imports and the
  offline CLI checks. The script consumer was exercised from the wheel
  environment; sdist consumes the same package source but was not separately
  used for that model-tool-model script.

**Findings / remaining work:** No public API usability blocker found. The API
is experimental and pre-1.0; the package is not available from PyPI. A
maintainer must separately authorize any distribution or publication.

## 6. Provider integration — CONDITIONAL PASS

**Evidence and checks**

- Ran provider/gateway tests across `test_provider.py`,
  `test_provider_adapters.py`, `test_provider_transport.py`, and
  `test_gateway_foundation.py`: **65 passed**.
- Added four offline regressions in `tests/unit/test_gateway_foundation.py`:
  approved retry of a retryable transient error, no retry for a
  non-retryable failure, bounded retry exhaustion, and fail-closed rejection
  of multiple attempts without routing-policy approval.
- Ran 15 focused tests selected for retry/routing/budget behavior across the
  gateway and agent engine: **15 passed** (51 deselected). Existing tests
  cover approved automatic routing, unavailable providers, explicit fallback,
  model selection, and cost/token budget outcomes.
- Reviewed adapters and the provider verification matrix for OpenAI,
  Anthropic, Gemini, DeepSeek, OpenRouter, OpenCode Zen/Go, Ollama, and the
  generic OpenAI Chat Completions-compatible subset. Offline adapter tests
  use mocked transports. Endpoint restrictions, timeout/error normalization,
  streaming normalization, usage, and capability gates remain covered by
  adapter/transport tests.

**Findings / limitations:** No live provider request was made. Mock tests and
the hosted CI matrix do not establish live provider, model, account, region,
or entitlement compatibility. The matrix's narrow OpenCode Go evidence is
user-reported and not independently repeated. Provider-specific tool calling
and structured output remain unknown unless explicitly established; unknown
capabilities fail closed. Retry defaults to one attempt; retries can repeat
billable inference. Additional coverage for cancellation during retry delay
and provider-specific `Retry-After` edge cases remains a non-blocking coverage
gap.

## 7. Security and execution boundaries — CONDITIONAL PASS

**Evidence and checks**

- Ran the requested `tests/unit/test_tool_policy.py` and
  `tests/unit/test_execution_boundary.py`: **45 passed** on macOS/Python 3.12.
  The full 233-test suite also includes the agent authorization/approval and
  worker lifecycle regressions.
- Reviewed name allowlists, exact scope grants, denial precedence, trusted
  approval binding/expiry/cancellation/replay, registry identity revalidation,
  HMAC dispatch authorization, fail-closed public executor behavior, strict
  JSON protocol and size limits, static worker identifiers, concurrency/time
  limits, direct-child cleanup, cancellation races, and diagnostic
  sanitization. Existing tests cover the documented supported boundaries.
- No production runtime or security policy code changed in RR-004. Added tests
  exercise gateway retries only. No credentials were inspected or printed.
- RR-003 hosted CI run 39114896871 passed the worker-related suite on all
  three OSes and all three Python versions. This is CI test evidence, not a
  guarantee for every Windows configuration or an OS-level security control.

**Accepted limitations:** The Python host and registered host code are
trusted. The worker subprocess is not an OS sandbox; filesystem/network access
and ambient same-user authority are not isolated. CPU, memory, and disk quotas,
descendant process cleanup, durable approval replay protection, exactly-once
effects, rollback of committed side effects, and forced termination of
synchronous in-process handlers are unsupported. Cost/token accounting is not
a hard spending ceiling.

**Important non-blocking finding:** `SECURITY.md` still has no dedicated
security contact configured. Before broader public promotion, maintainers
should establish a private reporting channel and response process. No
critical/high finding was identified in the reviewed scope; this is not an
independent certification or penetration test.

## 8. Release docs and metadata — PASS after corrections

Corrected active README, changelog, quickstart, installation, first-agent,
feature-matrix, API/gateway architecture, security, platform-validation,
smoke-testing, coding standards, release-notes, setup, roadmap, and index
statements that were stale about the agent loop, approval support, package
contents, Python versions, and Windows/hosted CI. Added links to RR-004 and the
verified RR-003 run. Clarified the historical status of the YANTRA-004 closure
and updated the release process to require exact-final-candidate CI. Preserved
dated RR-001, RR-002, RR-003, RR-002 release audit, and milestone history;
those documents describe their original evidence and are not rewritten as if
they had known later results.

Metadata remains consistently at package `0.2.0`, Python `>=3.12`, and SPDX
`Apache-2.0`; the wheel confirms the modern `License-Expression` field and
license inclusion. No version bump, tag, release, or publication was made.

## 9. Tests and CI evidence

### RR-004 local validation (macOS)

| Check | Result |
|---|---|
| Full suite, Python 3.12.15 | **233 passed** |
| Full suite, Python 3.13.15 | **233 passed** |
| Full suite, Python 3.14.7 | **233 passed** |
| Provider/gateway focused files, Python 3.12.15 | **65 passed** |
| Tool-policy and execution-boundary files, Python 3.12.15 | **45 passed** |
| Focused retry/routing/budget selection, Python 3.12.15 | **15 passed, 51 deselected** |
| Four offline examples | **4/4 passed on Python 3.12, 3.13, and 3.14** |
| `ruff check .` | **PASS** |
| `ruff format --check .` | **PASS; 85 files already formatted** |
| `pyright` | **PASS; 0 errors, warnings, or information diagnostics** |
| `uv lock --check` | **PASS; 35 packages resolved, lock unchanged** |
| `uv audit --locked` | **PASS; no known vulnerability/adverse status in 34 packages** |
| `git diff --check` | **PASS** |

The focused counts overlap the full suite; they are not additive. Ruff,
formatting, Pyright, and dependency audit were run with the locked Python 3.12
tool environment. The suite and examples were run with separate locked Python
3.12/3.13/3.14 environments on macOS.

### Hosted CI (historical RR-003)

GitHub Actions run
[39114896871](https://github.com/Rishit1769/Yantra/actions/runs/39114896871)
completed successfully on 2026-10-18 for head
`2f07ec92d550f7734f844c8caaa4bd725d8b26fc`: all nine
Ubuntu/macOS/Windows × Python 3.12/3.13/3.14 jobs succeeded. The workflow's
test, wheel/sdist build, installed-wheel CLI checks, and Ubuntu/Python 3.12
sdist CLI checks passed in their applicable jobs; lint/type/audit ran on
Ubuntu/Python 3.12. RR-004's four new gateway tests and documentation changes
are not present in that run. The subsequent final RR-004 evidence is recorded
below.

### Final RR-004 CI and dependency-audit evidence

The final closure brief supplied two successful workflow records for commit
`5a89991ebd3c46c9478fb10849ae7db736becd85`:

| Workflow | Supplied result | Coverage |
|---|---|---|
| [Push workflow, run 39122672600](https://github.com/Rishit1769/Yantra/actions/runs/39122672600) | **success, 9/9 jobs** | Ubuntu, macOS, Windows × Python 3.12, 3.13, 3.14 |
| [Pull-request workflow, run 39122682064](https://github.com/Rishit1769/Yantra/actions/runs/39122682064) | **success, 9/9 jobs** | Ubuntu, macOS, Windows × Python 3.12, 3.13, 3.14 |

The supplied evidence states both run heads matched that SHA, for 18 successful
matrix jobs total and zero failed, cancelled, skipped, or pending checks. The
closure brief also reports two successful `uv audit --locked` runs: 34
packages audited, no known vulnerabilities or adverse project statuses.

These are records supplied for this closure, not live queries performed in
this session. `gh auth status` reports an invalid token; `gh pr view 4` could
not connect to `api.github.com`, and the independent run URLs could not be
fetched. This session did rerun the full 233-test suite, Ruff lint and format
checks, Pyright, lock verification, wheel/sdist build, and all four offline
examples successfully. A fresh `uv audit --locked` attempt failed to resolve
`api.osv.dev` because DNS lookup failed; this session's audit is therefore
**NOT VERIFIED**, not a pass. The reported prior successful audits are kept
distinct from this failed-to-connect attempt.

The supplied local evidence also reports clean installation checks and a
successful external-consumer agent run. Those are historical results and were
not rerun in this closure session.

## 10. Findings register

| ID | Severity / category | Finding | Status / remediation |
|---|---|---|---|
| RR4-01 | Documentation inconsistency | Quickstart said approvals were unavailable and Windows/hosted CI were unverified. | **Resolved:** active docs now describe the implemented host-injected approval flow and cite the actual RR-003 matrix; history retained. |
| RR4-02 | Documentation inconsistency | README/release notes/matrices said no agent loop and YANTRA-004 was absent from the candidate. | **Resolved:** current docs updated; historical audits preserved. |
| RR4-03 | Coverage gap | Gateway retry execution had no focused retry tests despite an existing retry implementation. | **Resolved:** added four deterministic tests for approved retry success, non-retryable refusal, exhaustion, and approval fail-closed; all pass. |
| RR4-04 | Release gate | Exact-final-commit hosted matrix was absent at the original audit. | **Resolved by supplied evidence:** push and PR runs 39122672600 and 39122682064 report 9/9 passing jobs each on `5a89991ebd3c46c9478fb10849ae7db736becd85`; live records could not be independently queried in this closure session. |
| RR4-05 | Important non-blocking issue | No dedicated private security reporting contact is configured. | **Open:** maintainer should establish a channel and response process before wider public promotion. |
| RR4-06 | Accepted limitation | Live provider/model/account compatibility is mostly not independently verified. | **Accepted for offline developer preview:** keep capability gates truthful; do not infer live support from mocks. |
| RR4-07 | Accepted limitation | Restricted worker is not an OS sandbox and does not promise descendant/resource controls. | **Accepted/documented:** no unsupported isolation claims. |
| RR4-08 | Accepted limitation | Cost/token budgets and approval replay are not hard/durable guarantees. | **Accepted/documented:** accounting is post-response/best-effort; approval store is process-local. |

## 11. Area disposition

| Area | Status | Evidence and remaining work |
|---|---|---|
| Packaging/install | **PASS** | Reproducible fresh artifacts, metadata/content inspection, clean wheel and sdist installs, external CLI checks; supplied exact-SHA hosted matrix includes wheel/sdist build checks where configured. |
| Developer experience | **PASS** | Current install/quickstart docs and external installed-package agent cycle pass. API is experimental; version is not published. |
| Provider integration | **CONDITIONAL PASS** | 65 provider/gateway tests; live provider matrix is mostly mock/unknown. Retry tests added; further delay-hint/cancellation coverage remains non-blocking. |
| Security/execution | **CONDITIONAL PASS** | 45 focused security tests; full suite and historical hosted matrix pass. Scope limits and residual risks are explicit; no independent certification. |
| Release docs/metadata | **PASS** | Current docs reconciled, metadata consistent, historical reports preserved. Dedicated security contact remains an important open action. |
| Exact candidate CI | **PASS (supplied evidence)** | Two supplied RR-004 workflow records report all nine jobs passing on `5a89991ebd3c46c9478fb10849ae7db736becd85`; GitHub was unavailable for an independent query in this session. |

## 12. Remaining release blockers and recommendation

**Technical verdict: GO for RR-004 engineering acceptance**, based on the
supplied successful exact-SHA push and PR matrix records plus the supplied
dependency-audit results and local validation evidence. This GO is conditional
on the accuracy of those supplied records; this Codex session could not
independently query them. If this report is committed and pushed, that new
final documentation commit must pass the complete matrix before it is
considered CI-verified.

The runtime is not an OS sandbox, live provider compatibility is not
comprehensively verified, and approval replay protection remains process-local.
Maintainer approval is still required. Technical GO does not authorize merge,
tagging, publishing, or release. Before broader public promotion, maintainers
should establish a private security-reporting contact.

Before a developer preview, a release owner must review this audit and
explicitly approve the release. These are separate decisions; this report and
its technical GO do not authorize tagging, publishing, merging, or deployment.

No release tag, GitHub release, PyPI upload, version change, merge, or live
provider call occurred during RR-004. No push was performed in this closure
session because GitHub authentication and connectivity were unavailable.
