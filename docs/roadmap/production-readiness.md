# Production Readiness

YANTRA is not currently implemented and is not production-ready. A future release can claim support only for explicitly tested deployment configurations and measured gates in [acceptance criteria](acceptance-criteria.md).

Required evidence includes correctness and concurrency suites; fault injection and crash recovery; security review and dependency scans; tenant isolation; migration/restore exercises; provider compatibility matrix; representative performance benchmarks; observability and redaction tests; stable/versioned APIs; reproducible artifacts; backup, incident, deployment, and operations validation; complete documentation. Every guarantee must cite evidence, scope, and known limitations.

Initially unsupported unless separately verified: active-active multi-region writes, arbitrary hostile code sharing a Docker host, exactly-once external effects, universal provider feature parity, unreviewed plugins/skills, and any deployment without tested secrets/network/tenant controls. Local in-memory mode is intentionally non-durable. No certifications, SLOs, benchmark values, or test coverage are claimed.
