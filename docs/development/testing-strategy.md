# Testing Strategy

Future layers: pure unit tests; property/state-machine tests with Hypothesis; async cancellation/concurrency tests; provider/tool/persistence contract tests; PostgreSQL/Prisma integration and migration tests; security tests (tenant, SSRF, secret canaries, malicious skills, policy bypass); failure injection/crash recovery; package/CLI compatibility; reproducible evaluation. Live provider tests are opt-in and cannot be the only CI coverage.

Fixtures must not include credentials or unlicensed data. Tests assert prohibited actions do not execute, not only that expected outputs occur. Coverage percentage alone is not an acceptance gate. No tests currently exist or have been run.
