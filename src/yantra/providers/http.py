"""Bounded HTTPX transport shared by remote provider adapters."""

from __future__ import annotations

import asyncio
import ipaddress
import json
from collections.abc import AsyncGenerator, Generator, Mapping
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, cast
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from yantra.core.errors import (
    CredentialUnavailableError,
    ProviderAuthenticationError,
    ProviderAuthorizationError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderModelUnavailableError,
    ProviderNetworkError,
    ProviderProtocolError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from yantra.providers.base import ModelRequest
from yantra.security.credentials import CredentialManager

DEFAULT_MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def validate_endpoint(
    base_url: str,
    *,
    trusted_hosts: frozenset[str] = frozenset(),
    allow_private_network: bool = False,
) -> str:
    """Validate adapter endpoints and prohibit URL-embedded credentials/query secrets."""
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("provider base URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("provider base URL cannot contain user info, query, or fragment")
    host = parsed.hostname.lower().rstrip(".")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    loopback = (
        host == "localhost"
        or host.endswith(".localhost")
        or bool(address is not None and address.is_loopback)
    )
    if address is not None and not address.is_global and not loopback:
        if not allow_private_network or host not in trusted_hosts:
            raise ValueError("private and special-use IP endpoints require explicit trust")
    if parsed.scheme == "http" and not loopback:
        raise ValueError("plain HTTP is permitted only for loopback endpoints")
    if not loopback and host not in trusted_hosts and trusted_hosts:
        raise ValueError("provider endpoint host is not in the configured trust allowlist")
    if not loopback and not trusted_hosts:
        # Built-in adapters supply a fixed official host through this allowlist.
        raise ValueError("remote provider endpoint must be explicitly trusted")
    return base_url.rstrip("/")


class HttpxProvider:
    """Base class for adapters with bounded responses, disabled redirects, and typed failures."""

    def __init__(
        self,
        provider_id: str,
        base_url: str,
        *,
        credential_reference: str | None,
        credential_manager: CredentialManager | None = None,
        trusted_hosts: frozenset[str] = frozenset(),
        allow_private_network: bool = False,
        client: httpx.AsyncClient | None = None,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        session_header_name: str | None = None,
    ) -> None:
        if not provider_id:
            raise ValueError("provider_id must be non-empty")
        if max_response_bytes < 1024:
            raise ValueError("max_response_bytes must be at least 1024")
        self._provider_id = provider_id
        self.base_url = validate_endpoint(
            base_url,
            trusted_hosts=trusted_hosts,
            allow_private_network=allow_private_network,
        )
        self.base_url = self.base_url.rstrip("/") + "/"
        self.credential_reference = credential_reference
        self.credential_manager = credential_manager or CredentialManager()
        self._max_response_bytes = max_response_bytes
        self._session_header_name = session_header_name
        self._credential_override: ContextVar[SecretStr | None] = ContextVar(
            f"yantra_credential_{id(self)}", default=None
        )
        self.user_agent = "yantra/0.2.0"
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            base_url=self.base_url,
            headers={"User-Agent": self.user_agent},
            follow_redirects=False,
            trust_env=False,
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    @property
    def provider_id(self) -> str:
        return self._provider_id

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def __aenter__(self) -> HttpxProvider:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    def auth_headers(
        self,
        *,
        header_name: str = "Authorization",
        scheme: str = "Bearer",
        secret_override: SecretStr | None = None,
    ) -> dict[str, str]:
        if secret_override is None:
            secret_override = self._credential_override.get()
        if secret_override is not None:
            credential = secret_override.get_secret_value()
        elif self.credential_reference is None:
            return {}
        else:
            try:
                credential = self.credential_manager.resolve(
                    self.credential_reference
                ).get_secret_value()
            except CredentialUnavailableError as exc:
                raise ProviderAuthenticationError(
                    "provider credential could not be resolved", provider_id=self.provider_id
                ) from exc
        value = f"{scheme} {credential}" if scheme else credential
        return {header_name: value}

    @contextmanager
    def use_credential(self, secret: SecretStr) -> Generator[None, None, None]:
        """Temporarily bind a credential to this async task for an explicit smoke test."""
        token: Token[SecretStr | None] = self._credential_override.set(secret)
        try:
            yield
        finally:
            self._credential_override.reset(token)

    def request_headers(self, request: ModelRequest | None = None) -> dict[str, str]:
        """Return safe common headers; OpenCode Go session IDs are explicit metadata only."""
        result = {"User-Agent": self.user_agent}
        if request is not None and self._session_header_name is not None:
            session_id = request.metadata.get("session_id")
            if isinstance(session_id, str) and session_id:
                result[self._session_header_name] = session_id
        return result

    def timeout(self, seconds: float) -> httpx.Timeout:
        return httpx.Timeout(seconds, connect=min(seconds, 10.0))

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        timeout_seconds: float = 30.0,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        json_body: object | None = None,
        max_response_bytes: int | None = None,
    ) -> tuple[dict[str, Any], httpx.Headers]:
        limit = max_response_bytes or self._max_response_bytes
        try:
            async with asyncio.timeout(timeout_seconds):
                async with self.client.stream(
                    method,
                    path,
                    headers=dict(headers or {}),
                    params=params,
                    json=json_body,
                    timeout=self.timeout(timeout_seconds),
                ) as response:
                    body = await self._read_limited(response, limit)
                    if response.status_code < 200 or response.status_code >= 300:
                        raise self._http_error(response.status_code, response.headers, body)
                    try:
                        parsed_raw: Any = json.loads(body) if body else {}
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise ProviderProtocolError(
                            "provider returned invalid JSON", provider_id=self.provider_id
                        ) from exc
                    if not isinstance(parsed_raw, dict):
                        raise ProviderProtocolError(
                            "provider returned an unexpected JSON root",
                            provider_id=self.provider_id,
                        )
                    parsed = cast(dict[str, Any], parsed_raw)
                    return parsed, response.headers
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                "provider request exceeded its deadline",
                provider_id=self.provider_id,
                retryable=True,
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                "provider request timed out", provider_id=self.provider_id, retryable=True
            ) from exc
        except httpx.NetworkError as exc:
            raise ProviderNetworkError(
                "provider network request failed", provider_id=self.provider_id, retryable=True
            ) from exc
        except httpx.InvalidURL as exc:
            raise ProviderInvalidRequestError(
                "provider request URL is invalid", provider_id=self.provider_id
            ) from exc

    @asynccontextmanager
    async def stream_response(
        self,
        method: str,
        path: str,
        *,
        timeout_seconds: float,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        json_body: object | None = None,
    ) -> AsyncGenerator[httpx.Response, None]:
        """Open a streaming response with redirect denial and typed transport errors."""
        try:
            async with asyncio.timeout(timeout_seconds):
                async with self.client.stream(
                    method,
                    path,
                    headers=dict(headers or {}),
                    params=params,
                    json=json_body,
                    timeout=self.timeout(timeout_seconds),
                ) as response:
                    if response.status_code < 200 or response.status_code >= 300:
                        body = await self._read_limited(
                            response, min(self._max_response_bytes, 64 * 1024)
                        )
                        raise self._http_error(response.status_code, response.headers, body)
                    yield response
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                "provider stream exceeded its deadline",
                provider_id=self.provider_id,
                retryable=True,
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                "provider stream timed out", provider_id=self.provider_id, retryable=True
            ) from exc
        except httpx.NetworkError as exc:
            raise ProviderNetworkError(
                "provider stream failed at the network layer",
                provider_id=self.provider_id,
                retryable=True,
            ) from exc

    async def _read_limited(self, response: httpx.Response, limit: int) -> bytes:
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > limit:
                    raise ProviderProtocolError(
                        "provider response exceeds configured size limit",
                        provider_id=self.provider_id,
                    )
            except ValueError:
                pass
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > limit:
                raise ProviderProtocolError(
                    "provider response exceeds configured size limit", provider_id=self.provider_id
                )
            chunks.append(chunk)
        return b"".join(chunks)

    def _http_error(self, status_code: int, headers: httpx.Headers, body: bytes) -> ProviderError:
        # Never include arbitrary upstream response bodies in public errors.
        if status_code == 401:
            error = ProviderAuthenticationError(
                "provider rejected credentials", provider_id=self.provider_id
            )
        elif status_code == 403:
            error = ProviderAuthorizationError(
                "provider denied access", provider_id=self.provider_id
            )
        elif status_code == 402:
            error = ProviderQuotaError(
                "provider account has insufficient quota", provider_id=self.provider_id
            )
        elif status_code == 404:
            error = ProviderModelUnavailableError(
                "provider endpoint or model is unavailable", provider_id=self.provider_id
            )
        elif status_code == 429:
            error = ProviderRateLimitError(
                "provider rate or quota limit was reached",
                provider_id=self.provider_id,
                retry_after_seconds=parse_retry_after(headers.get("retry-after")),
            )
        elif status_code in (408, 504):
            error = ProviderTimeoutError(
                "provider request timed out", provider_id=self.provider_id, retryable=True
            )
        elif status_code in (400, 413, 422):
            error = ProviderInvalidRequestError(
                f"provider rejected the request (HTTP {status_code})", provider_id=self.provider_id
            )
        elif status_code >= 500 or status_code == 425:
            error = ProviderUnavailableError(
                f"provider is unavailable (HTTP {status_code})",
                provider_id=self.provider_id,
                retryable=True,
            )
        else:
            error = ProviderError(
                f"provider returned HTTP {status_code}", provider_id=self.provider_id
            )
        return error.set_http_diagnostics(
            status=status_code,
            provider_code=_provider_error_code(body),
            request_id=_provider_request_id(headers),
        )


def parse_retry_after(value: str | None) -> float | None:
    """Parse Retry-After seconds or HTTP date, clamped to a useful bounded value."""
    if value is None:
        return None
    try:
        return min(max(float(value), 0.0), 300.0)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            return min(max((retry_at - datetime.now(UTC)).total_seconds(), 0.0), 300.0)
        except (TypeError, ValueError, OverflowError):
            return None


def _provider_error_code(body: bytes) -> str | None:
    try:
        payload_raw: Any = json.loads(body) if body else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload_raw, dict):
        return None
    payload = cast(dict[str, Any], payload_raw)
    error_raw = payload.get("error")
    if not isinstance(error_raw, dict):
        return None
    error = cast(dict[str, Any], error_raw)
    for key in ("code", "type"):
        value = error.get(key)
        if isinstance(value, str):
            return value
    return None


def _provider_request_id(headers: httpx.Headers) -> str | None:
    for name in ("x-request-id", "request-id", "x-correlation-id"):
        value = headers.get(name)
        if value is not None:
            return value
    return None
