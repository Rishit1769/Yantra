# Feature Matrix

Repository inspection found no application source or package metadata. Every capability below is therefore **Proposed**, not implemented or verified.

| Capability | Status | Target phase | Key boundary |
|---|---|---|---|
| Python runtime, agent loop, typed contracts | Proposed | 1 | Async core, no mandatory database |
| Provider adapters and routing | Proposed | 1 / research | Capabilities negotiated, no vendor lock-in |
| Tools, permissions, audit | Proposed | 1-3 | Model cannot authorize its own call |
| Events and basic tracing | Proposed | 1 | Structured, redacted observations |
| PostgreSQL persistence | Proposed | 2 | Python calls versioned TypeScript service |
| Sessions, checkpoints, recovery | Proposed | 2 | No exactly-once external effects guarantee |
| Skills and validation | Proposed | 3 | Imported/generated content untrusted |
| Scraping, browser, sandbox | Proposed | 3 | Optional and policy constrained |
| Multi-agent and workflows | Proposed | 4 | Bounded concurrency, budgets, delegation depth |
| Memory and optional pgvector | Proposed | 4 | Core works without vector extension |
| MCP and plugin integrations | Proposed | 4 | Least privilege and versioned manifests |
| Inspector, workers, eval platform | Proposed | 5 | Inspector is optional; evidence required |
| Adaptive context/routing/recovery/learning | Proposed, experimental | Research | No quality claim before evaluation |

See the [roadmap](../../ROADMAP.md) for release gates. “Implemented” requires merged code; “Verified” requires tests and evidence meeting the acceptance criteria.
