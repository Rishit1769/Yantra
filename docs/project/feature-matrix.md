# Feature Matrix

YANTRA-001 adds a Python package and local contract foundation. YANTRA-002 adds the model gateway; YANTRA-003 adds a bounded model/tool loop; YANTRA-004 adds focused tool authorization, trusted approvals, and restricted subprocess execution. The table marks the implemented scope, not completeness of broader feature families. The configured nine-job Ubuntu/macOS/Windows × Python 3.12/3.13/3.14 matrix passed in RR-003 run [39114896871](https://github.com/Rishit1769/Yantra/actions/runs/39114896871) on commit `2f07ec9`. RR-004 is the current source of package/release status.

| Capability | Status | Target phase | Key boundary |
|---|---|---|---|
| Python contracts/state machine | Implemented | 1 | Typed contracts/state/event foundation; no durable persistence |
| Bounded agent runtime (YANTRA-003) | Implemented, experimental | 1 | Sequential model/tool loop, bounded controls, cancellation, and usage/cost accounting; budgets are not hard billing ceilings |
| Model gateway (YANTRA-002) | Implemented | 1 | Normalized adapters, mocked protocol tests; live provider/model behavior remains limited/unknown |
| Developer smoke CLI (YANTRA-002-V01) | Implemented | 1 | Offline mock and opt-in provider smoke checks; not a general agent CLI |
| Provider abstraction | Implemented | 1 | Async protocol, deterministic mock, explicit provider registry |
| Tool registry and policy (YANTRA-004) | Implemented | 1 | Typed definitions, name allowlist, exact scopes, trusted approvals, and engine-authorized dispatch |
| Restricted worker subprocess (YANTRA-004) | Implemented, limited | 1 | Fixed handler IDs, bounded JSON IPC and direct-child lifecycle; not an OS sandbox and no descendant/resource guarantee |
| Events and logging | Implemented | 1 | Serializable runtime events and local structured logger; no tracing backend |
| Hosted CI matrix | Verified for RR-003 source | 1 | All nine configured jobs passed; RR-004's final commit still requires its own CI result before release |
| PostgreSQL persistence | Proposed | 2 | Python calls versioned TypeScript service; not used in YANTRA-001 |
| Sessions, checkpoints, recovery | Proposed | 2 | No exactly-once external effects guarantee |
| Skills and validation | Proposed | 3 | Imported/generated content untrusted |
| Scraping, browser, sandbox | Proposed | 3 | Optional and policy constrained |
| Multi-agent and workflows | Proposed | 4 | Bounded concurrency, budgets, delegation depth |
| Memory and optional pgvector | Proposed | 4 | Core works without vector extension |
| MCP and plugin integrations | Proposed | 4 | Least privilege and versioned manifests |
| Inspector, workers, eval platform | Proposed | 5 | Inspector is optional; evidence required |
| Adaptive context/routing/recovery/learning | Proposed, experimental | Research | No quality claim before evaluation |

See the [roadmap](../../ROADMAP.md) for release gates. “Implemented” requires merged code; “Verified” requires tests and evidence meeting the acceptance criteria.
