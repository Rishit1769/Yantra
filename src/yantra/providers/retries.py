"""Bounded retry policy for provider calls; defaults to no paid retries."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

from yantra.core.errors import ProviderError, ProviderRateLimitError


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 1
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 4.0

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be in [1, 5]")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("retry delays must be non-negative and max >= base")

    def can_retry(self, error: ProviderError, attempt: int) -> bool:
        """Only retry explicitly retryable errors, before the bounded attempt limit."""
        return attempt < self.max_attempts and error.retryable

    async def wait(self, error: ProviderError, attempt: int) -> None:
        delay = min(self.base_delay_seconds * (2 ** (attempt - 1)), self.max_delay_seconds)
        if isinstance(error, ProviderRateLimitError) and error.retry_after_seconds is not None:
            delay = min(max(delay, error.retry_after_seconds), self.max_delay_seconds)
        if delay:
            await asyncio.sleep(random.uniform(delay / 2, delay))
