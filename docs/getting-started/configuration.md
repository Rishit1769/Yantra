# Configuration

Configuration is proposed as validated, typed Pydantic v2 models with explicit precedence: constructor arguments, explicit config file, then documented environment variables. Secrets must be injected through a secret source and excluded from serialization, logs, traces, and persistence. Unknown keys should fail validation by default to prevent misspelled security controls.

Expected configuration domains include runtime limits (steps, deadline, tokens), provider endpoint/model/auth reference, tool policy, persistence endpoint and service identity, telemetry exporters, and optional browser/sandbox settings. Secure defaults deny undeclared capabilities, cap resource use, redact content, and leave optional infrastructure disabled. Exact field names and environment variable names remain an implementation decision; see [configuration schema](../specifications/configuration-schema.md).
