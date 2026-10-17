# YANTRA Release Readiness Evidence (RR-002)

**RR-002 engineering verification: PASS. Public release readiness: NO-GO.**
This evidence records the accepted source at `d6eec8a` and does not authorize a
release. Package version remains `0.2.0`; no runtime or packaging configuration
was changed.

## 1. Repository baseline and scope

| Item | Evidence |
|---|---|
| Starting branch / commit | `chore/yantra-rr001-release-readiness` / `d6eec8ad81f207b7ffc728363d167b4992052faf` |
| Starting worktree | Clean |
| RR-002 branch | `chore/yantra-rr002-packaging-validation`, created at the verified starting commit |
| Package version | `0.2.0` (`src/yantra/_version.py`) |
| Host | macOS 26.5.1, arm64 |
| Interpreters | CPython 3.12.15, 3.13.15, and 3.14.7 |
| uv | 0.13.0 |

RR-002 was limited to building and inspecting distributions, isolated
installation, offline behavior, and locally available Python compatibility.
The stale, ignored artifacts in the checkout's `dist/` directory were not
used or modified. All new artifacts and environments were placed under a
disposable `/private/tmp/yantra-rr002.*` directory. No credential, keychain,
live provider, or network inference operation was performed.

## 2. Dependency and build provenance

Build environment: isolated CPython 3.12.15 virtual environment. It was
prepared with the project-constrained Hatchling range and the approved build
frontend. Installed build packages:

| Package | Version |
|---|---:|
| build | 1.6.1 |
| hatchling | 1.32.4 |
| packaging | 26.3 |
| pathspec | 1.1.1 |
| pluggy | 1.7.0 |
| pyproject-hooks | 1.3.3 |
| tomlkit | 0.15.2 |
| trove-classifiers | 2026.9.21.13 |

The build environment used this disposable setup/install pattern (with unique
temporary paths):

```sh
uv venv --python 3.12 /private/tmp/yantra-rr002-build
uv pip install --python /private/tmp/yantra-rr002-build/bin/python \
  'hatchling>=1.27,<2' build
```

Builds used the resolved, recorded tool environment without backend
re-resolution:

```sh
/private/tmp/yantra-rr002-build/bin/python -m build --no-isolation \
  --outdir /private/tmp/yantra-rr002-output-a
/private/tmp/yantra-rr002-build/bin/python -m build --no-isolation \
  --outdir /private/tmp/yantra-rr002-output-b
/private/tmp/yantra-rr002-build/bin/python -m build --no-isolation --wheel \
  --outdir /private/tmp/yantra-rr002-from-sdist \
  /private/tmp/yantra-rr002-output-a/yantra-0.2.0.tar.gz
```

The environment versions above were installed from the normal Python package
index into that disposable virtual environment. No project dependency or
lockfile was changed. Each of Python 3.12, 3.13, and 3.14 received its own
environment using `uv sync --locked --all-groups --python <version>`; each
resolved the existing lock (35 locked packages; 23 installed packages,
including YANTRA and the development group). The clean distribution
environments contained only YANTRA and its declared runtime dependency closure
(12 packages); they did not inherit the development tools.

## 3. Fresh artifacts and package inclusion

Both direct builds from the source checkout succeeded. The sdist independently
produced a wheel using the isolated, pinned build environment. The wheel has
the universal pure-Python tag `py3-none-any`.

| Artifact | Type / tag | Size | SHA-256 |
|---|---|---:|---|
| `yantra-0.2.0-py3-none-any.whl` | Wheel, `py3-none-any` | 124,251 bytes | `d805724b73c4cc283b68b16959e21ae1251cd37e6444f4adbc2387190e53c440` |
| `yantra-0.2.0.tar.gz` | Source distribution | 244,166 bytes | `6841ae280bc620ebc7a52db9f14e538613d8ebee2094d64638e1acb359423306` |

Build timestamp: 2026-10-17 00:05:20 +05:30. Source commit: `d6eec8a`.
The direct artifacts were written to a new temporary output directory, not
`dist/`.

Artifact inspection established:

- Wheel `METADATA` reports name `yantra`, version `0.2.0`,
  `Requires-Python: >=3.12`, Apache-2.0 license expression and license file,
  Markdown README metadata, and the declared `httpcore`, `httpx`, `pydantic`,
  and optional `keyring` requirements.
- `WHEEL` reports `Root-Is-Purelib: true` and `Tag: py3-none-any`.
  `entry_points.txt` contains `yantra-smoke = yantra.devtools.smoke:main`.
- All 59 Python source modules in the current package are present in the wheel
  and byte-identical to the checkout. The wheel contains 65 entries including
  metadata, license, and `py.typed`; all recorded `RECORD` SHA-256 values
  validated.
- The 248-entry sdist contains all 59 current Python modules and the declared
  build inputs. The generated wheel from that sdist is byte-identical to the
  direct wheel.
- Archive path/content inspection found no `.env`, `.git` internals,
  `__pycache__`, private credential files, or log files. The secure-tool
  modules, including worker protocol/entry point, approvals, policy,
  execution, and subprocess boundary, are included.

### Reproducibility findings

Two direct builds from the same checkout with the same builder environment
had identical SHA-256 results for both wheel and sdist. The wheel rebuilt from
the sdist also had the direct wheel's SHA-256. This is observed **bit-for-bit
reproducibility** for these repeated builds in this environment. It does not
establish reproducibility across different operating systems, tool versions,
or source commits.

## 4. Clean distribution installations

