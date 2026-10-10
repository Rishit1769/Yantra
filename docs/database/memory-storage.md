# Memory Storage

Memory rows are tenant/owner and namespace scoped, typed with provenance, sensitivity, retention/expiry, and deletion state. Conversation history is not automatically persistent memory; explicit write policy determines what crosses runs. Store content only when justified; prefer bounded references for large artifacts. Sensitive data requires encryption/access controls and must be excluded from embeddings unless specifically approved.

Relational metadata and keyword search are baseline. Optional embeddings/pgvector use versioned model/dimension metadata and support deletion. Retrieval APIs always enforce tenant/session namespace and return provenance. Retention jobs, user deletion requests, and backups must cover derived embeddings. See [memory engine](../architecture/memory-engine.md).
