# Repository Structure

Current repository: top-level README and documentation tree. There is no `src/`, package metadata, Prisma service, migrations, tests, or CI configuration. Proposed eventual separation:

```text
packages/yantra-python/    # SDK/runtime, dependency-light
services/persistence/      # TypeScript API, Prisma schema and migrations
docs/                      # architecture, contracts, operations
tests/                     # unit, contract, integration, security, eval
```

This layout is illustrative and not created as implementation. NIRMAAN remains a separate repository/consumer.
