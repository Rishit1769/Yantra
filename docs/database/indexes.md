# Indexes

Initial index candidates are listed in [entity model](entity-model.md). All indexes require query-plan validation on representative cardinality. Primary access paths include tenant+session chronology, run state recovery, per-run event sequence, tool/model attempts by run and time, pending approval expiry, skill identity/version, memory namespace/expiry, and audit actor/target chronology. Use partial indexes for active/pending states where measured; avoid broad JSONB GIN indexes without a query need.

High-volume event tables may need time partitioning and retention-driven partition drops, but partition keys and uniqueness constraints must be tested with Prisma and query patterns. Index creation/maintenance strategy must avoid unacceptable production locks; use supported concurrent operations in controlled migrations where appropriate.
