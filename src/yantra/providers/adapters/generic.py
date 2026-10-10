"""Explicitly trusted, configurable OpenAI-compatible inference endpoint."""

from collections.abc import Mapping

import httpx

from yantra.core.contracts import ProviderCapabilities
from yantra.providers.adapters.openai_compatible import OpenAICompatibleAdapter
from yantra.security.credentials import CredentialManager


class GenericOpenAICompatibleAdapter(OpenAICompatibleAdapter):
    """Developer-configured endpoint; a non-empty exact host allowlist is mandatory."""

    def __init__(
        self,
        provider_id: str,
        base_url: str,
        *,
        trusted_hosts: frozenset[str],
        credential_reference: str | None = None,
        credential_manager: CredentialManager | None = None,
        capability_overrides: Mapping[str, ProviderCapabilities] | None = None,
        allow_private_network: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not trusted_hosts:
            raise ValueError("custom provider endpoints require an explicit trusted host allowlist")
        super().__init__(
            provider_id,
            base_url,
            credential_reference=credential_reference,
            credential_manager=credential_manager,
            trusted_hosts=trusted_hosts,
            allow_private_network=allow_private_network,
            capability_overrides=capability_overrides,
            client=client,
        )
