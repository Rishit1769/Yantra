# Architecture Overview

YANTRA is designed as a Python async SDK/runtime surrounded by replaceable adapters. A TypeScript persistence service is the exclusive owner of PostgreSQL and Prisma. The core can run with in-memory state; durable deployment adds the service and PostgreSQL. Optional browser, sandbox, vector, Redis, workers, and inspector components are outside the minimum local runtime.

```mermaid
flowchart TB
  App[Application / SDK] --> Kernel[Python runtime kernel]
  Kernel --> Context[Context and memory interfaces]
  Kernel --> Gateway[Model gateway]
  Gateway --> Adapter[Provider adapters]
  Kernel --> Policy[Policy / approval]
  Policy --> Tools[Tool and skill engine]
  Tools --> External[External systems / isolated workers]
  Kernel --> EventBus[Typed execution events]
  EventBus --> OTel[OpenTelemetry exporters]
  Kernel --> Persist[Python persistence port]
  Persist -->|versioned RPC| TS[TypeScript service]
  TS --> Prisma[Prisma Client + Migrate]
  Prisma --> DB[(PostgreSQL)]
  DB -. optional .-> Vec[pgvector]
  UI[Optional inspector] --> TS
```

Trust boundaries are detailed in the [threat model](../security/threat-model.md). The runtime is authoritative for policy and run state; model output, skills, plugins, tool inputs, browser content, and RPC payloads are untrusted until validated.
