# Developer-preview stability and support policy

YANTRA `0.2.0` is an unreleased, pre-1.0 developer-preview candidate. It is
not currently a PyPI release. A future `v0.3.0` preview is proposed, not
approved or created by this milestone.

## Compatibility expectations

- Python support begins at 3.12; the release-candidate workflow exercises
  Python 3.12, 3.13, and 3.14 on macOS, Ubuntu, and Windows.
- Public Python APIs, CLI syntax, and provider behavior may change before
  `1.0.0`. Breaking changes should still be documented in release notes and
  migration guidance when a release is prepared.
- The `yantra` CLI is the developer entry point. `yantra-smoke` remains
  available for gateway-level checks and is retained for compatibility during
  this preview.
- Offline CLI behavior is deterministic. Live provider catalog and inference
  behavior remains dependent on the provider, model, account, and service
  version; mocks do not establish upstream compatibility.
- No warranty of production readiness, service-level objective, or
  backward-compatibility guarantee is made by this preview.

## Security boundaries and limitations

YANTRA keeps the model gateway, bounded agent loop, tool authorization,
trusted host-injected approvals, and worker subprocess as distinct layers.
The Python host and registered host code are trusted. A worker subprocess is
**not an OS sandbox** and does not guarantee filesystem/network isolation,
descendant cleanup, or CPU/memory/disk quotas. Approval replay protection is
process-local; exactly-once side effects and hard spending ceilings are not
provided. Applications must independently review tools and policy before
connecting real data or side-effecting systems.

Live provider compatibility is not comprehensively verified. No credentials
or billable inference are required for the first-run quickstart. Catalog
requests are live network operations when explicitly selected.

## Distribution policy

Preparing or downloading a GitHub Actions artifact is not a publication.
Release-candidate CI does not create tags, GitHub Releases, or PyPI uploads.
Each release requires a separate maintainer decision, approved version, exact
commit CI evidence, artifact review, and explicit authorization to tag and
publish. See [release engineering](releasing.md).
