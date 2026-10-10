# Checkpointing

Checkpoint only after a safe state boundary with no unclassified in-flight operation, or include explicit in-flight status for reconciliation. Serialize a versioned allowlist of logical state, never Python object graphs/pickle. Store schema/runtime version, digest, sequence, and references. Protect sensitive state and apply retention.

Resume verifies integrity and compatibility, fences stale workers, reconciles external attempts, and resumes a linked attempt. Incompatible state requires migration or operator action. See [checkpoint feature](../features/checkpoints.md).
