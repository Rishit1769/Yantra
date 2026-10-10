# Distributed Workers

Distributed execution is future work. It requires authenticated worker identity, bounded durable queue, expiring leases, fencing tokens, tenant fairness, task payload minimization, idempotent state updates, cancellation propagation, and crash reconciliation. Redis is optional and only justified if measurements favor it for coordination/cache; PostgreSQL remains durable source of truth.

At-least-once delivery is expected. Worker acknowledgements and tool side effects can be ambiguous. Never interpret queue deduplication as exactly-once execution. Test duplicate delivery, stale worker fencing, service outage, poison tasks, and rolling upgrades before release.
