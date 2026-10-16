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


def test_runtime_diagnostics_omit_untrusted_identifiers_and_private_metadata() -> None:
    import asyncio

    result, _ = asyncio.run(load_demo()())
    original = result.trace[0]
    trace = original.model_copy(
        update={
            "tool_name": "sk-synthetic-tool-key\nforged-工具",
            "call_id": "Bearer synthetic-call-token\n" + ("x" * 100),
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

    assert "sk-synthetic-tool-key" not in output
    assert "forged-工具" not in output
    assert "synthetic-call-token" not in output
    assert "x" * 100 not in output
    assert "tool[1]" in output
    assert "private-canary" not in output
    assert output == format_run_result(changed)


def test_runtime_diagnostics_show_only_allowlisted_tool_error_categories() -> None:
    import asyncio

    result, _ = asyncio.run(load_demo()())
    payload = result.model_dump()
    payload["tool_results"] = (
        {
            "call_id": "sk-synthetic-call-secret",
            "name": "sk-synthetic-name-secret",
            "result": {
                "error_code": "invalid_arguments",
                "message": "Authorization: Bearer synthetic-payload-token",
                "arguments": {"private": "synthetic-argument-secret"},
            },
            "is_error": True,
        },
        *(
            {
                "call_id": f"ordinary-{code}",
                "name": "calculator.add",
                "result": {"error_code": code, "message": "private exception text"},
                "is_error": True,
            }
            for code in (
                "tool_not_found",
                "tool_timeout",
                "tool_approval_required",
                "invalid_output",
                "tool_exception",
            )
        ),
        {
            "call_id": "Bearer synthetic-missing-category-token",
            "name": "calculator.add",
            "result": {"message": "secret should not be displayed"},
            "is_error": True,
        },
        {
            "call_id": "ordinary-malformed-payload",
            "name": "calculator.add",
            "result": "untrusted raw error payload",
            "is_error": True,
        },
        {
            "call_id": "ordinary-successful",
            "name": "calculator.add",
            "result": {"total": 20},
            "is_error": False,
        },
        {
            "call_id": "ordinary-unknown-category",
            "name": "calculator.add",
            "result": {"error_code": "attacker-controlled-category"},
            "is_error": True,
        },
    )
    output = format_run_result(AgentRunResult.model_validate(payload))

    assert "error (invalid_arguments)" in output
    assert "error (tool_not_found)" in output
    assert "error (tool_timeout)" in output
    assert "error (tool_approval_required)" in output
    assert "error (invalid_output)" in output
    assert "error (tool_exception)" in output
    assert "tool[9]: success" in output
    assert "tool[7]: error" in output
    assert "tool[8]: error" in output
    assert "attacker-controlled-category" not in output
    assert "synthetic-payload-token" not in output
    assert "sk-synthetic-call-secret" not in output
    assert "sk-synthetic-name-secret" not in output
    assert "calculator.add" not in output
    assert "ordinary-successful" not in output
    assert "synthetic-argument-secret" not in output
    assert "private exception text" not in output
    assert "secret should not be displayed" not in output
    assert "untrusted raw error payload" not in output
    assert "12 + 8 = 20" not in output
