# ADR 0016: Initial Persistence RPC Transport

- Status: Proposed
- Context: Python runtime requires a language-neutral, versioned API to a TypeScript Prisma service. Durable calls are not on every transient loop operation.
- Decision: Begin with authenticated HTTP/JSON over TLS, versioned routes, explicit request deadlines and idempotency semantics, and generated/validated schemas. Avoid calls for transient state. Reconsider gRPC if measured latency/streaming needs justify added complexity.
- Alternatives: gRPC; message queue; Python direct database access; shared process binding.
- Consequences: Easy inspection, proxies, and operational onboarding; moderate request overhead and weaker compile-time guarantees than protobuf require conformance tests.
- Tradeoffs: HTTP service semantics still have ambiguous timeout-after-commit cases; idempotency lookup and compare-and-set are required. No distributed transactions are implied.
