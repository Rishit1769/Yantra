# Secrets Management

Credentials are supplied as references to environment-specific secret stores or workload identity; plaintext values are resolved only at the narrow adapter boundary. Never store raw credentials in PostgreSQL, agent definitions, skill manifests, events, logs, traces, checkpoints, artifacts, or CLI output. Redaction must cover headers, exception messages, URLs, and provider payloads.

Use distinct credentials/scopes per provider and integration, rotate/revoke, restrict egress, and avoid passing secrets to models/tools. Configuration dumps and diagnostics must emit reference identifiers only. Secret scanning is a release gate; response to exposure includes revocation and incident record.

The gateway supports environment references and an optional OS-keyring extra. Keyring storage fails closed when the OS backend is unavailable; it does not fall back to plaintext. Explicit smoke tests require both a model and billable-inference opt-in when the provider lacks a non-inference validation endpoint. Smoke tests are not a default credential check. Mocked tests cover secret isolation; live provider redaction has not been independently verified.
