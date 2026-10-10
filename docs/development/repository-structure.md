# Repository Structure

Current structure separates the implemented Python contract foundation from future services:

```text
src/yantra/                # installable package; contracts, adapters, gateway, smoke CLI
tests/unit/                # deterministic unit and contract tests
.github/workflows/ci.yml   # macOS/Windows CI configuration
docs/                      # architecture, contracts, operations
services/persistence/      # future TypeScript API, Prisma schema/migrations
```

The future persistence service does not exist yet. NIRMAAN remains a separate repository/consumer.
