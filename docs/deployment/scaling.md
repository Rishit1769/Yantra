# Scaling

Scale based on measured workload and bottleneck: provider concurrency/rate limits, Python event-loop and worker capacity, persistence service replicas, PostgreSQL pool/query/index load, artifact bandwidth, and optional browser/sandbox capacity. Bound every queue and reject/backpressure rather than accumulating unbounded work. Keep transaction duration short and align connection pool totals to database limits.

Read replicas and event partitioning are future options with staleness/uniqueness constraints. Redis is not mandatory. Publish no throughput claims without reproducible workload, environment, and error/latency distributions.
