# Migrations

Prisma Migrate owns schema history. Migration files are reviewed source, tested against an empty database and a representative previous schema, and run once by a deployment job with migration-only credentials. Application replicas do not race to migrate at startup.

Use expand/contract for rolling compatibility: add nullable/new structures, deploy code that can read old and new, backfill in bounded observable batches, switch writes/reads, then remove old structures in a later release. Backfills are restartable and rate-limited. Destructive migration requires backup/restore validation and explicit approval. Rollback is not assumed possible after data transformation; define forward fix and recovery plan. Migration lock, service/API compatibility, and database version support are release gates.
