# YANTRA-005 Developer Preview Distribution and Release Engineering

## Decision

**Local engineering verification: PASS. Hosted verification: NOT VERIFIED. Release: NO-GO / not authorized.** YANTRA-005 adds a standard-library CLI entry point, deterministic offline agent demonstration, safe local diagnostics, end-user installation and stability documentation, portable distribution checks, and a manually dispatched / PR-triggered release-candidate workflow. The package version remains `0.2.0`. This report does not authorize a tag, GitHub Release, package-index publication, or merge.

## Scope delivered

- Added `yantra --version`, `doctor`, `providers`, `models`, and `quickstart` while preserving the existing `yantra-smoke` entry point. Model listing is offline by default; network lookup requires `yantra models PROVIDER --live`. Doctor checks local runtime/dependency state and reports only whether credential variables exist, never their values. Optional Ollama checking is explicit and restricted to a loopback endpoint.
- Reused the existing runtime, provider registry, model catalog, tool registry, and offline example fixture. The quickstart prints the model tool proposal, tool result, and final answer without network access, credentials, external services, or extra dependencies.
- Added macOS and Windows pip/uv install instructions, CLI reference, troubleshooting, provider/environment notes, and explicit alpha/stability/security limitations. PyPI availability is not claimed.
- Added a portable wheel/sdist verifier for archive path safety, expected metadata/entry points/source files, prohibited secret/cache files, and SHA-256 manifest generation or checking.
- Added a read-only GitHub Actions release-candidate workflow with nine Ubuntu/macOS/Windows × Python 3.12/3.13/3.14 validation jobs. After that matrix passes, it runs static checks and the dependency audit, builds and clean-installs wheel and sdist, verifies checksums, and uploads a 14-day Actions artifact. It does not publish a package or create a GitHub Release/tag.

## Local verification evidence

Environment: macOS, Python 3.12.15. These results describe local verification only; they do not establish behavior on Windows or other Python versions.

- `uv run --locked python -m pytest -q`: **247 passed**.
- `uv run --locked ruff check .`: passed.
- `uv run --locked ruff format --check .`: passed (91 files already formatted).
- `uv run --locked pyright`: passed with zero errors, warnings, or information diagnostics.
- `uv lock --check`: passed (35 packages resolved).
- `uv audit --locked`: passed after retry with network access; no known vulnerabilities or adverse project statuses found in 34 packages. This does not replace future audits.
- All four offline demonstrations ran successfully.
- The release-artifact and CLI focused regression tests passed (14 tests) after the final verifier hardening.
- Wheel and sdist were installed into separate clean virtual environments outside the checkout. Installed `yantra` and legacy `yantra-smoke` commands, doctor/provider/model listing, and the offline quickstart worked without importing from the repository checkout.
- Two equivalent local builds after implementation and formatting were finalized produced matching SHA-256 values: wheel `42600706eb57d40acbf95c93d7cad82fe7d4dbcaaf5a0856c1c28df81f253527`; sdist `b5f3590e4ce12510ef46e41a289637755b92994c5f866a05d975f14a277b108a`. These hashes document the repeated-build check before recording the hash evidence in this report; the final commit's hosted workflow independently rebuilds and verifies its own artifact.

## Security, compatibility, and limitations

Diagnostics are read-only. No credential values are emitted; no inference request is made by doctor, providers, or default model listing. `--live` is an explicit user choice. The demo uses fixed local components and synthetic responses. The subprocess tool runtime elsewhere in YANTRA remains restricted execution, not an OS sandbox. Local macOS testing is not evidence of Windows compatibility.

The release-candidate workflow is configured but has not yet run for this change. Until the latest commit's complete nine-job matrix and packaging job pass on GitHub Actions, hosted CI, Windows/macOS verification, and release readiness are **NOT VERIFIED**. Historical RR-003 CI evidence applies only to its recorded commit and does not cover YANTRA-005. Dependency audit is locally verified as above; the hosted audit remains pending with the workflow.

No repository source version was bumped. No package was published, no GitHub Release or tag was created, and no branch was merged as part of this report. The pre-existing RR-003 documentation working-tree edit was preserved and is not part of YANTRA-005.

## Release gate

1. Run the new workflow on the final YANTRA-005 commit and verify all nine OS/Python jobs plus its build/install/audit job.
2. Inspect the uploaded artifact and independently verify its checksums and clean installs.
3. Review any platform-specific failures and remediate before declaring cross-platform verification.
4. Make a separate maintainer decision for any version change, tag, release, or publication.
