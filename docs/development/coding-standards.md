# Coding Standards

Proposed Python style: typed public API, `Protocol` adapters, asyncio/AnyIO structured cancellation, Pydantic v2 validation at boundaries, Ruff formatting/lint, Pyright strict checks for public/core code, and no blocking IO on event loop. Keep core dependency-light; optional provider/browser/vector features in extras or services. Avoid hidden global registries and mutable cross-run state.

TypeScript persistence service uses generated Prisma types internally, explicit DTO/schema validation externally, repository boundaries, and parameterized raw SQL. No SQLAlchemy or Alembic. Do not introduce LangChain, CrewAI, AutoGen, or LangGraph into core orchestration. Security-sensitive behavior requires tests and concise rationale comments. These standards remain proposed until tooling is configured.
