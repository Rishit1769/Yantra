"""Typed tool metadata; registration does not authorize or execute a tool."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError

from yantra.core.errors import ToolValidationError
from yantra.core.tools_schema import ProviderToolSchema
from yantra.tools.execution import ToolExecutionBoundaryMode
from yantra.tools.policy import PermissionScope, ToolRiskLevel


class ExecutionMode(StrEnum):
    SYNC = "sync"
    ASYNC = "async"


class SideEffect(StrEnum):
    READ_ONLY = "read_only"
    REVERSIBLE = "reversible"
    IRREVERSIBLE = "irreversible"
    UNKNOWN = "unknown"


class ToolDefinition(BaseModel):
    """Registered callable metadata with explicit schemas and required scopes."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
    )

    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
    description: str = Field(default="", max_length=2000)
    input_model: type[BaseModel]
    output_model: type[BaseModel] | None = None
    executor: Callable[..., Any] | None = None
    execution_mode: ExecutionMode = ExecutionMode.SYNC
    execution_boundary: ToolExecutionBoundaryMode = ToolExecutionBoundaryMode.IN_PROCESS
    worker_handler_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_.-]{0,127}$")
    permission_scopes: frozenset[PermissionScope] = frozenset()
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    side_effect: SideEffect = SideEffect.UNKNOWN
    timeout_seconds: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @field_validator("executor")
    @classmethod
    def executor_is_callable(cls, value: Callable[..., Any] | None) -> Callable[..., Any] | None:
        if value is not None and not callable(value):
            raise ValueError("executor must be callable")
        return value

    @model_validator(mode="after")
    def schemas_and_execution_mode_are_consistent(self) -> ToolDefinition:
        if self.execution_boundary == ToolExecutionBoundaryMode.IN_PROCESS:
            if self.executor is None or self.worker_handler_id is not None:
                raise ValueError("in-process tools require an executor and no worker handler ID")
            call_method = type(self.executor).__call__
            is_async = inspect.iscoroutinefunction(self.executor) or inspect.iscoroutinefunction(
                call_method
            )
            if (self.execution_mode == ExecutionMode.ASYNC) != is_async:
                raise ValueError(
                    "execution_mode must match the executor's sync/async callable type"
                )
        elif self.executor is not None or self.worker_handler_id is None:
            raise ValueError("subprocess tools require a worker handler ID and no local executor")
        self.input_model.model_json_schema()
        if self.output_model is not None:
            self.output_model.model_json_schema()
        return self

    def validate_input(self, arguments: dict[str, JsonValue]) -> BaseModel:
        """Validate untrusted input while avoiding echoing rejected values."""
        try:
            return self.input_model.model_validate(arguments)
        except PydanticValidationError as exc:
            raise ToolValidationError(
                f"arguments for tool {self.name!r} failed schema validation"
            ) from exc

    def validate_output(self, value: Any) -> BaseModel | Any:
        """Validate output where an output model is declared."""
        if self.output_model is None:
            return value
        try:
            return self.output_model.model_validate(value)
        except PydanticValidationError as exc:
            raise ToolValidationError(
                f"output from tool {self.name!r} failed schema validation"
            ) from exc

    def provider_schema(self) -> ProviderToolSchema:
        """Export the provider-neutral callable schema, excluding permission grants."""
        schema = self.input_model.model_json_schema()
        return ProviderToolSchema(name=self.name, description=self.description, parameters=schema)
