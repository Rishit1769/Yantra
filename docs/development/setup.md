# Development Setup

YANTRA-001 requires Python 3.12+ and uv. The core has no network, PostgreSQL, Prisma, or platform-specific runtime dependency.

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
```

`uv.lock` pins the development environment. CI runs this suite on macOS and Windows; until a GitHub Actions run succeeds on both, those platforms are configured but not verified. Do not connect to PostgreSQL for YANTRA-001.
