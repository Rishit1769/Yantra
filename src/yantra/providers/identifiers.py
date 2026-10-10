"""Provider/model references preserving provider-specific model IDs verbatim."""

from __future__ import annotations

import re
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from yantra.core.errors import ModelIdentifierError

_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class ModelIdentifier(BaseModel):
    """A YANTRA provider ID plus an exact provider-owned model identifier."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)

    provider_id: str = Field(pattern=_PROVIDER_ID.pattern)
    model_id: str = Field(min_length=1, max_length=512)

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse `provider/model`, splitting only at the first slash."""
        provider_id, separator, model_id = value.partition("/")
        if not separator or not provider_id or not model_id:
            raise ModelIdentifierError("model reference must have the form provider/model")
        if any(character.isspace() or ord(character) < 32 for character in model_id):
            raise ModelIdentifierError("model identifier cannot contain whitespace or controls")
        try:
            return cls(provider_id=provider_id, model_id=model_id)
        except ValueError as exc:
            raise ModelIdentifierError(
                "model reference has an invalid provider identifier"
            ) from exc

    @property
    def reference(self) -> str:
        return f"{self.provider_id}/{self.model_id}"

    def __str__(self) -> str:
        return self.reference
