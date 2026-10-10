# Observability

## Overview
Structured logs, traces, metrics, and durable execution events explain runtime behavior without leaking sensitive content.
## Motivation
Debugging, recovery, evaluation, and future inspection require correlated evidence.
## Functional requirements
1. `YANTRA-OBS-001`: Propagate correlation/run/task/invocation IDs across runtime and adapters.
2. `YANTRA-OBS-002`: Emit state, model, tool, workflow, approval, budget, and recovery observations.
3. `YANTRA-OBS-003`: Apply configurable redaction before logs, traces, and exports.
4. `YANTRA-OBS-004`: Support replay from observations without external side-effect execution.
## Non-functional requirements
Security: data minimization. Performance: bounded async exporters. Reliability: exporter failure does not corrupt run state. Scalability: sampling/retention. Maintainability: stable event schemas.
## Architecture
structlog JSON logs, OpenTelemetry spans/metrics, optional Prometheus/Grafana, separate durable event store.
## Data flow
Runtime emits typed observation -> redaction/filter -> local event and optional exporter -> retention-controlled consumers.
## Interfaces
Event envelope and telemetry hooks; see [event schema](../specifications/event-schema.md).
## Persistence
Durable execution events distinct from transient telemetry traces; retention independently configured.
## Configuration
Exporter, sampling, trace retention, redaction, payload capture opt-in.
## Security
No secrets; prompts/results off by default; access-controlled audit data.
## Error handling
Exporter outage is observable but should not block core execution unless audit policy requires durable append.
## Observability
Metrics: latency, errors, token usage/cost when known, tool success, queue time, recovery, throughput.
## Testing
Redaction canaries, exporter outage, cardinality bounds, trace correlation, replay no-effects test.
## Acceptance criteria
Secret canaries never reach exporter; every transition has correlation and sequence; telemetry outage behavior meets configured policy; replay cannot dispatch a tool.
## Dependencies
Event contract, OpenTelemetry, structlog.
## Priority
P0.
## Implementation status
Proposed.
## Open questions
Default trace sampling and event retention.
