# Feature Matrix

YANTRA-001 adds a Python package and local contract foundation. Complete feature families remain incomplete; only the specific implemented portions are marked In Development. Verification is limited to recorded local checks; CI platforms are configured but not verified until GitHub Actions runs.

| Capability | Status | Target phase | Key boundary |
|---|---|---|---|
| Python contracts/state machine | In Development | 1 | Agent/message/budget/result/state/event contracts; no execution loop |
| Provider abstraction | In Development | 1 | Async protocol and deterministic mock; no live adapter |
| Tool registry | In Development | 1 | Typed definitions/validation/schema export; no authorization or execution |
| Events and logging | In Development | 1 | Serializable events and local structured logger; no tracing backend |
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
