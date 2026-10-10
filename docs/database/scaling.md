# Database Scaling

Scale first by query/index and payload-retention discipline, bounded connection pools, and service replicas. Partition high-volume event/telemetry tables only after measured evidence and compatibility testing. Read replicas can serve authorized read-heavy inspector queries with documented staleness; writes and concurrency checks use primary. Redis is optional and justified only for concrete coordination, lease, or cache needs; it is not source of truth.

Horizontal Python workers require leases/fencing tokens, idempotent persistence operations, bounded queues, and cancellation/recovery semantics. PostgreSQL connection budgets account for all replicas and migration jobs. pgvector indexes have independent capacity/maintenance needs. No scaling numbers are claimed.
