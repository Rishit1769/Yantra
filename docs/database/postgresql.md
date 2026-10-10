# PostgreSQL

Use supported PostgreSQL versions declared by each release (not yet selected). Enforce referential integrity, uniqueness, check constraints, tenant scoping, and bounded indexes at the database layer where appropriate. JSONB is reserved for versioned flexible payloads such as event data/config extensions; stable query keys remain typed relational columns. Large artifacts and raw traces should use a separate retention-controlled store rather than unbounded rows.

Connection pooling belongs at service deployment boundary; Prisma pool sizing must account for replicas and PostgreSQL connection limits. TLS, restricted service role, encrypted backups, rotation, monitoring, and migration rehearsals are required. Local mode need not run PostgreSQL. No database schema exists today.
