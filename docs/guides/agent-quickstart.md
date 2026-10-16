# Agent Runtime Quickstart (YANTRA-003-V03)

The experimental agent runtime connects a configured `ModelGateway` to the
existing typed tool registry. It runs a bounded asynchronous model/tool loop,
validates proposed tool arguments and results, and returns an
`AgentRunResult` containing the final response, stop category, usage when
available, and sanitized trace metadata. The gateway/provider contracts are
the existing public interfaces; the agent runtime is still experimental and
does not promise a stable pre-1.0 API.

## Run the offline demonstration

From the repository root, install the locked development environment and run:

```bash
uv sync --locked --all-groups
uv run python examples/agent_loop_offline.py
```

The example uses a deterministic in-process provider, the real
`ModelGateway`, `AgentExecutionEngine`, and a registered typed calculator tool.
It performs a complete two-model-step tool cycle, makes no provider request,
does not resolve credentials, and is repository-only (examples are not included
in the wheel or source distribution).

The output includes a visible final answer followed by structured diagnostics.
It reports the state, termination reason, model/tool counts, tool names and
call IDs, known usage/cost, error category where present, and trace event order.
The formatter intentionally omits message content, tool arguments, and provider
reasoning. Missing usage and cost are shown as unavailable, never estimated by
the formatter.

## Use a controlled tool

Tools are registered explicitly. Each definition declares its input model,
optional output model, sync/async execution mode, and side-effect category.
`AgentRunConfig.tool_names` can further restrict which registered tools are
advertised and executable during that run.

```python
from pydantic import BaseModel

from yantra.tools import ExecutionMode, SideEffect, ToolDefinition, ToolRegistry

class AddInput(BaseModel):
    left: int
    right: int

class AddOutput(BaseModel):
    total: int

def add(arguments: AddInput) -> AddOutput:
    return AddOutput(total=arguments.left + arguments.right)

tools = ToolRegistry()
tools.register(
    ToolDefinition(
        name="calculator.add",
        description="Add two integers.",
        input_model=AddInput,
        output_model=AddOutput,
        executor=add,
        execution_mode=ExecutionMode.SYNC,
        side_effect=SideEffect.READ_ONLY,
    )
)
```

The example contains the complete gateway/provider setup and runnable loop.
`AgentRunConfig` accepts the selected `provider/model`, initial typed messages,
step/tool/time limits, optional token/cost budgets, and the tool allowlist.
Always inject the gateway and registry explicitly; the runtime does not load
credentials or create global registries on its own.

## Inspect a result and cancel a run

Await `engine.run(config)` to receive the immutable result. Check
`termination_reason` and `error_code` instead of treating every non-exceptional
return as success. `format_run_result(result)` provides a concise summary and
trace for developer display; inspect the typed `steps`, `tool_results`, `usage`,
and `trace` fields when application logic needs structured data.

For explicit cooperative cancellation, pass a `CancellationToken` and call
`cancel()` from the owning task:

```python
import asyncio

from yantra.runtime import AgentExecutionEngine, AgentRunConfig, CancellationToken

async def run_with_cancellation(engine: AgentExecutionEngine, config: AgentRunConfig) -> None:
    cancellation = CancellationToken()
    task = asyncio.create_task(engine.run(config, cancellation=cancellation))
    # The owning application decides when cancellation is needed.
    cancellation.cancel()
    result = await task
    print(result.termination_reason)
```

External `asyncio.Task.cancel()` propagates `CancelledError`; explicit token
cancellation returns a `CANCELLED` result. Async handlers are cancelled and
awaited where possible. A synchronous handler runs in a worker thread and
cannot be forcibly stopped by Python, even though the runtime stops waiting.

## Implemented boundaries

The engine supports sequential registered-tool execution, typed input/output
validation, per-run tool allowlists, bounded model steps and tool calls,
wall-clock deadlines, cooperative cancellation, normalized gateway failures,
partial-progress results, and sanitized traces. Configured token/cost budgets
fail closed when the required accounting information is unavailable.

The runtime does not provide authorization policy, persistence, durable
recovery, exactly-once side effects, shell/filesystem/browser/network tools,
MCP, multi-agent execution, or production guarantees. Provider tool support
depends on the selected model and is not established by this offline example.
Windows/Linux and hosted CI execution have not been verified here.
