"""Controlled in-process execution of registered tools."""

from __future__ import annotations

from threading import Lock
from uuid import UUID

from pydantic import JsonValue, TypeAdapter

from yantra.core.errors import ToolNotFoundError, ToolValidationError
from yantra.core.messages import ToolCall, ToolResult
from yantra.tools.base import ToolDefinition
from yantra.tools.execution import (
    ExecutionAuthorization,
    ExecutionBoundary,
    ExecutionLimits,
    ExecutionResultStatus,
    InProcessExecutionBoundary,
    ToolExecutionBoundaryMode,
    canonical_json_digest,
    verify_execution_authorization,
)
from yantra.tools.policy import PolicyDecision
from yantra.tools.registry import ToolRegistry
from yantra.tools.subprocess_boundary import SubprocessExecutionBoundary

_JSON_VALUE = TypeAdapter(JsonValue)


class ToolExecutor:
    """Validate and invoke only tools explicitly present in a registry.

    Tool failures are returned as structured observations so the model can
    recover or explain the failure. Cancellation is deliberately not caught.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        subprocess_boundary: SubprocessExecutionBoundary | None = None,
        execution_limits: ExecutionLimits | None = None,
    ) -> None:
        self.registry = registry
        self.__consumed_authorizations: set[UUID] = set()
        self.__authorization_lock = Lock()
        self.in_process_boundary: ExecutionBoundary = InProcessExecutionBoundary()
        self.subprocess_boundary = subprocess_boundary or SubprocessExecutionBoundary(
            execution_limits or ExecutionLimits()
        )

    def _verify_authorization(
        self,
        authorization: ExecutionAuthorization,
        *,
        run_id: UUID,
        call: ToolCall,
        definition: ToolDefinition,
    ) -> bool:
        del authorization, run_id, call, definition
        return False

    async def execute(
        self,
        call: ToolCall,
        *,
        authorization: PolicyDecision | None = None,
        execution_authorization: ExecutionAuthorization | None = None,
        run_id: UUID | None = None,
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

        if (
            execution_authorization is None
            or run_id is None
            or not self._verify_authorization(
                execution_authorization,
                run_id=run_id,
                call=call,
                definition=definition,
            )
            or (authorization is not None and authorization != execution_authorization.decision)
        ):
            return self.failure(call, "tool_not_permitted", "tool is not authorized for this run")
        with self.__authorization_lock:
            if execution_authorization.invocation_id in self.__consumed_authorizations:
                return self.failure(
                    call, "tool_not_permitted", "execution authority was already used"
                )
            self.__consumed_authorizations.add(execution_authorization.invocation_id)

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

        if definition.execution_boundary == ToolExecutionBoundaryMode.SUBPROCESS:
            boundary: ExecutionBoundary = self.subprocess_boundary
        else:
            boundary = self.in_process_boundary

        try:
            execution = await boundary.execute(
                definition,
                arguments,
                invocation_id=execution_authorization.invocation_id,
                timeout_seconds=effective_timeout,
            )
            if execution.status != ExecutionResultStatus.SUCCEEDED:
                return self._execution_failure(call, execution.status)
            value = execution.value
            validated = definition.validate_output(value)
            if hasattr(validated, "model_dump"):
                value = validated.model_dump(mode="json")
            else:
                value = validated
            result = _JSON_VALUE.validate_python(value)
        except ToolValidationError:
            return self.failure(call, "invalid_output", "tool output failed schema validation")
        except Exception:
            return self.failure(call, "tool_exception", "tool execution failed")
        return ToolResult(call_id=call.call_id, name=call.name, result=result)

    @staticmethod
    def _execution_failure(call: ToolCall, status: ExecutionResultStatus) -> ToolResult:
        errors = {
            ExecutionResultStatus.TIMEOUT: ("tool_timeout", "tool execution exceeded its timeout"),
            ExecutionResultStatus.CANCELLED: ("tool_cancelled", "tool execution was cancelled"),
            ExecutionResultStatus.STARTUP_FAILURE: (
                "tool_worker_startup_failed",
                "tool worker could not be started",
            ),
            ExecutionResultStatus.PROTOCOL_FAILURE: (
                "tool_worker_protocol_error",
                "tool worker returned an invalid response",
            ),
            ExecutionResultStatus.UNEXPECTED_EXIT: (
                "tool_worker_failed",
                "tool worker exited unexpectedly",
            ),
            ExecutionResultStatus.REQUEST_TOO_LARGE: (
                "tool_request_too_large",
                "tool invocation exceeds the worker request limit",
            ),
            ExecutionResultStatus.RESPONSE_TOO_LARGE: (
                "tool_response_too_large",
                "tool worker response exceeds the configured limit",
            ),
            ExecutionResultStatus.WORKER_LIMIT: (
                "tool_worker_limit",
                "maximum concurrent worker capacity was reached",
            ),
            ExecutionResultStatus.TOOL_ERROR: ("tool_exception", "tool execution failed"),
        }
        code, message = errors.get(status, ("tool_worker_failed", "tool worker execution failed"))
        return ToolExecutor.failure(call, code, message)

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


class _EngineToolExecutor(ToolExecutor):  # pyright: ignore[reportUnusedClass]
    """Executor with an engine-provided verifier key; intentionally not public API."""

    def __init__(
        self,
        registry: ToolRegistry,
        verification_key: bytes,
        *,
        subprocess_boundary: SubprocessExecutionBoundary | None = None,
        execution_limits: ExecutionLimits | None = None,
    ) -> None:
        super().__init__(
            registry,
            subprocess_boundary=subprocess_boundary,
            execution_limits=execution_limits,
        )
        self.__verification_key = verification_key

    def _verify_authorization(
        self,
        authorization: ExecutionAuthorization,
        *,
        run_id: UUID,
        call: ToolCall,
        definition: ToolDefinition,
    ) -> bool:
        return verify_execution_authorization(
            authorization,
            self.__verification_key,
            run_id=run_id,
            call_id=call.call_id,
            definition=definition,
            arguments_sha256=canonical_json_digest(call.arguments),
        )
