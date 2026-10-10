"""OpenRouter chat adapter with slash-preserving model IDs and no upstream fallback by default."""

from collections.abc import Mapping
from typing import Any, cast

import httpx
from pydantic import SecretStr

from yantra.core.contracts import ProviderCapabilities
from yantra.core.errors import ProviderError
from yantra.providers.adapters.common import is_json_object
from yantra.providers.adapters.openai_compatible import OpenAICompatibleAdapter
from yantra.providers.base import ModelRequest
from yantra.providers.catalog import ModelCatalogEntry
from yantra.providers.validation import (
    CredentialValidationResult,
    CredentialValidationStatus,
)
from yantra.security.credentials import CredentialManager


class OpenRouterAdapter(OpenAICompatibleAdapter):
    """OpenRouter adapter; provider selection/fallback stays disabled unless enabled explicitly."""

    def __init__(
        self,
        *,
        credential_reference: str | None = "env://OPENROUTER_API_KEY",
        credential_manager: CredentialManager | None = None,
        client: httpx.AsyncClient | None = None,
        capability_overrides: Mapping[str, ProviderCapabilities] | None = None,
        allow_upstream_fallbacks: bool = False,
        http_referer: str | None = None,
        app_title: str | None = None,
    ) -> None:
        super().__init__(
            "openrouter",
            "https://openrouter.ai/api/v1",
            credential_reference=credential_reference,
            credential_manager=credential_manager,
            trusted_hosts=frozenset({"openrouter.ai"}),
            client=client,
            capability_overrides=capability_overrides,
            stream_usage=True,
        )
        self.allow_upstream_fallbacks = allow_upstream_fallbacks
        self.http_referer = http_referer
        self.app_title = app_title

    _allowed_options = OpenAICompatibleAdapter._allowed_options | frozenset({"provider"})

    def _headers(
        self, secret: SecretStr | None = None, request: ModelRequest | None = None
    ) -> dict[str, str]:
        headers = super()._headers(secret, request)
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.app_title:
            headers["X-OpenRouter-Title"] = self.app_title
        return headers

    async def list_models(
        self, *, secret: SecretStr | None = None
    ) -> tuple[ModelCatalogEntry, ...]:
        # The public catalog is not an authenticated account/model-access check.
        payload, _ = await self.request_json("GET", "models", headers=self._headers(secret))
        return self._normalize_catalog(payload)

    def _normalize_catalog(self, payload: Mapping[str, object]) -> tuple[ModelCatalogEntry, ...]:
        entries = super()._normalize_catalog(payload)
        normalized: list[ModelCatalogEntry] = []
        raw_models = payload.get("data", [])
        if not isinstance(raw_models, list):
            return entries
        for entry, raw in zip(entries, cast(list[Any], raw_models), strict=False):
            if not is_json_object(raw):
                normalized.append(entry)
                continue
            parameters = raw.get("supported_parameters")
            caps = entry.capabilities
            if isinstance(parameters, list):
                values = {item for item in cast(list[Any], parameters) if isinstance(item, str)}
                caps = caps.model_copy(
                    update={
                        "tool_calling": "tools" in values,
                        "structured_output": "response_format" in values,
                        "streaming": "stream" in values,
                    }
                )
            normalized.append(entry.model_copy(update={"capabilities": caps}))
        return tuple(normalized)

    def build_chat_payload(self, request: ModelRequest):
        payload = super().build_chat_payload(request)
        user_provider = request.provider_options.get("provider")
        if user_provider is not None and not self.allow_upstream_fallbacks:
            # Prevent an unreviewed per-request override from enabling OpenRouter failover.
            if (
                not is_json_object(user_provider)
                or user_provider.get("allow_fallbacks") is not False
            ):
                raise ProviderError(
                    "OpenRouter provider fallback requires explicit adapter approval",
                    provider_id=self.provider_id,
                )
        payload["provider"] = {
            "allow_fallbacks": self.allow_upstream_fallbacks,
            **(dict(user_provider) if is_json_object(user_provider) else {}),
        }
        return payload

    async def validate_credentials(self, secret: SecretStr | None) -> CredentialValidationResult:
        if secret is None:
            return CredentialValidationResult(
                provider_id=self.provider_id,
                status=CredentialValidationStatus.UNVERIFIED,
                message="OpenRouter credential was not supplied",
            )
        try:
            payload, _ = await self.request_json(
                "GET", "key", headers=self._headers(secret), max_response_bytes=128 * 1024
            )
        except ProviderError as exc:
            if exc.code == "provider_authentication_error":
                status = CredentialValidationStatus.INVALID
            elif exc.code == "provider_authorization_error":
                status = CredentialValidationStatus.RESTRICTED
            elif exc.retryable:
                status = CredentialValidationStatus.PROVIDER_UNAVAILABLE
            else:
                status = CredentialValidationStatus.UNVERIFIED
            return CredentialValidationResult(
                provider_id=self.provider_id,
                status=status,
                message=exc.message,
            )
        if not is_json_object(payload) or not is_json_object(payload.get("data")):
            return CredentialValidationResult(
                provider_id=self.provider_id,
                status=CredentialValidationStatus.UNVERIFIED,
                message="OpenRouter key endpoint returned an unrecognized response",
            )
        data = cast(Mapping[str, Any], payload["data"])
        limit = data.get("limit")
        usage = data.get("usage")
        restricted = (
            isinstance(limit, (int, float)) and isinstance(usage, (int, float)) and usage >= limit
        )
        status = (
            CredentialValidationStatus.RESTRICTED
            if restricted
            else CredentialValidationStatus.VALID
        )
        return CredentialValidationResult(
            provider_id=self.provider_id,
            status=status,
            message="Key accepted; per-model access is separate",
        )
