# ADR 0001: Python-First Runtime

- Status: Proposed
- Context: Target users and agent ecosystem need an async Python SDK; persistence technology has a separate TypeScript constraint.
- Decision: Implement the agent runtime in Python 3.12+ using asyncio/AnyIO, Pydantic v2, HTTPX, typing and Protocol interfaces.
- Alternatives: TypeScript runtime; polyglot runtime; Rust core.
- Consequences: Python ergonomics and provider ecosystem; Python packaging/async semantics must be managed; TypeScript persistence remains a service boundary.
- Tradeoffs: Some cross-language API cost is accepted for clear ownership; no Prisma import in Python.
