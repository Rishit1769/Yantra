# Releasing YANTRA

This process governs Python package releases. A release is a separately approved operation; passing CI or preparing distributions does not authorize tagging, publishing, or deployment.

## Versioning

YANTRA uses Semantic Versioning conventions for pre-1.0 releases, with the explicit understanding that `0.y.z` APIs are not stable: changes within `0.y` may still require compatibility adjustments. After `1.0.0`, major versions indicate incompatible public API changes, minor versions add backward-compatible features, and patch versions contain backward-compatible fixes.

The package version has one source: `src/yantra/_version.py`. Hatchling reads that value for wheel and sdist metadata. `uv.lock` locks dependencies; it is not an independent version authority.

Identifiers are distinct:

- `YANTRA-002` is the model-gateway engineering milestone.
- `YANTRA-002-R03` identifies this release-preparation task.
- `0.2.0` is the Python package release-candidate version.
- `v0.2.0` is the intended Git tag for that package version.

No tag is created by routine development or CI.

## Prerequisites

Before requesting release approval:

- Work from a clean working tree; review all staged and untracked files.
- Confirm Apache License 2.0 metadata and root `LICENSE` are present.
- Confirm `src/yantra/_version.py`, wheel metadata, sdist metadata, installed metadata, and provider User-Agent agree.
- Require passing CI for every configured OS/Python matrix combination. A workflow definition is not execution evidence.
- Run the locked test, Ruff, Pyright, build, and dependency-vulnerability checks.
- Build and install both wheel and sdist in isolated environments outside the checkout; run only offline CLI tests during release validation.
- Review the provider evidence matrix, security review, known limitations, release audit, changelog, and release notes.
- Resolve all critical/high security findings and release blockers. Any accepted residual risk must have a written owner decision before approval.
- Obtain explicit maintainer/release-owner approval. This repository has no formal governance model; authority must be established by the project maintainers rather than inferred by this document.

## Release Checklist

1. Verify branch, commit, tags, clean status, and intended tracked files.
2. Confirm the single source version is the requested release version.
3. Confirm Apache 2.0 SPDX metadata and complete license inclusion in both distributions.
4. Run `uv sync --locked --all-groups` and `uv lock --check`.
5. Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, and `uv run pytest -v`.
6. Run `uv audit --locked` and review all findings and the scan's data-source limitations.
7. Build with `uv build`; inspect metadata, contents, entry points, private-file exclusions, and archive hashes.
8. Install wheel and sdist independently in clean environments outside the repository; verify version, imports, license metadata, and offline CLI behavior.
9. Review the changelog, release notes, provider matrix, API docs, security findings, and known limitations.
10. Verify actual green GitHub Actions results for the exact candidate commit on Ubuntu, macOS, and Windows with Python 3.12, 3.13, and 3.14.
11. Obtain release-audit approval and explicit authorization to tag.
12. Only after authorization, create the intended tag `v0.2.0` pointing to the approved candidate commit. This task does not create it.
13. Verify tag target and build artifacts from the tagged source. Sign the tag only if an approved signing key and project signing policy exist.
14. Obtain separate authorization to publish. Do not publish as a side effect of a push, pull request, or tag.
15. After an authorized publication, install the published wheel and sdist in fresh environments, verify metadata and checksums, and record the results.

## PyPI Publishing

When publication is separately approved, prefer PyPI Trusted Publishing through GitHub Actions OIDC. Register the exact repository, publishing workflow, and protected GitHub environment with PyPI; require a human approval gate on that environment. A dedicated publishing workflow should have `id-token: write` only on its publishing job, build or verify artifacts from the approved tag, and upload only those artifacts after approval.

Do not use a long-lived PyPI API token when Trusted Publishing is available. Do not add publishing credentials to ordinary CI, pull-request workflows, local configuration, or this repository. This repository currently has no publishing workflow or publishing credentials configured.

## Current Candidate

The prepared package version is `0.2.0`, with intended tag `v0.2.0`. YANTRA-002-R03 is release preparation only. Until all prerequisites and every CI matrix result are verified and an authorized maintainer approves the release, the candidate must not be tagged or published.
