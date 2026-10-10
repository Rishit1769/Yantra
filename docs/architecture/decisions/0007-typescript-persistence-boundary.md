# ADR 0007: TypeScript Persistence Service Boundary

- Status: Proposed
- Context: Python runtime and Prisma/TypeScript have different execution and type systems; duplicated DB access risks split ownership.
- Decision: TypeScript service exclusively owns Prisma/database; Python uses versioned language-neutral persistence API, initially authenticated HTTP/JSON.
- Communication options: HTTP/JSON offers low deployment complexity and clear operations with moderate latency; gRPC offers lower overhead/strong generated types at greater toolchain and proxy complexity; queues suit asynchronous writes but add delivery/backlog semantics; direct Python DB access has low call latency but violates ownership and expands credentials. Avoid RPC for transient loop state.
- Alternatives: Python directly accesses PostgreSQL; gRPC; queue-only writes; shared in-process binding.
- Consequences: Clear migration/query ownership and service isolation; RPC latency and outage semantics must be managed.
- Tradeoffs: HTTP/JSON is operationally simple but less strongly generated than gRPC; avoid calls for transient state.
