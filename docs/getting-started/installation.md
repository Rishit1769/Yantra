# Installation

YANTRA `0.2.0` is an unreleased developer-preview candidate; no package-index release has been published. To try the current source, use Python 3.12+ and uv from the repository root:

```sh
uv sync --locked --all-groups
uv run python -c "import yantra; print(yantra.__version__)"
uv run python examples/agent_loop_offline.py
```

The offline agent example performs a complete mock model/tool/model cycle and
makes no network requests. For isolated wheel/sdist installation and external
consumer verification, see the current [RR-004 audit](../development/yantra-release-readiness-rr004.md).

The model gateway uses HTTPX, included in the base package. OS keyring support is optional; install it with `uv sync --extra credentials` when secure credential storage is needed. The mock quickstart makes no network requests; gateway adapters do when called.

YANTRA is licensed under the Apache License, Version 2.0; see the [LICENSE](../../LICENSE) file. A published release still requires supported artifact provenance, clean-environment installation tests, and a versioned compatibility policy.
