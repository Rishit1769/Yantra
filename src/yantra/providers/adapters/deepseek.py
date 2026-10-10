"""DeepSeek's official Chat Completions API adapter."""

from collections.abc import Mapping

import httpx

from yantra.core.contracts import ProviderCapabilities
from yantra.providers.adapters.openai_compatible import OpenAICompatibleAdapter
from yantra.providers.base import ModelRequest
from yantra.security.credentials import CredentialManager


class DeepSeekAdapter(OpenAICompatibleAdapter):
    """DeepSeek chat/reasoning API; no OpenAI endpoint parity is assumed."""

    _allowed_options = OpenAICompatibleAdapter._allowed_options | frozenset(
        {"thinking", "reasoning_effort"}
    )

    def __init__(
        self,
        *,
        credential_reference: str | None = "env://DEEPSEEK_API_KEY",
        credential_manager: CredentialManager | None = None,
        client: httpx.AsyncClient | None = None,
        capability_overrides: Mapping[str, ProviderCapabilities] | None = None,
    ) -> None:
        super().__init__(
            "deepseek",
            "https://api.deepseek.com",
            credential_reference=credential_reference,
            credential_manager=credential_manager,
            trusted_hosts=frozenset({"api.deepseek.com"}),
            client=client,
            capability_overrides=capability_overrides,
            structured_output=None,
            stream_usage=True,
        )

    def build_chat_payload(self, request: ModelRequest):
        payload = super().build_chat_payload(request)
        if "max_completion_tokens" in payload:
            payload["max_tokens"] = payload.pop("max_completion_tokens")
        if "reasoning_effort" in request.provider_options:
            payload["reasoning_effort"] = request.provider_options["reasoning_effort"]
        if "thinking" in request.provider_options:
            payload["thinking"] = request.provider_options["thinking"]
        return payload
