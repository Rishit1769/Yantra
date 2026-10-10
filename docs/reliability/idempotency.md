# Idempotency

An idempotency key identifies a logical operation at a cooperating service; it does not provide universal exactly-once semantics. Keys are scoped by tenant, operation, and retention window and stored without sensitive arguments (use a digest). The service must define whether repeated identical payloads return original result and how conflicting payloads are rejected.

For tools without idempotency support, record attempts, query external state when possible, and classify ambiguous outcomes; do not blindly retry irreversible actions. At-least-once delivery is expected in distributed workers. Exactly-once effects are not promised for arbitrary external tools.
