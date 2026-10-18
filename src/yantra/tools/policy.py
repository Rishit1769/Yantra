"""Immutable logical authorization contracts for tool execution."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, StringConstraints

PermissionScope = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=128,
        pattern=r"^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$",
    ),
]


class ToolRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class PolicyReason(StrEnum):
    ALLOWED = "allowed"
    LEGACY_UNSCOPED = "legacy_unscoped"
    EXPLICIT_DENY = "explicit_deny"
    MISSING_SCOPE = "missing_scope"
    APPROVAL_REQUIRED = "approval_required"
    RISK_RESTRICTED = "risk_restricted"
    POLICY_RESTRICTED = "policy_restricted"
    MISSING_CONTEXT = "missing_context"
    INVALID_POLICY = "invalid_policy"
    EVALUATOR_ERROR = "evaluator_error"


class PolicyRequest(BaseModel):
    """Trusted tool metadata presented to a policy evaluator; contains no arguments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: str
    required_scopes: frozenset[PermissionScope] = frozenset()
    risk_level: ToolRiskLevel


class PolicyContext(BaseModel):
    """Application-supplied per-run authority and restrictive policy configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    granted_scopes: frozenset[PermissionScope] = frozenset()
    denied_scopes: frozenset[PermissionScope] = frozenset()
    approval_required_scopes: frozenset[PermissionScope] = frozenset()
    approval_required_risks: frozenset[ToolRiskLevel] = frozenset()


class PolicyDecision(BaseModel):
    """Safe machine-readable outcome; arbitrary evaluator messages are excluded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    effect: PolicyEffect
    reason: PolicyReason


class PolicyEvaluator(Protocol):
    """Synchronous deterministic evaluator over trusted metadata and run context."""

    def evaluate(self, request: PolicyRequest, context: PolicyContext) -> PolicyDecision:
        """Return an authorization restriction or allow decision."""
        ...


class DefaultPolicyEvaluator:
    """Exact-match evaluator that requires every declared scope to be granted."""

    def evaluate(self, request: PolicyRequest, context: PolicyContext) -> PolicyDecision:
        required = request.required_scopes
        if required & context.denied_scopes:
            return PolicyDecision(effect=PolicyEffect.DENY, reason=PolicyReason.EXPLICIT_DENY)
        if not required <= context.granted_scopes:
            return PolicyDecision(effect=PolicyEffect.DENY, reason=PolicyReason.MISSING_SCOPE)
        if required & context.approval_required_scopes:
            return PolicyDecision(
                effect=PolicyEffect.APPROVAL_REQUIRED,
                reason=PolicyReason.APPROVAL_REQUIRED,
            )
        if request.risk_level in context.approval_required_risks:
            return PolicyDecision(
                effect=PolicyEffect.APPROVAL_REQUIRED,
                reason=PolicyReason.RISK_RESTRICTED,
            )
        return PolicyDecision(effect=PolicyEffect.ALLOW, reason=PolicyReason.ALLOWED)
