# Runtime State Machine

States: `CREATED`, `QUEUED`, `RUNNING`, `WAITING_FOR_MODEL`, `WAITING_FOR_TOOL`, `WAITING_FOR_APPROVAL`, `SUSPENDED`, `COMPLETED`, `FAILED`, `CANCELLED`.

| From | Valid next states | Conditions |
|---|---|---|
| CREATED | QUEUED, CANCELLED, FAILED | Validated request or preflight failure |
| QUEUED | RUNNING, CANCELLED, FAILED | Scheduler lease acquired or cancellation |
| RUNNING | WAITING_FOR_MODEL, WAITING_FOR_TOOL, WAITING_FOR_APPROVAL, SUSPENDED, COMPLETED, FAILED, CANCELLED | A bounded operation/terminal decision |
| WAITING_FOR_MODEL | RUNNING, FAILED, CANCELLED | Response normalized, error, or cancellation |
| WAITING_FOR_TOOL | RUNNING, FAILED, CANCELLED | Tool outcome/timeout, fatal policy or cancellation |
| WAITING_FOR_APPROVAL | QUEUED, CANCELLED, FAILED | Approved, rejected/expired, or policy failure |
| SUSPENDED | QUEUED, CANCELLED, FAILED | Explicit resume, cancel, or unrecoverable reconciliation |
| COMPLETED | none | Terminal |
| FAILED | none | Terminal |
| CANCELLED | none | Terminal |

Invalid: any transition out of a terminal state; direct waiting-to-waiting without returning to RUNNING; approval to QUEUED without revalidating the bound request and then transitioning through RUNNING; resume without checking checkpoint schema and execution lease. Recovery should normally create a new linked attempt rather than mutate a terminal run.

Each transition carries expected previous state and version, actor, reason code, timestamp, and event sequence. On version conflict, the writer reloads and reconciles; it does not blindly retry a stale mutation. Database persistence must atomically append transition event and update state/version. In-memory mode applies the same invariant in a single event-loop coordinator. See [event schema](../specifications/event-schema.md).
