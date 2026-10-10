# Event Schema

Event envelope: `schema_version`, `event_id`, `event_type`, `occurred_at`, `recorded_at`, `producer`, `tenant_id` when applicable, `session_id`, `run_id`, `task_id`, per-run `sequence`, `correlation_id`, `causation_id`, `payload`, and `classification`. Payload schemas are type-specific and versioned. Event IDs are unique; `(run_id, sequence)` is unique and monotonically allocated transactionally for durable runs.

Events are append-only observations. Corrections are compensating events, never edits. Consumers tolerate duplicates by event ID and gaps by detecting sequence discontinuity. PII, secrets, full prompts, and large artifacts are excluded or redacted by policy. Event retention is configurable and bounded. Event reprocessing cannot trigger external effects.
