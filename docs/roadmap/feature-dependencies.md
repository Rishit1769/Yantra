# Feature Dependencies

```mermaid
flowchart TD
  Contracts[Typed/versioned contracts] --> Runtime[Runtime kernel/state machine]
  Contracts --> Gateway[Model gateway]
  Runtime --> Tools[Tool registry/policy/executor]
  Gateway --> Runtime
  Runtime --> Events[Events/observability]
  Events --> Persistence[Persistence service + PostgreSQL]
  Persistence --> Sessions[Durable sessions]
  Persistence --> Checkpoints[Checkpoint/recovery]
  Tools --> Approval[Human approval]
  Tools --> Sandbox[Sandbox]
  Contracts --> Skills[Skill manifest/registry]
  Skills --> Context[Context engine]
  Context --> Memory[Memory]
  Persistence --> Memory
  Memory -. optional .-> Vector[pgvector]
  Runtime --> Workflow[Workflow engine]
  Runtime --> Multi[Multi-agent scheduler]
  Events --> Inspector[Optional inspector]
  Persistence --> Workers[Distributed workers]
```

Core ordering: contract/versioning -> runtime/gateway/tool policy -> events -> durable service -> recovery -> skills/sandbox -> workflows/multi-agent/memory -> optional platform. Browser requires network policy and isolated worker. pgvector is optional and cannot block keyword memory. Inspector depends on APIs but no runtime component depends on it. NIRMAAN consumes public SDK only.
