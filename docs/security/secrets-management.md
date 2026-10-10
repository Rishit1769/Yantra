# Secrets Management

Credentials are supplied as references to environment-specific secret stores or workload identity; plaintext values are resolved only at the narrow adapter boundary. Never store raw credentials in PostgreSQL, agent definitions, skill manifests, events, logs, traces, checkpoints, artifacts, or CLI output. Redaction must cover headers, exception messages, URLs, and provider payloads.

Use distinct credentials/scopes per provider and integration, rotate/revoke, restrict egress, and avoid passing secrets to models/tools. Configuration dumps and diagnostics must emit reference identifiers only. Secret scanning is a release gate; response to exposure includes revocation and incident record.
