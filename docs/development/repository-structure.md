# Repository Structure

Current structure separates the implemented Python contract foundation from future services:

```text
src/yantra/                # installable package; runtime, adapters, yantra and yantra-smoke CLIs
tests/unit/                # deterministic unit and contract tests
.github/workflows/         # cross-platform CI and release-candidate validation
scripts/                   # portable distribution artifact verification
docs/                      # architecture, contracts, operations
services/persistence/      # future TypeScript API, Prisma schema/migrations
```

The future persistence service does not exist yet. NIRMAAN remains a separate repository/consumer.
