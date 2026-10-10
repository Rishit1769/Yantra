import pytest
from pydantic import BaseModel

from yantra.core.errors import (
    DuplicateToolError,
    ToolNotFoundError,
    ToolValidationError,
)
from yantra.tools.base import ExecutionMode, ToolDefinition
from yantra.tools.registry import ToolRegistry


def test_registry_registers_retrieves_lists_and_unregisters(echo_tool: ToolDefinition) -> None:
    registry = ToolRegistry()
    registry.register(echo_tool)

    assert registry.get("demo.echo") is echo_tool
    assert registry.list() == (echo_tool,)
    assert registry.unregister("demo.echo") is echo_tool
    assert registry.list() == ()


def test_registry_rejects_duplicate_tool_name(echo_tool: ToolDefinition) -> None:
    registry = ToolRegistry()
    registry.register(echo_tool)
    with pytest.raises(DuplicateToolError):
        registry.register(echo_tool)


def test_registry_unknown_tool_has_typed_error() -> None:
    with pytest.raises(ToolNotFoundError):
        ToolRegistry().get("missing")
    with pytest.raises(ToolNotFoundError):
        ToolRegistry().unregister("missing")


def test_registry_exports_sorted_provider_schemas(echo_tool: ToolDefinition) -> None:
    registry = ToolRegistry()
    another = echo_tool.model_copy(update={"name": "demo.alpha"})
    registry.register(echo_tool)
    registry.register(another)

    exported = registry.export_provider_schemas()

    assert [schema.name for schema in exported] == ["demo.alpha", "demo.echo"]
    assert "properties" in exported[0].parameters
    assert "permission_scopes" not in exported[0].model_dump_json()


def test_tool_input_validation_does_not_echo_untrusted_values(echo_tool: ToolDefinition) -> None:
    with pytest.raises(ToolValidationError) as error:
        echo_tool.validate_input({"text": "", "password": "should-not-leak"})
    assert "should-not-leak" not in str(error.value)


def test_tool_output_validation(echo_tool: ToolDefinition) -> None:
    output = echo_tool.validate_output({"text": "hello"})
    assert output.text == "hello"
    with pytest.raises(ToolValidationError):
        echo_tool.validate_output({"unexpected": "value"})


def test_tool_definition_rejects_async_mode_mismatch(echo_tool: ToolDefinition) -> None:
    with pytest.raises(ValueError, match="execution_mode"):
        ToolDefinition(
            name="demo.bad",
            input_model=echo_tool.input_model,
            executor=echo_tool.executor,
            execution_mode=ExecutionMode.ASYNC,
        )


def test_tool_definition_accepts_async_callable() -> None:
    class AsyncInput(BaseModel):
        value: str

    async def async_echo(arguments: AsyncInput) -> AsyncInput:
        return arguments

    definition = ToolDefinition(
        name="demo.async",
        input_model=AsyncInput,
        executor=async_echo,
        execution_mode=ExecutionMode.ASYNC,
    )
    assert definition.execution_mode == ExecutionMode.ASYNC


def test_registry_schema_contains_no_callable_or_permissions(echo_tool: ToolDefinition) -> None:
    schema = echo_tool.provider_schema().model_dump()
    assert set(schema) == {"name", "description", "parameters"}
