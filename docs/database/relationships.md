# Entity Relationships

```mermaid
erDiagram
  TENANT ||--o{ USER : contains
  TENANT ||--o{ AGENT : owns
  AGENT ||--o{ AGENT_CONFIGURATION : versions
  TENANT ||--o{ SESSION : scopes
  USER ||--o{ SESSION : owns
  SESSION ||--o{ RUN : contains
  AGENT_CONFIGURATION ||--o{ RUN : configures
  RUN ||--o{ TASK : contains
  TASK ||--o{ TASK : delegates
  RUN ||--o{ EXECUTION_EVENT : records
  RUN ||--o{ CHECKPOINT : snapshots
  RUN ||--o{ TOOL_EXECUTION : invokes
  TASK ||--o{ TOOL_EXECUTION : contains
  RUN ||--o{ MODEL_INVOCATION : calls
  TENANT ||--o{ SKILL : owns
  SKILL ||--o{ SKILL_VERSION : releases
  SKILL_VERSION ||--o{ SKILL_DEPENDENCY : requires
  SKILL_VERSION ||--o{ SKILL_PERMISSION : declares
  TENANT ||--o{ PLUGIN : registers
  WORKFLOW_DEFINITION ||--o{ WORKFLOW_EXECUTION : instantiates
  RUN ||--o{ WORKFLOW_EXECUTION : executes
  RUN ||--o{ APPROVAL_REQUEST : gates
  TENANT ||--o{ MEMORY_RECORD : scopes
  TENANT ||--o{ ARTIFACT : owns
  TENANT ||--o{ AUDIT_EVENT : records
```

Diagram omits scalar fields and optional ownership edges for readability. Every reference and optionality must be reflected in migrations and API validation. Use cascade deletion only where retention/legal policy permits; otherwise retain tombstones or anonymize with audited workflows. No raw credentials are modeled.
