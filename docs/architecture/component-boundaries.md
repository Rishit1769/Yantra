# Component Boundaries

| Component | Owns | Must not own |
|---|---|---|
| Python SDK/runtime | Agent loop, typed state, policy decisions, budgets, events | Prisma client, app-specific business policy, provider credentials in logs |
| Provider adapter | Provider protocol/auth mapping, capability declaration, response normalization | Tool authorization or run state authority |
| Tool executor | Schema validation, permission enforcement, bounded dispatch, result normalization | Deciding its own permission grants from model input |
| Skill engine | Manifest/content validation, version resolution, context loading | Implicit code execution or permission escalation |
| Persistence service (TypeScript) | Prisma/database access, tenant scoping, durable transaction boundaries | Agent loop or model calls |
| PostgreSQL | Durable relational state and constraints | Raw secrets or unbounded transient trace payloads |
| Worker/sandbox | Narrow task execution under resource limits | Trusting Docker as the sole isolation guarantee |
| Inspector | Authorized read/approval UX through APIs | Direct database access or being required by headless SDK |
| Application | Domain policy and UX | Modifying YANTRA internal state outside contracts |

Interfaces are versioned and validated at process boundaries. Avoid circular dependencies and hidden shared mutable state.
