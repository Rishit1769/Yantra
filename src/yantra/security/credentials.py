"""Environment and OS-keyring credential references with no plaintext fallback."""

from __future__ import annotations

import importlib
import os
import re
import sys
from collections.abc import Mapping
from typing import Protocol
from urllib.parse import unquote, urlsplit

from pydantic import SecretStr

from yantra.core.errors import (
    CredentialError,
    CredentialUnavailableError,
    SecureStorageUnavailableError,
)

_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CredentialReference:
    """Parsed reference; never contains a credential value."""

    __slots__ = ("scheme", "service", "account", "environment_name")

    def __init__(
        self,
        scheme: str,
        *,
        service: str | None = None,
        account: str | None = None,
        environment_name: str | None = None,
    ) -> None:
        self.scheme = scheme
        self.service = service
        self.account = account
        self.environment_name = environment_name

    @classmethod
    def parse(cls, value: str) -> CredentialReference:
        parsed = urlsplit(value)
        if parsed.scheme == "env":
            if parsed.query or parsed.fragment or parsed.username or parsed.password:
                raise CredentialError("environment credential reference cannot include URL options")
            name = parsed.netloc or parsed.path
            if parsed.netloc and parsed.path not in ("", "/"):
                raise CredentialError(
                    "environment credential reference must contain one variable name"
                )
            if not _ENV_NAME.fullmatch(name):
                raise CredentialError(
                    "environment credential reference has an invalid variable name"
                )
            return cls("env", environment_name=name)
        if parsed.scheme == "keyring":
            try:
                has_port = parsed.port is not None
            except ValueError as exc:
                raise CredentialError("keyring reference has an invalid port") from exc
            if parsed.query or parsed.fragment or parsed.username or parsed.password or has_port:
                raise CredentialError(
                    "keyring reference cannot include user information or query data"
                )
            service = unquote(parsed.netloc)
            account = unquote(parsed.path.lstrip("/"))
            if not service or not account or "/" in account:
                raise CredentialError("keyring reference must be keyring://service/account")
            return cls("keyring", service=service, account=account)
        raise CredentialError("credential reference scheme must be env:// or keyring://")

    def __repr__(self) -> str:
        if self.scheme == "env":
            return f"CredentialReference(env://{self.environment_name})"
        return f"CredentialReference(keyring://{self.service}/{self.account})"

    def __str__(self) -> str:
        if self.scheme == "env":
            return f"env://{self.environment_name}"
        return f"keyring://{self.service}/{self.account}"


class KeyringBackend(Protocol):
    def get_password(self, service: str, account: str) -> str | None: ...

    def set_password(self, service: str, account: str, password: str) -> None: ...

    def delete_password(self, service: str, account: str) -> None: ...


class SystemKeyringBackend:
    """Lazy adapter for the installed macOS Keychain/Windows Credential Locker backend."""

    def __init__(self) -> None:
        try:
            keyring = importlib.import_module("keyring")
            backend = keyring.get_keyring()
            module_name = type(backend).__module__.lower()
            secure_platform_backend = (sys.platform == "darwin" and "macos" in module_name) or (
                sys.platform == "win32" and "windows" in module_name
            )
            if getattr(backend, "priority", 0) <= 0 or not secure_platform_backend:
                raise SecureStorageUnavailableError(
                    "no supported secure OS keyring backend is available"
                )
            self._keyring = keyring
        except SecureStorageUnavailableError:
            raise
        except Exception as exc:
            raise SecureStorageUnavailableError(
                "install the yantra[credentials] extra and configure an OS keyring"
            ) from exc

    def get_password(self, service: str, account: str) -> str | None:
        return self._keyring.get_password(service, account)

    def set_password(self, service: str, account: str, password: str) -> None:
        self._keyring.set_password(service, account, password)

    def delete_password(self, service: str, account: str) -> None:
        self._keyring.delete_password(service, account)


class CredentialManager:
    """Resolves credentials at adapter-call time and stores secrets only in OS keyring."""

    def __init__(
        self,
        *,
        environment: Mapping[str, str] | None = None,
        keyring_backend: KeyringBackend | None = None,
    ) -> None:
        self._environment = environment
        self._keyring_backend = keyring_backend

    def resolve(self, reference: str | CredentialReference) -> SecretStr:
        ref = CredentialReference.parse(reference) if isinstance(reference, str) else reference
        if ref.scheme == "env":
            values = os.environ if self._environment is None else self._environment
            secret = values.get(ref.environment_name or "")
            if not secret:
                raise CredentialUnavailableError(
                    f"environment credential {ref.environment_name!r} is not set"
                )
            return SecretStr(secret)
        try:
            secret = self._get_backend().get_password(ref.service or "", ref.account or "")
        except SecureStorageUnavailableError:
            raise
        except Exception as exc:
            raise CredentialUnavailableError("OS keyring credential lookup failed") from exc
        if secret is None:
            raise CredentialUnavailableError(f"keyring credential {ref!s} was not found")
        return SecretStr(secret)

    def store(self, reference: str | CredentialReference, secret: SecretStr) -> None:
        """Store in OS keyring only; environment references are read-only."""
        ref = CredentialReference.parse(reference) if isinstance(reference, str) else reference
        if ref.scheme != "keyring":
            raise CredentialError("environment credential references are read-only")
        if not secret.get_secret_value():
            raise CredentialError("credential cannot be empty")
        try:
            self._get_backend().set_password(
                ref.service or "", ref.account or "", secret.get_secret_value()
            )
        except SecureStorageUnavailableError:
            raise
        except Exception as exc:
            raise CredentialError("OS keyring credential write failed") from exc

    def delete(self, reference: str | CredentialReference) -> None:
        ref = CredentialReference.parse(reference) if isinstance(reference, str) else reference
        if ref.scheme != "keyring":
            raise CredentialError("environment credentials cannot be deleted by YANTRA")
        try:
            self._get_backend().delete_password(ref.service or "", ref.account or "")
        except SecureStorageUnavailableError:
            raise
        except Exception as exc:
            raise CredentialError("OS keyring credential deletion failed") from exc

    def _get_backend(self) -> KeyringBackend:
        if self._keyring_backend is None:
            self._keyring_backend = SystemKeyringBackend()
        return self._keyring_backend
