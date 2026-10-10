"""Provider model discovery, truthful metadata, and bounded in-memory caching."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from yantra.core.contracts import ModelCapability, ProviderCapabilities, TokenUsage
from yantra.core.errors import ProviderError, UnsupportedCapabilityError
from yantra.providers.identifiers import ModelIdentifier
from yantra.providers.registry import ProviderRegistry


class ModelAvailability(StrEnum):
    LISTED = "listed"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ModelPricing(BaseModel):
    """Provider-sourced pricing per million tokens; missing prices stay unknown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_usd_per_million: Decimal | None = Field(default=None, ge=0)
    output_usd_per_million: Decimal | None = Field(default=None, ge=0)
    cached_input_usd_per_million: Decimal | None = Field(default=None, ge=0)
    source: str | None = Field(default=None, max_length=512)

    def estimate(self, usage: TokenUsage) -> Decimal | None:
        if self.input_usd_per_million is None or self.output_usd_per_million is None:
            return None
        cached = usage.cached_input_tokens or 0
        ordinary_input = usage.input_tokens - cached
        cached_rate = self.cached_input_usd_per_million or self.input_usd_per_million
        return (
            Decimal(ordinary_input) * self.input_usd_per_million
            + Decimal(cached) * cached_rate
            + Decimal(usage.output_tokens) * self.output_usd_per_million
        ) / Decimal(1_000_000)

    def estimate_maximum(self, *, input_tokens: int, output_tokens: int) -> Decimal | None:
        if self.input_usd_per_million is None or self.output_usd_per_million is None:
            return None
        return (
            Decimal(input_tokens) * self.input_usd_per_million
            + Decimal(output_tokens) * self.output_usd_per_million
        ) / Decimal(1_000_000)


class ModelCatalogEntry(BaseModel):
    """Normalized catalog metadata; listing never asserts inference access."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    model_id: str = Field(min_length=1, max_length=512)
    display_name: str | None = Field(default=None, max_length=256)
    is_local: bool = False
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)
    availability: ModelAvailability = ModelAvailability.LISTED
    context_window_tokens: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    input_modalities: tuple[str, ...] = ("text",)
    output_modalities: tuple[str, ...] = ("text",)
    pricing: ModelPricing | None = None
    protocol: str | None = Field(default=None, max_length=64)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    last_refreshed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def reference(self) -> str:
        return str(ModelIdentifier(provider_id=self.provider_id, model_id=self.model_id))


class ModelDiscovery(Protocol):
    async def list_models(self) -> Sequence[ModelCatalogEntry]:
        """Return provider catalog metadata without claiming account access."""
        ...


class ModelCatalog:
    """Async catalog cache backed by registered adapters that implement discovery."""

    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        ttl_seconds: float = 300.0,
        max_models_per_provider: int = 10_000,
        max_cached_providers: int = 100,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_models_per_provider < 1 or max_cached_providers < 1:
            raise ValueError("catalog cache limits must be positive")
        self._registry = registry
        self._ttl_seconds = ttl_seconds
        self._max_models_per_provider = max_models_per_provider
        self._max_cached_providers = max_cached_providers
        self._cache: dict[str, tuple[float, tuple[ModelCatalogEntry, ...]]] = {}
        self._lock = asyncio.Lock()

    async def list_models(
        self,
        provider_id: str,
        *,
        refresh: bool = False,
        required_capabilities: Iterable[ModelCapability] = (),
    ) -> tuple[ModelCatalogEntry, ...]:
        """List provider models, optionally filtering only positively supported capabilities."""
        async with self._lock:
            cached = self._cache.get(provider_id)
            now = time.monotonic()
            if not refresh and cached is not None and cached[0] > now:
                models = cached[1]
            else:
                registration = self._registry.get(provider_id)
                discovery_method = getattr(registration.adapter, "list_models", None)
                if not callable(discovery_method):
                    raise UnsupportedCapabilityError(
                        f"provider {provider_id!r} does not support model discovery",
                        provider_id=provider_id,
                    )
                discovery = cast(ModelDiscovery, registration.adapter)
                try:
                    discovered: tuple[ModelCatalogEntry, ...] = tuple(await discovery.list_models())
                except ProviderError:
                    raise
                except Exception as exc:
                    raise ProviderError(
                        f"provider {provider_id!r} model discovery failed",
                        provider_id=provider_id,
                        retryable=True,
                    ) from exc
                if len(discovered) > self._max_models_per_provider:
                    raise ProviderError(
                        "provider catalog exceeds configured model limit",
                        provider_id=provider_id,
                    )
                if any(model.provider_id != provider_id for model in discovered):
                    raise ProviderError(
                        "provider catalog returned an entry with a different provider ID",
                        provider_id=provider_id,
                    )
                refreshed_at = datetime.now(UTC)
                models = tuple(
                    model.model_copy(
                        update={
                            "last_refreshed_at": refreshed_at,
                            "is_local": registration.metadata.is_local,
                        }
                    )
                    for model in discovered
                )
                if (
                    provider_id not in self._cache
                    and len(self._cache) >= self._max_cached_providers
                ):
                    oldest_provider = min(self._cache, key=lambda key: self._cache[key][0])
                    del self._cache[oldest_provider]
                self._cache[provider_id] = (now + self._ttl_seconds, models)

        required = tuple(required_capabilities)
        if not required:
            return models
        return tuple(
            model
            for model in models
            if all(model.capabilities.supports(capability) for capability in required)
        )

    async def get(self, reference: str, *, refresh: bool = False) -> ModelCatalogEntry | None:
        """Look up the exact provider/model reference, preserving nested slashes."""
        identifier = ModelIdentifier.parse(reference)
        models = await self.list_models(identifier.provider_id, refresh=refresh)
        return next((model for model in models if model.model_id == identifier.model_id), None)

    async def peek(self, reference: str) -> ModelCatalogEntry | None:
        """Return a still-fresh cached entry without triggering network discovery."""
        identifier = ModelIdentifier.parse(reference)
        cached = self._cache.get(identifier.provider_id)
        if cached is None or cached[0] <= time.monotonic():
            return None
        return next((entry for entry in cached[1] if entry.model_id == identifier.model_id), None)

    def invalidate(self, provider_id: str | None = None) -> None:
        """Invalidate one provider cache or all cached catalogs."""
        if provider_id is None:
            self._cache.clear()
        else:
            self._cache.pop(provider_id, None)
