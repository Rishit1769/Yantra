# Error Taxonomy

Stable categories: `VALIDATION`, `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `UNSUPPORTED_CAPABILITY`, `RATE_LIMITED`, `TIMEOUT`, `CANCELLED`, `UNAVAILABLE`, `QUOTA_EXCEEDED`, `POLICY_DENIED`, `APPROVAL_REQUIRED`, `RESOURCE_LIMIT`, `PROVIDER_REFUSAL`, `AMBIGUOUS_EFFECT`, `CHECKPOINT_INCOMPATIBLE`, `INTERNAL`. Errors include safe message, retryability hint, subsystem, correlation ID, and optional typed details; never include credentials or unredacted arbitrary provider payload by default.

Retryability is advisory and conditioned on operation idempotency and deadline. `AMBIGUOUS_EFFECT` must not be converted to success or blindly retried. Internal exceptions are logged with protected correlation and exposed as sanitized errors.

Provider HTTP errors may expose the HTTP status, a syntax-validated provider error code, a syntax-validated request/correlation ID, and sanitized request-shape metadata (method, endpoint path for OpenCode, header names, and top-level JSON field names). Header values, prompt/body values, and arbitrary upstream response bodies/messages are never retained in these diagnostics.
