# Database Overview

PostgreSQL is the proposed primary production database. Prisma ORM and Prisma Migrate are operated by a TypeScript persistence service. Python communicates through a versioned RPC port and never imports Prisma. In-memory persistence supports lightweight, non-durable local execution. pgvector and Redis are optional; the framework must remain useful without either.

Database records cover identity/configuration, sessions/runs/tasks, events/checkpoints, model/tool attempts, approvals, workflows, skill packages, memory, artifacts, and audit. Tenant-scoped rows include tenant ownership and every API access path applies it. Raw credentials are never stored. See [entity model](entity-model.md), [relationship diagram](relationships.md), and [migrations](migrations.md).
