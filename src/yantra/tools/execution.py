"""Execution-boundary contracts and signed, single-use authorization tokens."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictBool

from yantra.tools.policy import PolicyDecision, PolicyEffect

if TYPE_CHECKING:
    from yantra.tools.base import ToolDefinition


class ToolExecutionBoundaryMode(StrEnum):
    IN_PROCESS = "in_process"
    SUBPROCESS = "subprocess"


class ExecutionResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    TOOL_ERROR = "tool_error"
    STARTUP_FAILURE = "startup_failure"
    PROTOCOL_FAILURE = "protocol_failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNEXPECTED_EXIT = "unexpected_exit"
    REQUEST_TOO_LARGE = "request_too_large"
    RESPONSE_TOO_LARGE = "response_too_large"
    WORKER_LIMIT = "worker_limit"


class ExecutionResult(BaseModel):
    """Normalized boundary result; callers must inspect status before using value."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    status: ExecutionResultStatus
    value: Any = None
    error_category: str | None = None


class ExecutionRequest(BaseModel):
    """Versioned JSON-only worker input. It carries no authorization or approval data."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    protocol_version: int = Field(ge=1, le=1)
    invocation_id: UUID
    handler_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")
    arguments: dict[str, JsonValue]


class ExecutionResponse(BaseModel):
    """Versioned JSON-only worker response, validated by the parent."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    protocol_version: int = Field(ge=1, le=1)
    invocation_id: UUID
    status: str = Field(pattern=r"^(succeeded|tool_error)$")
    value: JsonValue | None = None
    error_category: str | None = Field(default=None, max_length=64)


class ExecutionLimits(BaseModel):
    """Conservative protocol and lifecycle limits; not OS resource controls."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_request_bytes: int = Field(default=64 * 1024, ge=1024, le=1024 * 1024)
    max_response_bytes: int = Field(default=64 * 1024, ge=1024, le=1024 * 1024)
    max_diagnostic_bytes: int = Field(default=4096, ge=256, le=64 * 1024)
    max_execution_seconds: float = Field(default=10.0, gt=0, le=300, allow_inf_nan=False)
    termination_grace_seconds: float = Field(default=0.25, gt=0, le=5, allow_inf_nan=False)
    max_concurrent_workers: int = Field(default=4, ge=1, le=64)


class ExecutionBoundary(Protocol):
    """Runtime contract implemented by in-process and subprocess dispatchers."""

    async def execute(
        self,
        definition: ToolDefinition,
        arguments: Any,
        *,
        invocation_id: UUID,
        timeout_seconds: float | None,
    ) -> ExecutionResult: ...


class InProcessExecutionBoundary:
    """Run a trusted registered Python handler in the current process."""

    async def execute(
        self,
        definition: ToolDefinition,
        arguments: Any,
        *,
        invocation_id: UUID,
        timeout_seconds: float | None,
    ) -> ExecutionResult:
        del invocation_id
        handler = definition.executor
        if handler is None:
            return ExecutionResult(status=ExecutionResultStatus.STARTUP_FAILURE)

        async def invoke() -> Any:
            if definition.execution_mode.value == "async":
                return await handler(arguments)
            return await asyncio.to_thread(handler, arguments)

        try:
            value = (
                await invoke()
                if timeout_seconds is None
                else await asyncio.wait_for(invoke(), timeout=timeout_seconds)
            )
        except TimeoutError:
            return ExecutionResult(status=ExecutionResultStatus.TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            return ExecutionResult(
                status=ExecutionResultStatus.TOOL_ERROR, error_category="tool_exception"
            )
        return ExecutionResult(status=ExecutionResultStatus.SUCCEEDED, value=value)


class ExecutionAuthorization(BaseModel):
    """Publicly constructible claims with an engine-only HMAC signature."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    invocation_id: UUID
    run_id: UUID
    call_id: str = Field(min_length=1, max_length=128)
    tool_name: str = Field(min_length=1, max_length=128)
    definition_identity: int = Field(gt=0)
    arguments_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: PolicyDecision
    approval_granted: StrictBool
    signature: str = Field(pattern=r"^[a-f0-9]{64}$")

    def signed_payload(self) -> bytes:
        claims = self.model_dump(mode="json", exclude={"signature"})
        return json.dumps(
            claims, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8", errors="strict")


class ExecutionAuthorizationAuthority:
    """Engine-owned HMAC signer. The verifier receives the key but no signing API."""

    def __init__(self) -> None:
        self.__key = secrets.token_bytes(32)

    def _verifier_key(self) -> bytes:
        """Return the verification key to the executor during trusted construction."""
        return self.__key

    def issue(
        self,
        *,
        run_id: UUID,
        call_id: str,
        definition: ToolDefinition,
        arguments_sha256: str,
        decision: PolicyDecision,
        approval_granted: bool,
    ) -> ExecutionAuthorization:
        if decision.effect == PolicyEffect.DENY or (
            decision.effect == PolicyEffect.APPROVAL_REQUIRED and not approval_granted
        ):
            raise ValueError("cannot issue execution authority for a denied invocation")
        invocation_id = uuid4()
        claims = {
            "invocation_id": str(invocation_id),
            "run_id": str(run_id),
            "call_id": call_id,
            "tool_name": definition.name,
            "definition_identity": id(definition),
            "arguments_sha256": arguments_sha256,
            "decision": decision.model_dump(mode="json"),
            "approval_granted": approval_granted,
        }
        payload = json.dumps(
            claims, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8", errors="strict")
        signature = hmac.new(self.__key, payload, hashlib.sha256).hexdigest()
        return ExecutionAuthorization(
            invocation_id=invocation_id,
            run_id=run_id,
            call_id=call_id,
            tool_name=definition.name,
            definition_identity=id(definition),
            arguments_sha256=arguments_sha256,
            decision=decision,
            approval_granted=approval_granted,
            signature=signature,
        )


def verify_execution_authorization(
    authorization: ExecutionAuthorization,
    key: bytes,
    *,
    run_id: UUID,
    call_id: str,
    definition: ToolDefinition,
    arguments_sha256: str,
) -> bool:
    expected = hmac.new(key, authorization.signed_payload(), hashlib.sha256).hexdigest()
    return (
        hmac.compare_digest(expected, authorization.signature)
        and authorization.run_id == run_id
        and authorization.call_id == call_id
        and authorization.tool_name == definition.name
        and authorization.definition_identity == id(definition)
        and authorization.arguments_sha256 == arguments_sha256
        and (
            authorization.decision.effect == PolicyEffect.ALLOW
            or (
                authorization.decision.effect == PolicyEffect.APPROVAL_REQUIRED
                and authorization.approval_granted
            )
        )
    )


def canonical_json_digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8", errors="strict")).hexdigest()
