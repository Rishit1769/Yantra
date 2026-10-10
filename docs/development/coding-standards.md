# Coding Standards

Implemented Python baseline: typed public API, `Protocol` adapters, asyncio, Pydantic v2 validation at boundaries, Ruff lint/format, Pyright strict checks for `src/yantra`, and no blocking IO in async interfaces. Keep core dependency-light; optional provider/browser/vector features in extras or services. Avoid hidden global registries and mutable cross-run state.

The future TypeScript persistence service should use generated Prisma types internally, explicit DTO/schema validation externally, repository boundaries, and parameterized raw SQL. No SQLAlchemy or Alembic. Do not introduce LangChain, CrewAI, AutoGen, or LangGraph into core orchestration. Security-sensitive behavior requires tests and concise rationale comments. CI is configured for macOS and Windows but not yet verified by a GitHub Actions run.
