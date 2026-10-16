"""Trusted, invocation-bound approval contracts and in-memory replay protection."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from yantra.tools.policy import PermissionScope, PolicyEffect, PolicyReason, ToolRiskLevel


class ApprovalStatus(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"


class ApprovalRequest(BaseModel):
    """Trusted metadata for exactly one proposed tool invocation; arguments are never exposed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    run_id: UUID
    session_id: UUID
    invocation_id: UUID
    tool_name: str = Field(min_length=1, max_length=128)
    definition_identity: int = Field(gt=0)
    required_scopes: frozenset[PermissionScope]
    risk_level: ToolRiskLevel
    policy_effect: PolicyEffect
    policy_reason: PolicyReason
    arguments_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    authorization_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approval timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def requires_approval_policy(self) -> ApprovalRequest:
        if self.policy_effect != PolicyEffect.APPROVAL_REQUIRED:
            raise ValueError("approval requests require an approval-required policy outcome")
        return self


class ApprovalDecision(BaseModel):
    """Host-provider response, bound to the trusted request rather than a model call ID."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    status: ApprovalStatus
    authorization_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ApprovalProvider(Protocol):
    """Trusted host authority; never exposed as an ordinary model tool."""

    async def request_approval(self, request: ApprovalRequest) -> ApprovalDecision: ...


class ApprovalStore(Protocol):
    """Atomic, process-local, single-use approval record store."""

    def register(self, request: ApprovalRequest, definition: object) -> None: ...

    def consume(
        self, request: ApprovalRequest, definition: object, decision: ApprovalDecision
    ) -> bool: ...

    def revoke(self, request_id: UUID) -> None: ...


class InMemoryApprovalStore:
    """Thread-safe, single-process store. Consumption is atomic and precedes dispatch."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._records: dict[UUID, tuple[ApprovalRequest, object, bool]] = {}

    def register(self, request: ApprovalRequest, definition: object) -> None:
        with self._lock:
            if request.request_id in self._records:
                raise ValueError("approval request identifier is already registered")
            self._records[request.request_id] = (request, definition, False)

    def consume(
        self, request: ApprovalRequest, definition: object, decision: ApprovalDecision
    ) -> bool:
        with self._lock:
            record = self._records.get(request.request_id)
            if record is None:
                return False
            stored_request, stored_definition, consumed = record
            if (
                consumed
                or stored_request != request
                or stored_definition is not definition
                or decision.request_id != request.request_id
                or decision.status != ApprovalStatus.APPROVED
                or decision.authorization_sha256 != request.authorization_sha256
                or request.expires_at <= datetime.now(UTC)
            ):
                return False
            del self._records[request.request_id]
            return True

    def revoke(self, request_id: UUID) -> None:
        with self._lock:
            record = self._records.get(request_id)
            if record is not None and not record[2]:
                del self._records[request_id]


class DeterministicApprovalProvider:
    """Offline provider that approves or denies by trusted tool name configuration."""

    def __init__(self, *, approved_tools: frozenset[str] = frozenset()) -> None:
        self._approved_tools = approved_tools

    async def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        status = (
            ApprovalStatus.APPROVED
            if request.tool_name in self._approved_tools
            else ApprovalStatus.DENIED
        )
        return ApprovalDecision(
            request_id=request.request_id,
            status=status,
            authorization_sha256=request.authorization_sha256,
        )
