# Agent Contract

**Status: Proposed, schema version 1 design.** An agent definition is immutable for an individual run and includes stable `agent_id`, `definition_version`, display name, instruction content/reference, model preference, tool and skill references, policy reference, context sources, and finite default budgets. It contains no credential values.

Validation rejects unknown security-sensitive fields, unresolved capability references, invalid budget ranges, and unpinned skill versions in reproducible deployments. Application identity/tenant scope comes from authenticated invocation context. Updating an agent creates a new definition version; historic runs refer to the version and, where permitted, a content digest. Agent definition is not executable authority: runtime policy and registered capability metadata decide what can execute.

Acceptance: schema fixtures round-trip deterministically; invalid references fail before run creation; secrets are rejected/redacted; version changes do not mutate historical run snapshots.
