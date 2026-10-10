# Terminology

| Term | Meaning |
|---|---|
| Agent | Model-driven entity with a definition, policy, context sources, and available capabilities. |
| Runtime | Process-local execution kernel that coordinates runs and state transitions. |
| Run | One bounded attempt to execute an agent request; identified independently from a session. |
| Session | Durable or in-memory grouping of related runs and conversation history. |
| Task | A unit of work within a run or workflow, optionally delegated. |
| Tool | A single executable capability with a schema, permission, limits, and side-effect classification. |
| Skill | Versioned package of instructions, resources, metadata, dependencies, and declared capabilities; not inherently executable code. |
| Provider adapter | Connector translating the provider-neutral model contract to a particular inference API. |
| Event | Versioned observation of a state transition or execution fact; not itself proof that an external effect completed. |
| Checkpoint | Durable, versioned snapshot sufficient to resume from a defined safe boundary. |
| Persistence service | TypeScript service owning database access via Prisma; Python depends only on its versioned contract. |
| Inspector | Optional future UI consuming authorized execution and registry APIs. |

“May”, “should”, and “must” are used normatively: must is required for conformance; should indicates a default with documented exception; may is optional. Capability and implementation status are separate: a specified feature is not necessarily implemented.
