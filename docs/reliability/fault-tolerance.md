# Fault Tolerance

The runtime classifies failures by stage and effect certainty. Provider timeout can mean request accepted; tool timeout can mean side effect completed; persistence timeout can mean transaction committed. Store attempt intent/outcome when appropriate and represent unknown status explicitly. Retry only with bounded backoff, deadline, error classification, and idempotency/reconciliation semantics.

Circuit breakers may protect provider/service dependencies but must not conceal state. Persistence outage in durable mode prevents claiming durability; optional in-memory mode is explicitly non-durable. Worker loss uses leases/fencing and reconciliation. See [retries](retries.md), [idempotency](idempotency.md), and [crash recovery](crash-recovery.md).
