# Runtime Contract

Proposed public `Runtime` exposes asynchronous `run`, `stream`, `cancel`, and `resume` operations over typed agent/session/input/budget objects. `run` returns a terminal or suspended result with run/session IDs, status, output, event cursor, and usage fields that may be unknown. `stream` yields versioned events and has bounded buffering/backpressure behavior. Cancellation is best effort and reports confirmation status.

Runtime owns the state machine, independent authorization, budgets, and tool dispatch. Adapter callbacks cannot mutate state directly. Public methods validate schema versions and deadlines. Exact Python signatures remain subject to API review; consumers must not depend on internal modules. See [compatibility policy](compatibility-policy.md).
