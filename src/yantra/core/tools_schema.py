"""Provider-neutral representation of a tool schema."""

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ProviderToolSchema(BaseModel):
    """Portable tool description sent to capable model providers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(max_length=2000)
    parameters: dict[str, JsonValue]
