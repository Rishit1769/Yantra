"""Separate OpenCode Zen and Go gateway adapters with explicit protocol resolution."""

from __future__ import annotations

from collections.abc import AsyncIterator, Generator, Mapping
from contextlib import AbstractContextManager, ExitStack, contextmanager
from typing import Any, Protocol, cast

import httpx
from pydantic import SecretStr

from yantra.core.contracts import ProviderCapabilities, merge_capabilities
from yantra.core.errors import ProviderError, ProviderProtocolError, UnsupportedCapabilityError
from yantra.providers.adapters.anthropic import AnthropicAdapter
from yantra.providers.adapters.common import is_json_object
from yantra.providers.adapters.gemini import GeminiAdapter
from yantra.providers.adapters.openai import OpenAIAdapter
from yantra.providers.adapters.openai_compatible import OpenAICompatibleAdapter
from yantra.providers.base import (
    ModelProtocol,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    StreamingModelProvider,
)
from yantra.providers.catalog import ModelCatalogEntry
from yantra.providers.http import HttpxProvider
from yantra.providers.validation import CredentialValidationResult, CredentialValidationStatus
from yantra.security.credentials import CredentialManager


class OpenCodeProtocolResolver:
    """Resolve model protocols from explicit metadata, overrides, then official doc families.

    The OpenCode `/models` endpoints currently expose model IDs but not protocol fields.
    Family rules below mirror the endpoint table in the official Zen/Go docs. They are
    protocol hints only, not an embedded model catalog; unknown IDs fail closed.
    """

    def __init__(
        self,
        provider_id: str,
        overrides: Mapping[str, ModelProtocol] | None = None,
    ) -> None:
        if provider_id not in {"opencode-zen", "opencode-go"}:
            raise ValueError("OpenCode resolver provider must be opencode-zen or opencode-go")
        self.provider_id = provider_id
        self.overrides = dict(overrides or {})

    def resolve(self, model_id: str, metadata_protocol: str | None = None) -> ModelProtocol | None:
        if metadata_protocol is not None:
            try:
                return ModelProtocol(metadata_protocol)
            except ValueError:
                return None
        if model_id in self.overrides:
            return self.overrides[model_id]

        model = model_id.lower()
        if model.startswith(("gpt-", "grok-", "muse-spark-")):
            return ModelProtocol.OPENAI_RESPONSES
        if self.provider_id == "opencode-zen":
            if (
                model.startswith("claude-")
                or model in {"qwen3.8-flash"}
                or model.startswith(("qwen3.7-", "qwen3.6-", "qwen3.5-"))
            ):
                return ModelProtocol.ANTHROPIC_MESSAGES
            if model.startswith("gemini-"):
                return ModelProtocol.GEMINI_CONTENT
            if model.startswith("jev-"):
                return ModelProtocol.SYSTEM_ONE
            if model == "qwen3.8-max" or model.startswith(
                (
                    "deepseek-",
                    "minimax-",
                    "glm-",
                    "kimi-",
                    "mistral-",
                    "big-pickle",
                    "space-bunny-",
                    "longcat-",
                    "step-",
                    "exo-",
                    "mimo-",
                    "ling-",
                    "nemotron-",
                )
            ):
                return ModelProtocol.OPENAI_CHAT
        else:
            if model == "claude-haiku-5-5" or model.startswith(
                ("minimax-", "qwen3.8-", "qwen3.7-")
            ):
                return ModelProtocol.ANTHROPIC_MESSAGES
            if model.startswith(
                (
                    "glm-",
                    "kimi-",
                    "deepseek-",
                    "longcat-",
                    "step-",
                    "mimo-",
                    "hy3",
                    "hy4",
                    "space-bunny",
                )
            ):
                return ModelProtocol.OPENAI_CHAT
        return None


class _ProtocolAdapter(StreamingModelProvider, Protocol):
    def capabilities_for(self, model_id: str) -> ProviderCapabilities: ...

    def use_credential(self, secret: SecretStr) -> AbstractContextManager[None]: ...


