# Transactions

Transactions exist only inside the TypeScript persistence service/PostgreSQL. Use a short transaction for related row changes such as compare-and-set run state plus event append and sequence allocation, approval decision plus audit record, or checkpoint plus run pointer. Do not include provider, tool, browser, or human wait operations in database transactions.

Optimistic concurrency uses `state_version`/expected version and returns conflict on mismatch. Retry requires reload and semantic reconciliation. External tool attempts use a durable intent record before dispatch where risk warrants; completion is recorded separately. A crash between effect and completion record is ambiguous, not exactly-once. No distributed transaction across Python, service, provider, and tool is promised.
