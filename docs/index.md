# YANTRA Documentation

This site describes a proposed architecture, not implemented or verified behavior. All feature contracts use **Proposed** status unless explicitly marked otherwise. No feature is production-ready by virtue of being specified.

## Start here

- [Project vision](project/vision.md), [goals](project/goals.md), [non-goals](project/non-goals.md), [terminology](project/terminology.md), [feature matrix](project/feature-matrix.md)
- [Introduction](getting-started/introduction.md), [proposed installation](getting-started/installation.md), [proposed quickstart](getting-started/quickstart.md), [configuration](getting-started/configuration.md), [first agent](getting-started/first-agent.md)
- [Architecture overview](architecture/overview.md), [system design](architecture/system-design.md), [runtime kernel](architecture/runtime-kernel.md), [execution lifecycle](architecture/execution-lifecycle.md), [state machine](architecture/state-machine.md)
- [Specifications](specifications/agent-contract.md), [compatibility policy](specifications/compatibility-policy.md)
- [Security threat model](security/threat-model.md), [development standards](development/coding-standards.md), [roadmap](../ROADMAP.md)

## Architecture

See [component boundaries](architecture/component-boundaries.md), [event design](architecture/event-driven-design.md), [gateway](architecture/model-gateway.md), [tool engine](architecture/tool-engine.md), [skill engine](architecture/skill-engine.md), [memory](architecture/memory-engine.md), [context](architecture/context-engine.md), [orchestration](architecture/orchestration-engine.md), [plugins](architecture/plugin-system.md), and [persistence](architecture/persistence-architecture.md). [ADRs](architecture/decisions/) record major choices.

## Features

Feature specifications are organized in [features](features/). Major systems include [runtime](features/agent-runtime.md), [providers](features/model-providers.md), [tools](features/tool-execution.md), [skills](features/skill-registry.md), [sessions](features/sessions.md), [checkpoints](features/checkpoints.md), [memory](features/memory.md), [workflows](features/workflows.md), [security-sensitive execution](features/sandboxing.md), [evaluations](features/evaluations.md), and the [optional inspector](features/inspector.md).

## Database and contracts

- [Database overview](database/overview.md), [PostgreSQL](database/postgresql.md), [Prisma](database/prisma.md), [persistence service](database/persistence-service.md), [entity model](database/entity-model.md), [relationships](database/relationships.md)
- [Persistence contract](specifications/persistence-contract.md), [event schema](specifications/event-schema.md), [message schema](specifications/message-schema.md), [error taxonomy](specifications/error-taxonomy.md)

## Trust, resilience, and operations

- [Security](security/threat-model.md), [permissions](security/permission-system.md), [sandbox](security/sandbox-security.md), [prompt injection](security/prompt-injection.md), [browser security](security/browser-security.md)
- [Reliability](reliability/fault-tolerance.md), [retries](reliability/retries.md), [cancellation](reliability/cancellation.md), [recovery](reliability/crash-recovery.md), [idempotency](reliability/idempotency.md)
- [Deployment](deployment/local.md), [Docker](deployment/docker.md), [production gates](deployment/production.md), [observability](features/observability.md)

## Integrations, research, and development

- [NIRMAAN boundary](integrations/nirmaan.md); provider integration pages are design notes, not claims of working integrations.
- [Research objectives](research/objectives.md), [adaptive context](research/adaptive-context.md), [adaptive routing](research/adaptive-routing.md), [evidence-guided recovery](research/evidence-guided-recovery.md), [skill learning](research/skill-learning.md), [benchmarks](research/benchmarks.md), [reproducibility](research/reproducibility.md)
- [Development setup](development/setup.md), [testing strategy](development/testing-strategy.md), [documentation standards](development/documentation-standards.md), [release process](development/release-process.md)
- [Milestones](roadmap/milestones.md), [dependencies](roadmap/feature-dependencies.md), [acceptance criteria](roadmap/acceptance-criteria.md), [production readiness](roadmap/production-readiness.md)

## Status vocabulary

Feature implementation status is one of Proposed, Specified, In Development, Implemented, Verified, or Deprecated. This repository's source inspection found only documentation; therefore no runtime status is above Proposed/Specified. “Verified” requires recorded evidence and reproducible checks.
