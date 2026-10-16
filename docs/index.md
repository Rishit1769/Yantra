# YANTRA Documentation

This site documents implemented YANTRA-001 contracts, the YANTRA-002 model gateway foundation, the experimental YANTRA-003 bounded runtime, and YANTRA-004 secure tool runtime accepted for engineering completion but not released, alongside proposed architecture for later milestones. Feature documents identify implementation status; documentation alone is not proof. No feature is production-ready by virtue of being specified.

## Start here

- [Project vision](project/vision.md), [goals](project/goals.md), [non-goals](project/non-goals.md), [terminology](project/terminology.md), [feature matrix](project/feature-matrix.md)
- [Introduction](getting-started/introduction.md), [source installation](getting-started/installation.md), [core quickstart](getting-started/quickstart.md), [agent runtime quickstart](guides/agent-quickstart.md), [secure tool runtime guide](security/secure-tool-runtime.md), [configuration](getting-started/configuration.md), [first agent](getting-started/first-agent.md)
- [Architecture overview](architecture/overview.md), [system design](architecture/system-design.md), [runtime kernel](architecture/runtime-kernel.md), [agent execution engine](architecture/agent-execution-engine.md), [execution lifecycle](architecture/execution-lifecycle.md), [state machine](architecture/state-machine.md)
- [Core API reference](specifications/core-runtime-api.md), [YANTRA-004 engineering closure](development/yantra-004-engineering-closure.md), [specifications](specifications/agent-contract.md), [compatibility policy](specifications/compatibility-policy.md)
- [Security threat model](security/threat-model.md), [development standards](development/coding-standards.md), [roadmap](../ROADMAP.md)

## Architecture

See [component boundaries](architecture/component-boundaries.md), [event design](architecture/event-driven-design.md), [gateway](architecture/model-gateway.md), [tool engine](architecture/tool-engine.md), [skill engine](architecture/skill-engine.md), [memory](architecture/memory-engine.md), [context](architecture/context-engine.md), [orchestration](architecture/orchestration-engine.md), [plugins](architecture/plugin-system.md), and [persistence](architecture/persistence-architecture.md). [ADRs](architecture/decisions/) record major choices.

## Features

Feature specifications are organized in [features](features/). Major systems include [runtime](features/agent-runtime.md), [providers](features/model-providers.md), [tools](features/tool-execution.md), [skills](features/skill-registry.md), [sessions](features/sessions.md), [checkpoints](features/checkpoints.md), [memory](features/memory.md), [workflows](features/workflows.md), [security-sensitive execution](features/sandboxing.md), [evaluations](features/evaluations.md), and the [optional inspector](features/inspector.md).

## Database and contracts

- [Database overview](database/overview.md), [PostgreSQL](database/postgresql.md), [Prisma](database/prisma.md), [persistence service](database/persistence-service.md), [entity model](database/entity-model.md), [relationships](database/relationships.md)
- [Persistence contract](specifications/persistence-contract.md), [event schema](specifications/event-schema.md), [message schema](specifications/message-schema.md), [error taxonomy](specifications/error-taxonomy.md)

## Trust, resilience, and operations

- [Security](security/threat-model.md), [permissions](security/permission-system.md), [secure tool runtime](security/secure-tool-runtime.md), [sandbox](security/sandbox-security.md), [prompt injection](security/prompt-injection.md), [browser security](security/browser-security.md)
- [Reliability](reliability/fault-tolerance.md), [retries](reliability/retries.md), [cancellation](reliability/cancellation.md), [recovery](reliability/crash-recovery.md), [idempotency](reliability/idempotency.md)
- [Deployment](deployment/local.md), [Docker](deployment/docker.md), [YANTRA PostgreSQL runbook](deployment/yantra-postgresql.md), [production gates](deployment/production.md), [observability](features/observability.md)

## Integrations, research, and development

- [NIRMAAN boundary](integrations/nirmaan.md); provider integration pages are design notes, not claims of working integrations.
- [Research objectives](research/objectives.md), [adaptive context](research/adaptive-context.md), [adaptive routing](research/adaptive-routing.md), [evidence-guided recovery](research/evidence-guided-recovery.md), [skill learning](research/skill-learning.md), [benchmarks](research/benchmarks.md), [reproducibility](research/reproducibility.md)
- [Development setup](development/setup.md), [YANTRA-002 gateway smoke testing](development/smoke-testing.md), [secure tool platform validation](development/secure-tool-platform-validation.md), [testing strategy](development/testing-strategy.md), [documentation standards](development/documentation-standards.md), [release process](development/release-process.md)
- [Core runtime API (YANTRA-001–YANTRA-004-V05)](specifications/core-runtime-api.md)
- [Milestones](roadmap/milestones.md), [dependencies](roadmap/feature-dependencies.md), [acceptance criteria](roadmap/acceptance-criteria.md), [production readiness](roadmap/production-readiness.md)

## Status vocabulary

Feature implementation status is one of Proposed, Specified, In Development, Implemented, Verified, or Deprecated. YANTRA-001 contracts and the YANTRA-002 gateway foundation are implemented with local mocked tests; YANTRA-003 adds a bounded offline agent runtime; YANTRA-004-V01–V05 add and verify exact-match logical authorization, trusted approvals, engine-issued dispatch authorization, and a restricted subprocess boundary. Engineering acceptance is not a release or production claim. Windows, Python 3.13/3.14, hosted CI, and a fresh YANTRA-004 package build remain unverified; subprocess execution is not OS sandboxing.
