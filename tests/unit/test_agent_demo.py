import runpy
from pathlib import Path

import pytest

from yantra.core.messages import MessageRole
from yantra.core.states import RunState
from yantra.runtime import AgentRunResult, AgentTerminationReason, format_run_result


def load_demo():
    example = Path(__file__).resolve().parents[2] / "examples" / "agent_loop_offline.py"
    return runpy.run_path(str(example))["run_demo"]


@pytest.mark.asyncio
async def test_offline_agent_example_runs_full_gateway_tool_cycle_repeatably() -> None:
    run_demo = load_demo()
    first, first_provider = await run_demo()
    second, second_provider = await run_demo()

    for result, provider in ((first, first_provider), (second, second_provider)):
        assert result.output == "12 + 8 = 20. The sum is 20."
        assert result.termination_reason == AgentTerminationReason.FINAL_RESPONSE
        assert len(result.steps) == 2
        assert len(result.tool_results) == 1
        assert result.tool_results[0].call_id == "offline-add-1"
        assert result.tool_results[0].result == {"total": 20}
        assert len(provider.requests) == 2
        second_request = provider.requests[1]
        assert second_request.messages[-1].role == MessageRole.TOOL
        assert second_request.messages[-1].tool_result == result.tool_results[0]
        assert [entry.sequence for entry in result.trace] == list(range(1, len(result.trace) + 1))
        assert result.trace[-1].state.value == "completed"


def test_runtime_diagnostics_report_failure_and_unknown_usage_safely() -> None:
    import asyncio

    result, _ = asyncio.run(load_demo()())
    payload = result.model_dump()
    payload["trace"][-1].update(
        event="provider_failure",
        state=RunState.FAILED,
        error_code="provider_authentication_error",
    )
    failed = AgentRunResult.model_validate(
        payload
        | {
            "state": "failed",
            "termination_reason": "provider_failure",
            "usage": None,
            "usage_complete": False,
            "total_cost_usd": None,
            "error_code": "provider_authentication_error",
            "error_message": "provider authentication failed",
        }
    )
    output = format_run_result(failed)

    assert "State: failed" in output
    assert "Termination: provider_failure" in output
    assert "Error category: provider_authentication_error" in output
    assert "Token usage: incomplete or unavailable" in output
    assert "Cost: unavailable" in output
    assert "12 + 8 = 20" not in output


def test_runtime_diagnostics_redact_untrusted_trace_labels() -> None:
    import asyncio

    result, _ = asyncio.run(load_demo()())
    original = result.trace[0]
    trace = original.model_copy(
        update={
            "tool_name": "calculator api_key=synthetic-secret\nforged",
            "call_id": "Bearer abc.def",
        }
    )
    private_message = result.steps[0].response_message.model_copy(
        update={
            "provider_extensions": {"offline.provider": {"reasoning_content": "private-canary"}}
        }
    )
    private_step = result.steps[0].model_copy(update={"response_message": private_message})
    payload = result.model_dump()
    payload["steps"] = (private_step.model_dump(), *payload["steps"][1:])
    changed = AgentRunResult.model_validate(payload | {"trace": (trace, *result.trace[1:])})
    output = format_run_result(changed)

    assert "synthetic-secret" not in output
    assert "abc.def" not in output
    assert "[REDACTED]" in output
    assert "\nforged" not in output
    assert "private-canary" not in output
