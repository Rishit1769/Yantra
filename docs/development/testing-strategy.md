# Testing Strategy

YANTRA-001 implements deterministic unit/contract tests for package metadata, Pydantic validation/serialization, mock provider ordering/errors, tool registration/schema export, state transitions (including Hypothesis properties), storage isolation/sequence/concurrent append, and log redaction. Future layers include async cancellation/concurrency tests; provider/tool/persistence contracts; PostgreSQL/Prisma integration and migration tests; tenant/SSRF/secret/policy security tests; crash recovery; CLI compatibility; and reproducible evaluation. Live provider tests are opt-in and cannot be the only CI coverage.

Fixtures must not include credentials or unlicensed data. Tests assert prohibited actions do not execute, not only that expected outputs occur. Coverage percentage alone is not an acceptance gate. Tests in this milestone use no network or database.
