# Testing Strategy

YANTRA-001 implements deterministic unit/contract tests for package metadata, Pydantic validation/serialization, mock provider ordering/errors, tool registration/schema export, state transitions (including Hypothesis properties), storage isolation/sequence/concurrent append, and log redaction. YANTRA-002 adds mocked HTTP adapter, credential, catalog, routing, and streaming coverage; tests do not call live providers. Future layers include deeper cancellation/concurrency and protocol tests; PostgreSQL/Prisma integration and migration tests; tenant/SSRF/secret/policy security tests; crash recovery; CLI compatibility; and reproducible evaluation. Live provider tests are opt-in and cannot be the only CI coverage.

Fixtures must not include credentials or unlicensed data. Tests assert prohibited actions do not execute, not only that expected outputs occur. Coverage percentage alone is not an acceptance gate. Current tests use mocked network transports and no database.
