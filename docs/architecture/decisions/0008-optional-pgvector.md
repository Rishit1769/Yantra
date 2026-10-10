# ADR 0008: Optional pgvector

- Status: Proposed
- Context: Semantic memory/skill search may help, but embeddings add cost, migrations, and operational complexity.
- Decision: pgvector is optional; relational/keyword paths remain functional without it.
- Alternatives: Require vectors; external vector database; no semantic search.
- Consequences: Easier baseline/local operation and measured adoption; adapter/raw SQL support needs validation.
- Tradeoffs: Search capability differs by deployment; no assumed Prisma-native support for every operation.
