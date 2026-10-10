# Orchestration Engine

Orchestration supports deterministic workflow nodes and bounded agent tasks. A scheduler tracks dependencies and resource allocations; a parent may delegate only within configured depth, concurrency, task, token, and deadline budgets. Communication is structured task input/output or explicit messages, not unrestricted shared mutable state.

```mermaid
flowchart TD
  Parent[Parent task] --> Scheduler[Dependency scheduler]
  Scheduler --> A[Child task A]
  Scheduler --> B[Child task B]
  A --> Result[Validated result aggregation]
  B --> Result
  Result --> Parent
  A -. failure policy .-> Scheduler
  B -. cancellation propagation .-> Scheduler
```

Cycles are rejected in static workflow graphs. Dynamic delegation uses a depth limit and task budget. Tasks acquire resources in a stable order or use leases with deadlines; no worker waits indefinitely while holding a scarce resource. Failure policy is explicit (fail-fast, collect, compensate, or human intervention). See [multi-agent](../features/multi-agent.md) and [workflow schema](../specifications/workflow-schema.md).
