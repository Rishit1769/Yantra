# Cancellation

Cancellation propagates from caller to runtime loop, provider request, tool task, workflow descendants, and (for subprocess-bound tools) the direct worker process. The subprocess boundary closes stdin, terminates the child, waits for a short grace period, kills if needed, and reaps it. Worker startup racing with cancellation is also cleaned up. Cancellation is not rollback; descendants are not tracked, external effects may already have occurred, and remote completion may remain ambiguous. Synchronous in-process handlers delegated to a thread cannot be forcibly stopped.

Runtime performs bounded cleanup under a shielded cleanup deadline, records cancellation requested/acknowledged and unfinished children, and reaches CANCELLED only when its local state policy is satisfied. Shutdown drains or cancels according to configuration. Tests cover cancellation at every await boundary, during retries, and during persistence commit.
