# Development Setup

YANTRA requires Python 3.12+ and uv. HTTPX is included for model gateway adapters, but the core contracts and mock quickstart make no network calls. PostgreSQL and Prisma are not runtime dependencies; OS keyring support is optional.

## macOS

Install Python 3.12 and uv using the official installers for your environment. From the repository root:

```sh
uv sync --all-groups
uv run python -c "import yantra; print(yantra.__version__)"
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
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv build --wheel
uv run yantra-smoke offline
```

`uv.lock` pins the development environment. CI is configured for macOS and Windows; until GitHub Actions succeeds on both, those platforms remain unverified. No PostgreSQL service is needed for the current tests.
