"""Human-readable, payload-minimal diagnostics for agent run results."""

from __future__ import annotations

import re

from yantra.runtime.models import AgentRunResult

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:api[_-]?key|access[_-]?token|password|secret|authorization)\b\s*[:=]\s*)"
    r"([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")


def _safe_label(value: str) -> str:
    value = _SECRET_ASSIGNMENT.sub(r"\1[REDACTED]", value)
    value = _BEARER.sub("Bearer [REDACTED]", value)
    return value.replace("\r", "\\r").replace("\n", "\\n")[:256]


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
        for item in result.tool_results:
            status = "error" if item.is_error else "success"
            lines.append(f"- {_safe_label(item.name)} [{_safe_label(item.call_id)}]: {status}")
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
    if result.error_code:
        lines.append(f"Error category: {_safe_label(result.error_code)}")
    lines.append("Trace:")
    for entry in result.trace:
        details = [entry.event, entry.state.value]
        if entry.outcome:
            details.append(f"outcome={_safe_label(entry.outcome)}")
        if entry.tool_name:
            details.append(f"tool={_safe_label(entry.tool_name)}")
        if entry.call_id:
            details.append(f"call_id={_safe_label(entry.call_id)}")
        if entry.error_code:
            details.append(f"error={_safe_label(entry.error_code)}")
        lines.append(f"{entry.sequence}. " + " | ".join(details))
    return "\n".join(lines)
