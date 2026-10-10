"""Explicit provider adapter registry; registration performs no network I/O."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from yantra.core.contracts import ProviderCapabilities
from yantra.core.errors import DuplicateProviderError, ProviderNotFoundError


class ProviderAvailability(StrEnum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ProviderMetadata(BaseModel):
    """Operator-facing adapter metadata, separate from secret values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    display_name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=1000)
    is_local: bool = False
    availability: ProviderAvailability = ProviderAvailability.UNKNOWN


class ProviderRegistration(BaseModel):
    """Immutable registry view; adapter remains a runtime object."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True, frozen=True)

    metadata: ProviderMetadata
    adapter: Any

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self.adapter.capabilities


class ProviderRegistry:
    """Registry supporting built-in and developer-supplied provider adapters."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderRegistration] = {}

    def register(
        self,
        adapter: Any,
        *,
        display_name: str | None = None,
        description: str = "",
        is_local: bool = False,
    ) -> None:
        provider_id = getattr(adapter, "provider_id", None)
        capabilities = getattr(adapter, "capabilities", None)
        complete = getattr(adapter, "complete", None)
        if not isinstance(provider_id, str) or capabilities is None or not callable(complete):
            raise TypeError(
                "provider adapter must expose provider_id, capabilities, and async complete"
            )
        if not isinstance(capabilities, ProviderCapabilities):
            raise TypeError("provider capabilities must be a ProviderCapabilities model")
        if provider_id in self._providers:
            raise DuplicateProviderError(f"provider {provider_id!r} is already registered")
        metadata = ProviderMetadata(
            provider_id=provider_id,
            display_name=display_name or provider_id,
            description=description,
            is_local=is_local,
        )
        self._providers[provider_id] = ProviderRegistration(metadata=metadata, adapter=adapter)

    def get(self, provider_id: str) -> ProviderRegistration:
        """Return a provider registration or raise a typed error."""
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise ProviderNotFoundError(f"provider {provider_id!r} is not registered") from exc

    def list(self) -> tuple[ProviderRegistration, ...]:
        """List providers in stable provider-ID order."""
        return tuple(self._providers[key] for key in sorted(self._providers))

    def set_availability(self, provider_id: str, status: ProviderAvailability) -> None:
        """Update observed availability metadata without probing the network."""
        registration = self.get(provider_id)
        updated = registration.metadata.model_copy(update={"availability": status})
        self._providers[provider_id] = ProviderRegistration(
            metadata=updated,
            adapter=registration.adapter,
        )

    def unregister(self, provider_id: str) -> ProviderRegistration:
        """Remove and return a provider adapter."""
        try:
            return self._providers.pop(provider_id)
        except KeyError as exc:
            raise ProviderNotFoundError(f"provider {provider_id!r} is not registered") from exc
