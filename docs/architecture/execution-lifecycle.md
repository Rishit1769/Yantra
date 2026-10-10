# Execution Lifecycle

1. Validate caller identity, agent-definition version, configuration, request schema, and finite budgets.
2. Allocate session/run/task IDs and emit creation event; persist according to selected adapter.
3. Queue and acquire an execution lease if distributed mode is enabled.
4. Assemble context with source provenance, trust labels, and token budget.
5. Call provider adapter under deadline; normalize response and usage.
6. Validate response. Final output completes; tool proposals pass schema validation and independent policy, with approval suspension when required.
7. Execute authorized calls under limits; record outcomes/events and feed bounded observations into context.
8. Terminate on completion, cancellation, failure, approval, suspension, or exhausted budget.
9. On recovery, reconcile persisted version/lease and ambiguous external effects before any retry.

```mermaid
sequenceDiagram
  participant C as Caller
  participant R as Runtime
  participant G as Model gateway
  participant P as Policy
  participant T as Tool executor
  C->>R: start(agent, session, finite budgets)
  R->>R: validate and allocate run/task IDs
  loop while budget remains
    R->>G: request(provenance-bearing context)
    G-->>R: response or untrusted tool proposal
    alt final response
      R-->>C: COMPLETED result and event cursor
    else tool proposal
      R->>P: authorize exact tool/version/arguments
      alt denied
        P-->>R: denial observation
      else requires approval
        P-->>R: suspend in WAITING_FOR_APPROVAL
      else allowed
        R->>T: execute under bounded policy
        T-->>R: validated outcome or ambiguous effect
      end
    end
  end
```

See [runtime kernel](runtime-kernel.md), [state machine](state-machine.md), [cancellation](../reliability/cancellation.md), and [crash recovery](../reliability/crash-recovery.md).
