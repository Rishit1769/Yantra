# Cancellation

Cancellation propagates from caller to runtime loop, provider request, tool task, workflow descendants, and worker process. Each adapter declares whether cancellation is cooperative and whether an external operation can be confirmed stopped. Cancellation is not rollback; results remain ambiguous when remote completion cannot be determined.

Runtime performs bounded cleanup under a shielded cleanup deadline, records cancellation requested/acknowledged and unfinished children, and reaches CANCELLED only when its local state policy is satisfied. Shutdown drains or cancels according to configuration. Tests cover cancellation at every await boundary, during retries, and during persistence commit.
