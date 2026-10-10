"""Deterministic, opt-in routing policy with digest-bound approval."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from yantra.core.contracts import ModelCapability
from yantra.core.errors import RoutingPolicyError
from yantra.providers.catalog import ModelCatalogEntry
from yantra.providers.identifiers import ModelIdentifier


class RoutingMode(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class RoutingDecision(BaseModel):
    """Auditable reason for a deterministic provider/model selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_model: str
    mode: RoutingMode
    reason: str = Field(min_length=1, max_length=1000)
    fallback_from: str | None = None


class ModelRoutingPolicy(BaseModel):
    """Manual selection defaults; optional routing requires approval of exact settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approved_providers: frozenset[str] = frozenset()
    approved_models: frozenset[str] = frozenset()
    automatic_enabled: bool = False
    automatic_model_order: tuple[str, ...] = ()
    fallback_enabled: bool = False
    fallback_chain: tuple[str, ...] = ()
    local_only: bool = False
    allow_local_to_cloud: bool = False
    max_attempts_per_provider: int = Field(default=1, ge=1, le=5)
    max_estimated_cost_usd: Decimal | None = Field(default=None, gt=0)
    approval_digest: str | None = None

    def approval_fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"approval_digest"})
        payload["approved_providers"] = sorted(self.approved_providers)
        payload["approved_models"] = sorted(self.approved_models)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def approve(self) -> ModelRoutingPolicy:
        """Return a copy approved for this exact optional-routing configuration."""
        return self.model_copy(update={"approval_digest": self.approval_fingerprint()})

    @property
    def optional_routing_approved(self) -> bool:
        return self.approval_digest == self.approval_fingerprint()

    def authorize_model(
        self,
        reference: str,
        *,
        is_local: bool,
        estimated_cost_usd: Decimal | None = None,
        enforce_cost: bool = True,
    ) -> ModelIdentifier:
        identifier = ModelIdentifier.parse(reference)
        if self.approved_providers and identifier.provider_id not in self.approved_providers:
            raise RoutingPolicyError(f"provider {identifier.provider_id!r} is not approved")
        if self.approved_models and reference not in self.approved_models:
            raise RoutingPolicyError(f"model {reference!r} is not approved")
        if self.local_only and not is_local:
            raise RoutingPolicyError("policy permits local models only")
        if enforce_cost and self.max_estimated_cost_usd is not None:
            if estimated_cost_usd is None:
                raise RoutingPolicyError(
                    "cannot enforce cost limit because model pricing is unknown"
                )
            if estimated_cost_usd > self.max_estimated_cost_usd:
                raise RoutingPolicyError("estimated request cost exceeds the configured limit")
        return identifier

    def choose_automatic(
        self,
        candidates: Iterable[ModelCatalogEntry],
        *,
        required_capabilities: frozenset[ModelCapability],
        is_local_by_provider: dict[str, bool],
        estimated_input_tokens: int | None,
        max_output_tokens: int | None,
    ) -> tuple[ModelCatalogEntry, ...]:
        if not self.automatic_enabled or not self.optional_routing_approved:
            raise RoutingPolicyError(
                "automatic routing is disabled or lacks current policy approval"
            )

        by_reference = {entry.reference: entry for entry in candidates}
        ordered = [entry for ref in self.automatic_model_order if (entry := by_reference.get(ref))]
        eligible: list[ModelCatalogEntry] = []
        for entry in ordered:
            is_local = is_local_by_provider.get(entry.provider_id, False)
            estimated_cost = None
            if (
                entry.pricing is not None
                and estimated_input_tokens is not None
                and max_output_tokens is not None
            ):
                estimated_cost = entry.pricing.estimate_maximum(
                    input_tokens=estimated_input_tokens,
                    output_tokens=max_output_tokens,
                )
            try:
                self.authorize_model(
                    entry.reference,
                    is_local=is_local,
                    estimated_cost_usd=estimated_cost,
                )
            except RoutingPolicyError:
                continue
            if not all(
                entry.capabilities.supports(capability) for capability in required_capabilities
            ):
                continue
            if self.max_estimated_cost_usd is not None:
                if (
                    estimated_input_tokens is None
                    or max_output_tokens is None
                    or entry.pricing is None
                ):
                    continue
                if estimated_cost is None or estimated_cost > self.max_estimated_cost_usd:
                    continue
            eligible.append(entry)
        if not eligible:
            raise RoutingPolicyError("no approved model satisfies the routing constraints")
        return tuple(eligible)

    def approved_fallbacks(
        self,
        *,
        original: str,
        original_is_local: bool,
        is_local_by_provider: dict[str, bool],
    ) -> tuple[str, ...]:
        if not self.fallback_enabled:
            return ()
        if not self.optional_routing_approved:
            raise RoutingPolicyError("fallback routing is enabled without current policy approval")
        approved: list[str] = []
        for reference in self.fallback_chain:
            if reference == original:
                continue
            identifier = ModelIdentifier.parse(reference)
            fallback_is_local = is_local_by_provider.get(identifier.provider_id, False)
            if original_is_local and not fallback_is_local and not self.allow_local_to_cloud:
                raise RoutingPolicyError(
                    "local-to-cloud fallback requires explicit policy approval"
                )
            self.authorize_model(
                reference,
                is_local=fallback_is_local,
                enforce_cost=False,
            )
            approved.append(reference)
        return tuple(approved)
