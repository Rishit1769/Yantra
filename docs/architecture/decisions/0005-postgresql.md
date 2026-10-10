# ADR 0005: PostgreSQL

- Status: Proposed
- Context: Durable relational execution, tenant, event, skill, and workflow records need transactions and constraints.
- Decision: PostgreSQL is primary production database; local memory remains available.
- Alternatives: SQLite-only; document stores; multiple mandatory databases.
- Consequences: Strong relational integrity and JSONB; operational PostgreSQL is an optional deployment requirement for durable mode.
- Tradeoffs: Service/database operations add complexity; no database required for simple local use.
