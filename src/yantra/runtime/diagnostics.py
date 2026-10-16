"""Human-readable, payload-minimal diagnostics for agent run results."""

from __future__ import annotations

from typing import cast

from yantra.runtime.models import AgentRunResult

_TOOL_ERROR_CODES = frozenset(
    {
        "tool_not_permitted",
        "tool_approval_required",
        "tool_approval_denied",
        "tool_approval_expired",
        "tool_approval_invalid",
        "tool_approval_mismatched",
        "tool_approval_replay",
        "tool_approval_unavailable",
        "tool_not_found",
        "invalid_arguments",
        "tool_timeout",
        "invalid_output",
        "tool_exception",
    }
)
_RUN_ERROR_CODES = frozenset(
    {
        *_TOOL_ERROR_CODES,
        "provider_authentication_error",
        "provider_authorization_error",
        "provider_credential_error",
        "provider_invalid_request",
        "provider_model_unavailable",
        "provider_network_error",
        "provider_error",
        "provider_protocol_error",
        "provider_quota_exceeded",
        "provider_rate_limited",
        "provider_timeout",
        "provider_unavailable",
        "invalid_response",
        "cost_budget_exhausted",
        "cost_budget_unverifiable",
        "duplicate_tool_call_id",
        "max_steps",
        "run_timeout",
        "token_budget_exhausted",
        "token_budget_unverifiable",
        "tool_budget_exhausted",
    }
)


def format_run_result(result: AgentRunResult) -> str:
    """Format summary and trace metadata without arguments, messages, or reasoning."""
    lines = [
        f"State: {result.state.value}",
        f"Termination: {result.termination_reason.value}",
        f"Model steps: {len(result.steps)}",
        f"Tool calls: {len(result.tool_results)}",
    ]
    if result.tool_results:
        lines.append("Tools:")
        for index, item in enumerate(result.tool_results, start=1):
            status = "error" if item.is_error else "success"
            category = _tool_error_category(item.result) if item.is_error else None
            suffix = f" ({category})" if category else ""
            lines.append(f"- tool[{index}]: {status}{suffix}")
    if result.usage_complete and result.usage is not None:
        lines.append(
            "Token usage: "
            f"input={result.usage.input_tokens}, output={result.usage.output_tokens}, "
            f"total={result.usage.total_tokens}"
        )
    else:
        lines.append("Token usage: incomplete or unavailable")
    if result.total_cost_usd is None:
        lines.append("Cost: unavailable")
    else:
        lines.append(f"Cost: ${result.total_cost_usd:.6f} USD")
    if result.error_code in _RUN_ERROR_CODES:
        lines.append(f"Error category: {result.error_code}")
    lines.append("Trace:")
    for entry in result.trace:
        details = [entry.event, entry.state.value]
        if entry.outcome in {"tool_calls", "text", "success", "error"}:
            details.append(f"outcome={entry.outcome}")
        if entry.error_code in _RUN_ERROR_CODES:
            details.append(f"error={entry.error_code}")
        lines.append(f"{entry.sequence}. " + " | ".join(details))
    return "\n".join(lines)


def _tool_error_category(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    category = cast(dict[str, object], payload).get("error_code")
    return category if isinstance(category, str) and category in _TOOL_ERROR_CODES else None
