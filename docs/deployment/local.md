# Local Development Deployment

The target lightweight mode runs the Python runtime in process with an in-memory persistence adapter. It must not require PostgreSQL, Redis, pgvector, Playwright, or an inspector for basic SDK use. Provider access is optional and requires user-supplied credentials through a secret source. This mode is non-durable: process exit loses state and must be clearly labeled.

No local command currently exists. Future instructions must be verified in a clean environment and state supported OS/Python versions and optional extras.
