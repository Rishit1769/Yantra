"""Immutable agent configuration and a separate runtime-state snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_serializer, field_validator

from yantra.core.budgets import ExecutionBudget

_IDENTIFIER_PATTERN = r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        mapping = cast(dict[str, Any], value)
        frozen = MappingProxyType({key: _freeze_json(item) for key, item in mapping.items()})
        return frozen
    if isinstance(value, list):
        sequence = cast(list[Any], value)
        return tuple(_freeze_json(item) for item in sequence)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, Any], value)
        return {str(key): _thaw_json(item) for key, item in mapping.items()}
    if isinstance(value, tuple):
        sequence = cast(tuple[Any, ...], value)
        return [_thaw_json(item) for item in sequence]
    if isinstance(value, list):
        sequence = cast(list[Any], value)
        return [_thaw_json(item) for item in sequence]
    return value


class AgentConfig(BaseModel):
    """Validated immutable definition; mutable run state is stored separately."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    agent_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    system_instructions: str = Field(min_length=1, max_length=100_000)
    provider_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    model_id: str = Field(min_length=1, max_length=256)
    tool_references: tuple[str, ...] = ()
    execution_limits: ExecutionBudget = Field(default_factory=ExecutionBudget)
    metadata: Mapping[str, JsonValue] = Field(default_factory=dict)

    @field_validator("tool_references")
    @classmethod
    def tool_references_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("tool references must be non-empty")
        if len(values) != len(set(values)):
            raise ValueError("tool references must be unique")
        return values

    @field_validator("metadata")
    @classmethod
    def metadata_is_deeply_immutable(
        cls, value: Mapping[str, JsonValue]
    ) -> Mapping[str, JsonValue]:
        return cast(Mapping[str, JsonValue], _freeze_json(dict(value)))

    @field_serializer("metadata")
    def serialize_metadata(self, value: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], _thaw_json(value))
