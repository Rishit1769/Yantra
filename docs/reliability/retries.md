# Retries

Retry only transient, classified failures, with exponential backoff and jitter, maximum attempts, overall deadline, and per-provider/tool rate constraints. Honor server retry hints only within configured bounds. Do not retry validation, authorization, unsupported capability, policy denial, or irreversible ambiguous effects automatically. Provider inference retries may incur duplicate cost even without application side effects.

Persist attempt number/reason where durability is enabled. A retry is a new attempt linked to the logical operation, not an invisible repetition. Circuit breakers and rate limiters are separate controls. Tests inject timeouts, 429s, malformed hints, and cancellation during sleep.
