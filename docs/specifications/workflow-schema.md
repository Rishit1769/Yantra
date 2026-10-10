# Workflow Schema

Workflows are versioned directed acyclic graphs of typed nodes: deterministic tool/task, agent task, branch, join, approval, wait, and compensation. Each node defines input/output schema, dependencies, finite retry/deadline/resource policy, and failure behavior. Static validation rejects cycles, missing edges, incompatible schemas, unbounded retries, and budget totals exceeding workflow ceiling.

Model-driven nodes are opaque bounded runs with explicit outputs; they do not alter graph topology unless a validated branch condition chooses among declared edges. Runtime persists workflow-definition version and node execution history. A new definition version does not rewrite active execution semantics; resume uses pinned definition or an explicit migration procedure.
