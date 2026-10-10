# Installation

YANTRA-001 adds a source-installable Python package; no release has been published to a package index. Use Python 3.12+ and uv from the repository root:

```sh
uv sync --all-groups
uv run python -c "import yantra; print(yantra.__version__)"
uv build --wheel
```

The project license remains unresolved, so do not redistribute the built wheel as an openly licensed release. A published release requires a license decision, supported artifact provenance, clean-environment installation tests, and a versioned compatibility policy.
