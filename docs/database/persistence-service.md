# Persistence Service

The TypeScript service is the sole database owner: Prisma Client, schema, migrations, tenant enforcement, transaction boundaries, query optimization, retention/deletion, and service authentication. Python owns runtime logic and uses a generated/validated client for the language-neutral contract only.

## Transport comparison

| Option | Latency | Deployment complexity | Security | Failure modes | Type safety |
|---|---|---|---|---|---|
| HTTP/JSON | Moderate; acceptable for durable boundary calls; avoid per-token/per-loop chatter | Low; easy proxying, health checks, language-neutral | Mature TLS, auth middleware, rate limits; payload validation required | Timeouts, duplicate requests, partial/ambiguous commit; explicit idempotency and deadlines | OpenAPI/schema-generated clients, weaker compile-time guarantees across versions |
| gRPC | Low overhead, streaming, multiplexed | Medium; protobuf generation, HTTP/2/proxies and operational tooling | Strong mTLS/interceptors; policy still application-owned | Similar timeout/ambiguous commit concerns; streaming reconnection complexity | Strong generated contracts across languages |
| Message queue | Asynchronous, usually higher end-to-end latency | High; broker, consumers, delivery/ordering operations | Broker identity/ACL and payload protection | At-least-once, backlog, poison messages, eventual consistency | Schema registry/codegen can help, but asynchronous contract complexity |
| Python direct DB access | Low call overhead | Low initial, high cross-language coupling and duplicated ownership | Broadens DB credentials and query surface in runtime | Pool/query failures in every worker; split migration/query semantics | No Prisma type reuse; duplicate models |

Recommendation: authenticated HTTP/JSON over TLS for initial durable API. Publish schema and generated clients; include request deadline, idempotency key for mutation, tenant identity from service auth, and correlation ID. Choose gRPC only if measured throughput/streaming requirements justify it. Do not issue HTTP calls for transient runtime state.

## Failure and consistency

The service uses a local database transaction for atomic state/event updates and expected-version compare-and-set. Python/provider/tool calls are outside that transaction; no distributed transaction exists. On timeout after mutation, caller outcome is unknown until idempotency-key lookup/reconciliation. Durable mode surfaces unavailable/conflict and must not report success without confirmed persistence. Optional in-memory execution can continue only when caller explicitly accepts non-durability. Buffering requires bounded storage and an explicit loss/replay contract; it is not a default.

Service authentication uses workload identity or mTLS plus scoped authorization; caller-supplied tenant IDs are cross-checked. Admin, migration, runtime, and read-only inspector roles are separated. Health endpoints reveal no secrets. See [persistence contract](../specifications/persistence-contract.md).
