# Development Setup

YANTRA requires Python 3.12+ and uv. HTTPX is included for model gateway adapters, but the core contracts and mock quickstart make no network calls. PostgreSQL and Prisma are not runtime dependencies; OS keyring support is optional.

## macOS

Install Python 3.12 and uv using the official installers for your environment. From the repository root:

```sh
uv sync --all-groups
uv run python -c "import yantra; print(yantra.__version__)"
uv run yantra doctor
uv run yantra quickstart
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv build --wheel
uv run yantra-smoke offline
```

## Windows (PowerShell)

Install Python 3.12 and uv using the official Windows installers. From the repository root:

```powershell
uv sync --all-groups
uv run python -c "import yantra; print(yantra.__version__)"
uv run yantra doctor
uv run yantra quickstart
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv build --wheel
uv run yantra-smoke offline
```

`uv.lock` pins the development environment. The RR-003 GitHub Actions run
[39114896871](https://github.com/Rishit1769/Yantra/actions/runs/39114896871)
passed the configured Ubuntu/macOS/Windows × Python 3.12/3.13/3.14 matrix on
commit `2f07ec9`; the current RR-004 audit separately records its local
macOS/Python 3.12–3.14 results. These checks do not establish every platform
configuration or OS sandbox guarantees. No PostgreSQL service is needed for
the current tests.
