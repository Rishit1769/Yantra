# Audit Logging

Audit records capture security-relevant actor, action, target, outcome, timestamp, correlation ID, policy version, and bounded metadata for permission decisions, approvals, plugin/skill changes, secret access references, tenant administration, and retention/deletion. Audit is append-only to application roles and access is restricted. It is distinct from high-volume debug traces.

Never include raw secrets or unnecessary prompts/tool content. Define retention and tamper detection/integrity strategy before relying on audit for investigations. Failure to durably record a required security action blocks that action according to policy; ordinary telemetry exporter failure need not block runtime.
