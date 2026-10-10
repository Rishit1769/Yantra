"""Honest provider-credential validation outcomes."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class CredentialValidationStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    RESTRICTED = "restricted"
    UNVERIFIED = "unverified"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    NOT_REQUIRED = "not_required"


class CredentialValidationResult(BaseModel):
    """Credential result separated from model availability/account entitlement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str = Field(min_length=1, max_length=128)
    status: CredentialValidationStatus
    message: str = Field(max_length=1000)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    catalog_model_count: int | None = Field(default=None, ge=0)


class CredentialValidatingProvider(Protocol):
    async def validate_credentials(self, secret: SecretStr | None) -> CredentialValidationResult:
        """Validate auth without inference; report UNVERIFIED if no reliable check exists."""
        ...
