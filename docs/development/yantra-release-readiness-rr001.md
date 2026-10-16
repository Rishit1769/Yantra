# YANTRA Release Readiness Evidence (RR-001)

**RR-001 engineering verification: PASS. Public release readiness: NO-GO.**
This record distinguishes executed validation from static review and blocked
checks. It is not a production-readiness statement or release authorization.
Package version remains `0.2.0`.

## 1. Repository baseline

| Item | Evidence |
|---|---|
| Starting branch / commit | `feat/yantra-004-secure-tools` / `f41d0e729e86dc33fe37c96f04dd8af0c204ffd2` |
| Starting worktree | Clean |
| RR-001 branch | `chore/yantra-rr001-release-readiness`, created from the verified starting commit |
| Package version | `0.2.0`, from `src/yantra/_version.py` |
| Prior baseline | 229 tests; YANTRA-004 engineering closure accepted, not released |

The package version was not changed. No push, merge, tag, publication,
deployment, hosted workflow, credential access, or live inference was performed.

## 2. Packaging audit — static review

Inspected `pyproject.toml`, `uv.lock`, package source layout, public exports,
and `dist/` contents.

- Distribution name is `yantra`; version is dynamically read from
  `src/yantra/_version.py`; declared Python requirement is `>=3.12`.
- Build system is Hatchling (`hatchling>=1.27,<2`,
  `hatchling.build`). Wheel package selection is `src/yantra`; the source
  distribution includes `src/yantra`, tests, docs, `README.md`,
  `pyproject.toml`, and `LICENSE`.
- Metadata references `README.md` and `LICENSE`, uses Apache-2.0 metadata, and
  declares `py.typed` in the source package. The only console entry point is
  `yantra-smoke = yantra.devtools.smoke:main`.
- Runtime imports of Pydantic, HTTPX, and HTTP Core match declared runtime
  dependencies. Development tools are in the `dev` dependency group. `keyring`
  is imported lazily and declared only in the optional `credentials` extra.
- Lock metadata lists the same runtime and optional dependencies.
- No packaging configuration defect requiring a source change was found by
  static review. The current source-distribution inclusion rules contain the
  source and project files needed for an independent build, but that build was
  not executed.

## 3–5. Build, artifacts, and clean installation

**Fresh wheel/sdist build: BLOCKED.** Neither Hatchling nor the `build` package
is installed in the existing Python 3.12 project environment. They were not
installed. No new artifacts were produced in RR-001.

Ignored local files already existed in `dist/`, including `0.1.0` and
`0.2.0` wheel/sdist artifacts. Metadata inspection of the `0.2.0` wheel found
version `0.2.0`, `Requires-Python: >=3.12`, 54 Python modules, and `py.typed`.
However, comparison against this checkout showed that both the wheel and sdist
omit these current modules: `yantra/tools/_worker.py`, `approvals.py`,
`execution.py`, `policy.py`, and `subprocess_boundary.py`. Seven overlapping
Python modules also differ from the working source. These artifacts therefore
are **stale relative to this checkout** and cannot validate the current source
or be used as RR-001 build evidence. Their provenance was not established.

**Artifact contents:** Existing artifacts were inspected read-only for
metadata, package module inventory, version source, README/license/tests/docs
presence, `py.typed`, and obvious `.env`, `.git`, and `__pycache__` entries.
This is inspection of stale artifacts, not a current artifact validation.

**Fresh isolated install: BLOCKED.** No valid RR-001 wheel or sdist was built.
The existing artifacts are stale, and creating a clean environment with
resolved dependencies would require installing packages, which this task
prohibits without permission. Existing-environment imports and CLI checks below
are not installation evidence.

## 6. Python compatibility matrix

| Python | Environment available | Tests | Examples | Worker lifecycle | Result |
|---|---|---|---|---|---|
| 3.12.15 | Yes; existing `.venv` has locked project dependencies | 229 passed | All four passed | Full suite plus boundary example passed on macOS | **PASS locally** |
| 3.13.15 | Interpreter available; Pydantic and pytest absent | Not run | Not run | Not run | **BLOCKED**; dependencies not installed |
| 3.14.7 | Interpreter available; Pydantic and pytest absent | Not run | Not run | Not run | **BLOCKED**; dependencies not installed |

No result is inferred across interpreters.

## 7. macOS validation — executed

Environment: macOS 26.5.1, arm64, Python 3.12.15. The following checks passed
using the pre-existing project environment; `uv run` was invoked with
`--offline --no-sync` and a writable temporary uv cache, so it did not install
dependencies:

```text
uv lock --check                                      PASS
uv run --offline --no-sync ruff check .              PASS
uv run --offline --no-sync ruff format --check .     PASS (85 files)
uv run --offline --no-sync pyright src examples      PASS (0 diagnostics)
uv run --offline --no-sync pytest -q -p no:cacheprovider  # PASS (229 tests)
uv run --offline --no-sync pytest -q -p no:cacheprovider tests/unit/test_tool_policy.py tests/unit/test_execution_boundary.py  # PASS (45 tests)
```

