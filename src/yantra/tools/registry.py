"""In-process deterministic tool registry."""

from pydantic import ValidationError as PydanticValidationError

from yantra.core.errors import (
    DuplicateToolError,
    InvalidToolDefinitionError,
    ToolNotFoundError,
)
from yantra.core.tools_schema import ProviderToolSchema
from yantra.tools.base import ToolDefinition


class ToolRegistry:
    """A local registry; callers still must authorize each invocation separately."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Validate and register one tool, rejecting duplicate names."""
        if tool.name in self._tools:
            raise DuplicateToolError(f"tool {tool.name!r} is already registered")
        try:
            tool.input_model.model_json_schema()
            if tool.output_model is not None:
                tool.output_model.model_json_schema()
            tool.provider_schema()
        except (PydanticValidationError, TypeError, ValueError) as exc:
            raise InvalidToolDefinitionError(f"tool {tool.name!r} has an invalid schema") from exc
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        """Return a registered tool by exact name."""
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(f"tool {name!r} is not registered") from exc

    def list(self) -> tuple[ToolDefinition, ...]:
        """List definitions in stable name-sorted order."""
        return tuple(self._tools[name] for name in sorted(self._tools))

    def unregister(self, name: str) -> ToolDefinition:
        """Remove and return a registered tool by exact name."""
        try:
            return self._tools.pop(name)
        except KeyError as exc:
            raise ToolNotFoundError(f"tool {name!r} is not registered") from exc

    def export_provider_schemas(self) -> tuple[ProviderToolSchema, ...]:
        """Export stable schemas without permission metadata or execution callables."""
        return tuple(tool.provider_schema() for tool in self.list())