class _OpenCodeAdapter(HttpxProvider):
    """Shared transport with provider-specific identity, URL and credential ref."""

    def __init__(
        self,
        provider_id: str,
        base_url: str,
        *,
        credential_reference: str,
        credential_manager: CredentialManager | None = None,
        client: httpx.AsyncClient | None = None,
        protocol_overrides: Mapping[str, ModelProtocol] | None = None,
        capability_overrides: Mapping[str, ProviderCapabilities] | None = None,
        session_header_name: str | None = None,
    ) -> None:
        super().__init__(
            provider_id,
            base_url,
            credential_reference=credential_reference,
            credential_manager=credential_manager,
            trusted_hosts=frozenset({"opencode.ai"}),
            client=client,
            session_header_name=session_header_name,
        )
        self.resolver = OpenCodeProtocolResolver(provider_id, protocol_overrides)
        self._capability_overrides = dict(capability_overrides or {})
        self._protocol_adapters: dict[ModelProtocol, _ProtocolAdapter] = {
            ModelProtocol.OPENAI_RESPONSES: OpenAIAdapter(
                provider_id=provider_id,
                base_url=self.base_url,
                trusted_hosts=frozenset({"opencode.ai"}),
                credential_reference=credential_reference,
                credential_manager=self.credential_manager,
                client=self.client,
                capability_overrides=self._capability_overrides,
                session_header_name=session_header_name,
            ),
            ModelProtocol.ANTHROPIC_MESSAGES: AnthropicAdapter(
                provider_id=provider_id,
                base_url=self.base_url,
                trusted_hosts=frozenset({"opencode.ai"}),
                credential_reference=credential_reference,
                credential_manager=self.credential_manager,
                credential_header="Authorization",
                credential_scheme="Bearer",
                client=self.client,
                capability_overrides=self._capability_overrides,
                session_header_name=session_header_name,
            ),
            ModelProtocol.GEMINI_CONTENT: GeminiAdapter(
                provider_id=provider_id,
                base_url=self.base_url,
                trusted_hosts=frozenset({"opencode.ai"}),
                credential_reference=credential_reference,
                credential_manager=self.credential_manager,
                credential_header="Authorization",
                credential_scheme="Bearer",
                client=self.client,
                capability_overrides=self._capability_overrides,
                session_header_name=session_header_name,
            ),
            ModelProtocol.OPENAI_CHAT: OpenAICompatibleAdapter(
                provider_id,
                self.base_url,
                trusted_hosts=frozenset({"opencode.ai"}),
                credential_reference=credential_reference,
                credential_manager=self.credential_manager,
                client=self.client,
                capability_overrides=self._capability_overrides,
                max_output_tokens_parameter="max_tokens",
                stream_usage=True,
                session_header_name=session_header_name,
            ),
        }

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    def capabilities_for(self, model_id: str) -> ProviderCapabilities:
        protocol = self.resolver.resolve(model_id)
        if protocol is None or protocol == ModelProtocol.SYSTEM_ONE:
            return ProviderCapabilities()
        adapter = self._protocol_adapters.get(protocol)
        if adapter is None:
            return ProviderCapabilities()
        return merge_capabilities(
            adapter.capabilities_for(model_id),
            self._capability_overrides.get(model_id),
        )

    def _headers(self, secret: SecretStr | None = None) -> dict[str, str]:
        return {
            **self.request_headers(),
            "Accept": "application/json",
            **self.auth_headers(secret_override=secret),
        }

    async def list_models(
        self, *, secret: SecretStr | None = None
    ) -> tuple[ModelCatalogEntry, ...]:
        payload, _ = await self.request_json("GET", "models", headers=self._headers(secret))
        raw_models = payload.get("data")
        if not isinstance(raw_models, list):
            raise ProviderProtocolError(
                "OpenCode model catalog was malformed", provider_id=self.provider_id
            )
        entries: list[ModelCatalogEntry] = []
        for item in cast(list[Any], raw_models):
            if not is_json_object(item) or not isinstance(item.get("id"), str):
                continue
            model_id = item["id"]
            protocol = self.resolver.resolve(model_id)
            entries.append(
                ModelCatalogEntry(
                    provider_id=self.provider_id,
                    model_id=model_id,
                    display_name=item.get("name")
                    if isinstance(item.get("name"), str)
                    else model_id,
                    capabilities=self.capabilities_for(model_id),
                    protocol=protocol.value if protocol is not None else None,
                    metadata={
                        "protocol_source": "OpenCode official endpoint table snapshot"
                        if protocol is not None
                        else "unknown",
                        "protocol_supported": protocol not in (None, ModelProtocol.SYSTEM_ONE),
                    },
                )
            )
        return tuple(entries)

    async def validate_credentials(self, secret: SecretStr | None) -> CredentialValidationResult:
        if secret is None:
            return CredentialValidationResult(
                provider_id=self.provider_id,
                status=CredentialValidationStatus.UNVERIFIED,
                message="OpenCode credential was not supplied",
            )
        try:
            models = await self.list_models(secret=secret)
        except ProviderError as exc:
            status = (
                CredentialValidationStatus.INVALID
                if exc.code == "provider_authentication_error"
                else CredentialValidationStatus.PROVIDER_UNAVAILABLE
                if exc.retryable
                else CredentialValidationStatus.UNVERIFIED
            )
            return CredentialValidationResult(
                provider_id=self.provider_id,
                status=status,
                message=exc.message,
            )
        # The official catalog is public; a 200 does not prove the key was checked.
        return CredentialValidationResult(
            provider_id=self.provider_id,
            status=CredentialValidationStatus.UNVERIFIED,
            message="Public catalog does not authenticate this key; use an approved smoke test",
            catalog_model_count=len(models),
        )

    def _adapter_for(self, model_id: str) -> _ProtocolAdapter:
        protocol = self.resolver.resolve(model_id)
        if protocol == ModelProtocol.SYSTEM_ONE:
            raise UnsupportedCapabilityError(
                "OpenCode System One models are typed decision models, not text-generation models",
                provider_id=self.provider_id,
            )
        if protocol is None:
            raise ProviderProtocolError(
                f"OpenCode model {model_id!r} has no trusted protocol metadata",
                provider_id=self.provider_id,
            )
        return self._protocol_adapters[protocol]

    async def complete(self, request: ModelRequest) -> ModelResponse:
        return await self._adapter_for(request.model_id).complete(request)

    @contextmanager
    def use_credential(self, secret: SecretStr) -> Generator[None, None, None]:
        """Apply an explicit validation-smoke credential to each protocol delegate."""
        with ExitStack() as stack:
            stack.enter_context(super().use_credential(secret))
            for adapter in self._protocol_adapters.values():
                stack.enter_context(adapter.use_credential(secret))
            yield

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        adapter = self._adapter_for(request.model_id)
        async for event in adapter.stream(request):
            yield event