All deterministic examples passed: `agent_loop_offline.py`,
`secure_tool_policy.py`, `secure_tool_approval.py`, and
`secure_tool_boundaries.py`. `import yantra` and selected public API imports
worked from the checkout environment, reporting version `0.2.0`. The existing
`yantra-smoke --help` and `yantra-smoke offline` entry point commands passed.
These do not establish a clean wheel/sdist installation.

The full suite includes policy and approval handling, HMAC authorization,
worker protocol, timeout/cancellation cleanup, and capacity recovery. The
subprocess example also completed success, denial, and timeout cases. No
sandbox or descendant-process guarantee is claimed. No runtime warnings or
skipped tests appeared in the recorded pytest output.

## 8. Windows validation — blocked

No Windows runtime is accessible in this environment. Windows validation is
**BLOCKED**, not simulated. Follow
[`secure-tool-platform-validation.md`](secure-tool-platform-validation.md)
from a provisioned Windows checkout to verify the full offline suite, examples,
worker startup/protocol, timeout/cancellation/reaping, capacity recovery,
paths/environment, and CLI. Hosted CI remains unavailable due to the known
billing issue.

## 9. Security regression results

The focused files `tests/unit/test_tool_policy.py` and
`tests/unit/test_execution_boundary.py` passed: **45 tests**. The full suite
also passed: **229 tests**. Existing coverage includes explicit allowlisting,
scope denial and precedence, trusted approval provider binding/expiry/replay/
cancellation, public ALLOW and token forgery/replay rejection, run/argument/
definition binding, standalone executor fail-closed behavior, registry
mutation, strict worker protocol and size bounds, timeout/cancellation, and
worker capacity recovery. No source security-boundary change was made in RR-001.
This is a repository regression run, not an independent security audit.

## 10. CI readiness — static review only

The existing `.github/workflows/ci.yml` parsed successfully with Ruby Psych.
This confirms YAML syntax only; `actionlint` and GitHub schema validation were
not available, and the workflow was not triggered.

Static inspection found:

- A 3×3 matrix for Ubuntu, macOS, Windows and Python 3.12, 3.13, 3.14.
- Dependency setup uses `uv sync --locked --all-groups` and `uv lock --check`.
- Tests and wheel builds run on every matrix entry. Wheel CLI smoke cases run
  outside the checkout. Sdist CLI smoke cases run on Ubuntu/Python 3.12.
- Ruff, formatting, Pyright, and `uv audit --locked` run on Ubuntu/Python 3.12.
- Workflow permissions are globally `contents: read`; checkout credentials are
  not persisted. No secret references or unnecessary write permissions were
  found.
- Hosted matrix results, build artifacts, and actual GitHub runner behavior
  remain unverified because hosted CI was not triggered.

## 11. Quality checks and documentation

All available local checks passed as listed in the macOS section. Markdown
local-target validation passed for 176 repository Markdown files; `git diff
--check` passed. This evidence document records the packaging audit, artifact
mismatch, platform matrix, CI review, and distinct engineering/release
decisions. No runtime, packaging, or workflow configuration fix was made;
there is no verified source defect requiring one.

## 12. Blockers and corrective actions

1. Provision an approved, offline-capable build environment with Hatchling and
   a build frontend; build fresh wheel and sdist into a temporary directory.
2. Inspect artifact metadata and contents, compare modules and version to the
   checkout, then build a wheel from the fresh sdist.
3. Install those artifacts into disposable isolated environments with resolved
   dependencies; distinguish wheel and sdist installation evidence.
4. Provision the locked dependency set for Python 3.13/3.14 and run each
   interpreter independently.
5. Execute the documented worker lifecycle and full regression checklist on
   Windows; do not treat macOS results as Windows proof.
6. Restore hosted CI billing and collect the full matrix results and CI
   artifacts. Do not trigger it until authorized/available.
7. Reconcile or remove stale ignored `dist/` files only under a separate
   explicit cleanup scope; RR-001 did not modify them.

## 13. Final readiness decisions

**Decision A — RR-001 Engineering Verification: PASS.** Every check runnable
with the authorized, pre-provisioned environment passed; build, clean install,
additional interpreter, Windows, and hosted checks are explicitly marked
BLOCKED rather than represented as passed.

**Decision B — Public Release Readiness: NO-GO.** Current wheel/sdist are stale
relative to the checkout; no fresh package build or clean install is verified;
Python 3.13/3.14, Windows, hosted CI, and maintainer release approval remain
outstanding. Do not publish or describe `v0.4.0` as released.

## 14. Final repository status

RR-001 work is on `chore/yantra-rr001-release-readiness`, based on the clean
V05 closure commit. The package version remains `0.2.0`. Final commit and
worktree status are recorded in the task handoff; this evidence file makes no
claim that any blocked release check subsequently passed.
