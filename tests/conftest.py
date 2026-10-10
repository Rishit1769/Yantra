import pytest
from pydantic import BaseModel, Field

from yantra.tools.base import ExecutionMode, SideEffect, ToolDefinition


class EchoInput(BaseModel):
    text: str = Field(min_length=1)


class EchoOutput(BaseModel):
    text: str


@pytest.fixture
def echo_tool() -> ToolDefinition:
    def echo(arguments: EchoInput) -> EchoOutput:
        return EchoOutput(text=arguments.text)

    return ToolDefinition(
        name="demo.echo",
        description="Return supplied text",
        input_model=EchoInput,
        output_model=EchoOutput,
        executor=echo,
        execution_mode=ExecutionMode.SYNC,
        permission_scopes=frozenset({"demo:read"}),
        side_effect=SideEffect.READ_ONLY,
    )
