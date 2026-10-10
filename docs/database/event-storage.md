# Event Storage

Durable events are append-only and sequenced per run. PostgreSQL transactions allocate sequence and update current state atomically. Keep event envelope/index fields relational and type-specific bounded payload in JSONB. Large prompt/tool/artifact bodies are omitted or stored by classified reference. Apply retention, partitioning, export, and deletion policies before high-volume rollout. Telemetry exporter delivery is distinct from durable event commit. The inspector reads through authorized APIs, not direct database credentials.