Each install used a newly created disposable environment and was run from
`/private/tmp`, outside the repository, with `PYTHONPATH` unset. The resolved
`yantra.__file__` was inside that environment's `site-packages`; version and
public exports (`ModelGateway`, `MockProvider`, `AgentExecutionEngine`, and
core message/tool types) were verified. No editable install was used.

| Distribution | Python | Result |
|---|---:|---|
| Fresh wheel | 3.12.15 | PASS |
| Fresh wheel | 3.13.15 | PASS |
| Fresh wheel | 3.14.7 | PASS |
| Fresh sdist | 3.12.15 | PASS; build isolation enabled by the installer |

The installed CLI's `--help` and `offline` commands passed in all four
environments. The installed package also completed the deterministic secure
tool boundary and approval examples: mock-backed agent loop, in-process tool,
fixed-handler subprocess, scoped denial, timeout cleanup, approval, rejection,
and approval replay rejection. These are offline demonstrations, not an OS
sandbox or Windows process-lifecycle guarantee. Clean install dependency
resolution followed the declared version ranges (for example, it resolved
Pydantic 2.14.1); the three full test environments instead used the exact
versions in `uv.lock` (Pydantic 2.14.0).

## 5. Python compatibility and security regressions

Each interpreter had a separate `uv sync --locked --all-groups` environment.
No site-packages were shared. All test runs were offline and used the required
no-cache pytest invocation.

| Python | Locked dependencies | Full tests | Four examples | Worker lifecycle | Decision |
|---|---|---:|---|---|---|
| 3.12.15 | PASS | 229 passed, 0 failed, 0 skipped | 4/4 pass | Full suite and subprocess success/denial/timeout example pass | PASS |
| 3.13.15 | PASS | 229 passed, 0 failed, 0 skipped | 4/4 pass | Full suite and subprocess success/denial/timeout example pass | PASS |
| 3.14.7 | PASS | 229 passed, 0 failed, 0 skipped | 4/4 pass | Full suite and subprocess success/denial/timeout example pass | PASS |

Executed for each version:

```text
python -m pytest -q -p no:cacheprovider                 229 passed
python examples/agent_loop_offline.py                    PASS
python examples/secure_tool_policy.py                   PASS
python examples/secure_tool_approval.py                  PASS
python examples/secure_tool_boundaries.py                PASS
python -m pytest -q -p no:cacheprovider \
  tests/unit/test_tool_policy.py \
  tests/unit/test_execution_boundary.py                 45 passed
```

The existing regression coverage includes name allowlisting, scope grants and
denial, approval binding/expiry/replay/cancellation, HMAC authorization,
single-use dispatch, standalone executor fail-closed behavior, registry
mutation protection, worker protocol and bounds, timeout cleanup, concurrency
limits, and capacity recovery. No security behavior or tests were weakened.
No test warnings or skips were reported.

## 6. Quality checks and CLI

| Check | Result |
|---|---|
| `uv lock --check` | PASS; 35 packages resolved, lock unchanged |
| `ruff check .` | PASS |
| `ruff format --check .` | PASS; 85 files formatted |
| `pyright --pythonpath <Python 3.12 env> src examples` | PASS; 0 errors, warnings, or information diagnostics |
| `pytest -q -p no:cacheprovider` | PASS on all three interpreters, 229 each |
| Four deterministic examples | PASS on all three interpreters |
| Installed CLI help and offline mock | PASS on all three wheel installs and the sdist install |
| `git diff --check` | PASS before commit |

An initial direct Pyright invocation did not point Pyright at the disposable
interpreter, so it could not locate that environment's Pydantic stubs. Rerunning
with the explicit `--pythonpath` above passed with zero diagnostics; no source
change was needed. No repository Markdown-link checker is configured, so the
new evidence links and edited README/index/roadmap targets were checked
directly.

## 7. Windows, hosted CI, and security status

- **Windows runtime: BLOCKED / not tested.** No Windows host was available.
  macOS results are not represented as Windows evidence.
- **Hosted GitHub Actions: BLOCKED / not triggered.** The known billing issue
  remains; RR-002 did not push or otherwise trigger workflows.
- **Security regression: PASS locally** across all three available Python
  versions as listed above. This is regression verification, not an independent
  security audit. The subprocess boundary remains a fixed-handler process
  boundary, not an OS sandbox; descendant-process guarantees and OS resource
  quotas are not claimed.
- No critical or high-severity packaging/security defect was found in this
  scope. No code/configuration fix was required.

## 8. Decisions and remaining work

**Decision A — RR-002 Engineering Verification: PASS.** Fresh wheel and sdist
builds, artifact inspection, sdist-to-wheel build, clean installation,
installed-package offline behavior, Python 3.12/3.13/3.14 full test suites,
security regressions, CLI, and quality checks passed. Windows and hosted
validation are outside the available local evidence and remain explicitly
blocked.

**Decision B — Public Release Readiness: NO-GO.** A release still requires
Windows runtime verification, the required hosted CI matrix, and explicit
maintainer approval. No tag, publication, merge, push, or deployment was made.
Do not describe `0.2.0` or `v0.4.0` as released.

Recommended RR-003 scope: provision a real Windows runner and restore hosted CI
availability; run the documented cross-platform matrix and resolve any actual
platform-specific findings. After those checks, request a separate maintainer
release decision. Preserve the package version and do not publish until that
approval is explicit.

The working branch is `chore/yantra-rr002-packaging-validation`, based on
`d6eec8a`. The final commit hash and worktree status are recorded in the task
handoff after the evidence and documentation changes are committed.