class OpenCodeZenAdapter(_OpenCodeAdapter):
    """OpenCode Zen curated-model gateway with protocol-specific model dispatch."""

    def __init__(
        self,
        *,
        credential_reference: str | None = "env://OPENCODE_ZEN_API_KEY",
        credential_manager: CredentialManager | None = None,
        client: httpx.AsyncClient | None = None,
        protocol_overrides: Mapping[str, ModelProtocol] | None = None,
        capability_overrides: Mapping[str, ProviderCapabilities] | None = None,
    ) -> None:
        super().__init__(
            "opencode-zen",
            "https://opencode.ai/zen/v1",
            credential_reference=credential_reference or "env://OPENCODE_ZEN_API_KEY",
            credential_manager=credential_manager,
            client=client,
            protocol_overrides=protocol_overrides,
            capability_overrides=capability_overrides,
        )


class OpenCodeGoAdapter(_OpenCodeAdapter):
    """OpenCode Go subscription gateway; independent credentials and model protocol map."""

    def __init__(
        self,
        *,
        credential_reference: str | None = "env://OPENCODE_GO_API_KEY",
        credential_manager: CredentialManager | None = None,
        client: httpx.AsyncClient | None = None,
        protocol_overrides: Mapping[str, ModelProtocol] | None = None,
        capability_overrides: Mapping[str, ProviderCapabilities] | None = None,
    ) -> None:
        super().__init__(
            "opencode-go",
            "https://opencode.ai/zen/go/v1",
            credential_reference=credential_reference or "env://OPENCODE_GO_API_KEY",
            credential_manager=credential_manager,
            client=client,
            protocol_overrides=protocol_overrides,
            capability_overrides=capability_overrides,
            session_header_name="x-opencode-session",
        )
