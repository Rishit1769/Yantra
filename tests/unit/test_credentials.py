import pytest
from pydantic import SecretStr

from yantra.core.errors import CredentialError, CredentialUnavailableError
from yantra.security.credentials import CredentialManager, CredentialReference


class FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self.values.get((service, account))

    def set_password(self, service: str, account: str, password: str) -> None:
        self.values[(service, account)] = password

    def delete_password(self, service: str, account: str) -> None:
        del self.values[(service, account)]


def test_environment_credentials_resolve_to_redacted_secret() -> None:
    manager = CredentialManager(environment={"OPENAI_TEST_KEY": "secret-value"})
    secret = manager.resolve("env://OPENAI_TEST_KEY")
    assert secret.get_secret_value() == "secret-value"
    assert "secret-value" not in repr(secret)


def test_missing_environment_credential_fails_without_plaintext_fallback() -> None:
    manager = CredentialManager(environment={})
    with pytest.raises(CredentialUnavailableError):
        manager.resolve("env://MISSING_KEY")


def test_keyring_credentials_can_be_added_resolved_and_removed() -> None:
    keyring = FakeKeyring()
    manager = CredentialManager(environment={}, keyring_backend=keyring)
    reference = "keyring://yantra/openai"
    manager.store(reference, SecretStr("keyring-secret"))
    assert manager.resolve(reference).get_secret_value() == "keyring-secret"
    manager.delete(reference)
    with pytest.raises(CredentialUnavailableError):
        manager.resolve(reference)


def test_environment_reference_is_read_only() -> None:
    manager = CredentialManager(environment={"KEY": "value"}, keyring_backend=FakeKeyring())
    with pytest.raises(CredentialError, match="read-only"):
        manager.store("env://KEY", SecretStr("other"))
    with pytest.raises(CredentialError, match="cannot be deleted"):
        manager.delete("env://KEY")


@pytest.mark.parametrize(
    "reference",
    [
        "plaintext-secret",
        "keyring://service",
        "keyring://service/account?token=secret",
        "env://BAD-NAME",
        "env://NAME/extra",
    ],
)
def test_invalid_credential_references_are_rejected(reference: str) -> None:
    with pytest.raises(CredentialError):
        CredentialReference.parse(reference)
