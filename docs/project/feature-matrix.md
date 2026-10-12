# Feature Matrix

YANTRA-001 adds a Python package and local contract foundation. YANTRA-002 adds the model gateway foundation. Complete feature families remain incomplete; only the specific implemented portions are marked In Development. The 3-operating-system/3-Python CI matrix is configured, but hosted execution is pending; configuration is not verification.

| Capability | Status | Target phase | Key boundary |
|---|---|---|---|
| Python contracts/state machine | In Development | 1 | Agent/message/budget/result/state/event contracts; no execution loop |
| Model gateway (YANTRA-002) | In Development | 1 | Normalized adapters and mocked wire tests; provider behavior not live-verified |
| Developer smoke CLI (YANTRA-002-V01) | In Development | 1 | Offline mock and manual Ollama/OpenCode checks; not an agent runner |
| Provider abstraction | In Development | 1 | Async protocol, deterministic mock, and explicit provider registry |
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
