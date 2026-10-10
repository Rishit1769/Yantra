# Production Deployment

No production configuration is currently supported. A future supported topology includes Python application/workers, authenticated TypeScript persistence service, PostgreSQL, telemetry backend, secret manager, and optional isolated tool/browser workers. Inspector and Redis remain optional.

Before support is claimed, document versions, network paths, TLS/identity, tenant boundaries, backup/restore, migrations, scaling, resource quotas, incident response, data retention, monitoring, and tested failure modes. Unsupported until validated: multi-region active-active writes, arbitrary hostile code on shared Docker workers, exactly-once external effects, and unreviewed plugin execution. See [production-readiness gates](../roadmap/production-readiness.md).
