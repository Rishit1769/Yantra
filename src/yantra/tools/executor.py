"""Controlled in-process execution of registered tools."""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from pydantic import JsonValue, TypeAdapter

from yantra.core.errors import ToolNotFoundError, ToolValidationError
from yantra.core.messages import ToolCall, ToolResult
from yantra.tools.base import ExecutionMode, ToolDefinition
from yantra.tools.policy import PolicyDecision, PolicyEffect
from yantra.tools.registry import ToolRegistry

_JSON_VALUE = TypeAdapter(JsonValue)


class _ExecutionCapability:
    """Opaque executor-instance-bound authority minted only by the engine path."""

    __slots__ = ("_seal", "call_id", "name", "arguments_sha256", "definition", "approved")

    def __init__(
        self,
        seal: object,
        call: ToolCall,
        definition: ToolDefinition,
        *,
        approved: bool,
    ) -> None:
        self._seal = seal
        self.call_id = call.call_id
        self.name = call.name
        self.arguments_sha256 = _arguments_digest(call.arguments)
        self.definition = definition
        self.approved = approved

    def matches(self, seal: object, call: ToolCall, definition: ToolDefinition) -> bool:
        return (
            self._seal is seal
            and self.call_id == call.call_id
            and self.name == call.name
            and self.definition is definition
            and self.arguments_sha256 == _arguments_digest(call.arguments)
        )


def _arguments_digest(arguments: object) -> str:
    encoded = json.dumps(
        arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8", errors="strict")).hexdigest()


class ToolExecutor:
    """Validate and invoke only tools explicitly present in a registry.

    Tool failures are returned as structured observations so the model can
    recover or explain the failure. Cancellation is deliberately not caught.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self.__capability_seal = object()

    def _issue_capability(
        self,
        call: ToolCall,
        definition: ToolDefinition,
        *,
        approved: bool,
    ) -> _ExecutionCapability:
        return _ExecutionCapability(self.__capability_seal, call, definition, approved=approved)

    async def execute(
        self,
        call: ToolCall,
        *,
        authorization: PolicyDecision | None = None,
        _capability: _ExecutionCapability | None = None,
        expected_definition: ToolDefinition | None = None,
        timeout_seconds: float | None = None,
    ) -> ToolResult:
        try:
            definition = self.registry.get(call.name)
        except ToolNotFoundError:
            return self.failure(call, "tool_not_found", f"tool {call.name!r} is not registered")

        if expected_definition is not None and definition is not expected_definition:
            return self.failure(
                call, "tool_not_permitted", "tool configuration changed during authorization"
            )

        if not isinstance(_capability, _ExecutionCapability) or not _capability.matches(
            self.__capability_seal, call, definition
        ):
            return self.failure(call, "tool_not_permitted", "tool is not authorized for this run")
        if authorization is None or type(authorization) is not PolicyDecision:
            return self.failure(call, "tool_not_permitted", "tool is not authorized for this run")
        if authorization.effect != PolicyEffect.ALLOW and not (
            authorization.effect == PolicyEffect.APPROVAL_REQUIRED and _capability.approved
        ):
            if authorization.effect == PolicyEffect.APPROVAL_REQUIRED:
                return self.policy_failure(
                    call,
                    "tool_approval_required",
                    "tool execution requires approval, which is unavailable",
                    authorization,
                )
            return self.policy_failure(
                call,
                "tool_not_permitted",
                "tool is not authorized for this run",
                authorization,
            )

        try:
            arguments = definition.validate_input(call.arguments)
        except ToolValidationError:
            return self.failure(
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
            return self.failure(call, "tool_timeout", "tool execution exceeded its timeout")
        except ToolValidationError:
            return self.failure(call, "invalid_output", "tool output failed schema validation")
        except Exception:
            return self.failure(call, "tool_exception", "tool execution failed")
        return ToolResult(call_id=call.call_id, name=call.name, result=result)

    async def _invoke(self, definition: ToolDefinition, arguments: Any) -> Any:
        if definition.execution_mode == ExecutionMode.ASYNC:
            return await definition.executor(arguments)
        return await asyncio.to_thread(definition.executor, arguments)

    @staticmethod
    def failure(call: ToolCall, code: str, message: str) -> ToolResult:
        return ToolResult(
            call_id=call.call_id,
            name=call.name,
            result={"error_code": code, "message": message},
            is_error=True,
        )

    @staticmethod
    def policy_failure(
        call: ToolCall, code: str, message: str, decision: PolicyDecision
    ) -> ToolResult:
        return ToolResult(
            call_id=call.call_id,
            name=call.name,
            result={"error_code": code, "message": message, "policy_reason": decision.reason},
            is_error=True,
        )
