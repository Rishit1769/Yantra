# Crash Recovery

Recovery scans durable nonterminal runs with expired leases, verifies version/sequence, acquires a new fencing token, and classifies work since checkpoint. Confirmed completed operations are not repeated; pending operations are checked by idempotency/reconciliation contract; unknown irreversible outcomes pause or require human action. Recovery creates linked history rather than rewriting terminal records.

Recovery must handle crashes before/after DB commit, provider acceptance, tool effect, event append, and acknowledgement. A database restore may diverge from external effects and requires reconciliation. See [recovery feature](../features/recovery.md).
