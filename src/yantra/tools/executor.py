"""Controlled in-process execution of registered tools."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import JsonValue, TypeAdapter

from yantra.core.errors import ToolNotFoundError, ToolValidationError
from yantra.core.messages import ToolCall, ToolResult
from yantra.tools.base import ExecutionMode, ToolDefinition
from yantra.tools.registry import ToolRegistry

_JSON_VALUE = TypeAdapter(JsonValue)


class ToolExecutor:
    """Validate and invoke only tools explicitly present in a registry.

    Tool failures are returned as structured observations so the model can
    recover or explain the failure. Cancellation is deliberately not caught.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def execute(self, call: ToolCall, *, timeout_seconds: float | None = None) -> ToolResult:
        try:
            definition = self.registry.get(call.name)
        except ToolNotFoundError:
            return self._failure(call, "tool_not_found", f"tool {call.name!r} is not registered")

        try:
            arguments = definition.validate_input(call.arguments)
        except ToolValidationError:
            return self._failure(
                call, "invalid_arguments", "tool arguments failed schema validation"
            )

        effective_timeout = timeout_seconds
        if definition.timeout_seconds is not None:
            effective_timeout = (
                definition.timeout_seconds
                if effective_timeout is None
                else min(effective_timeout, definition.timeout_seconds)
            )

        try:
            operation = self._invoke(definition, arguments)
            value = (
                await operation
                if effective_timeout is None
                else await asyncio.wait_for(operation, timeout=effective_timeout)
            )
            validated = definition.validate_output(value)
            if hasattr(validated, "model_dump"):
                value = validated.model_dump(mode="json")
            else:
                value = validated
            result = _JSON_VALUE.validate_python(value)
        except TimeoutError:
            return self._failure(call, "tool_timeout", "tool execution exceeded its timeout")
        except ToolValidationError:
            return self._failure(call, "invalid_output", "tool output failed schema validation")
        except Exception:
            return self._failure(call, "tool_exception", "tool execution failed")
        return ToolResult(call_id=call.call_id, name=call.name, result=result)

    async def _invoke(self, definition: ToolDefinition, arguments: Any) -> Any:
        if definition.execution_mode == ExecutionMode.ASYNC:
            return await definition.executor(arguments)
        return await asyncio.to_thread(definition.executor, arguments)

    @staticmethod
    def _failure(call: ToolCall, code: str, message: str) -> ToolResult:
        return ToolResult(
            call_id=call.call_id,
            name=call.name,
            result={"error_code": code, "message": message},
            is_error=True,
        )
