# ADR 0006: Prisma ORM and Migrate

- Status: Proposed
- Context: Persistence layer is TypeScript and requires typed database access and migration management.
- Decision: Use Prisma ORM/Client and Prisma Migrate inside the TypeScript persistence service.
- Alternatives: Handwritten query layer; other TypeScript ORMs; Python SQLAlchemy/Alembic.
- Consequences: Generated TypeScript access and migration workflow; extension/custom type support needs validation.
- Tradeoffs: Python has no direct Prisma dependency; raw SQL for pgvector may need a narrow adapter. SQLAlchemy/Alembic are excluded.
