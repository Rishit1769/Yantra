"""Run the package's deterministic, fully offline agent quickstart."""

from __future__ import annotations

import asyncio

from yantra.devtools.quickstart import run_demo
from yantra.runtime import AgentTerminationReason


async def main() -> None:
    result, provider = await run_demo()
    print("YANTRA offline agent demonstration (no network requests)")
    print(f"Final answer: {result.output or '(no visible answer)'}")
    if result.termination_reason != AgentTerminationReason.FINAL_RESPONSE:
        raise SystemExit(f"offline agent demo failed: {result.error_code or 'unknown'}")
    if len(provider.requests) != 2 or len(result.tool_results) != 1:
        raise SystemExit("offline agent demo did not complete the expected tool cycle")


if __name__ == "__main__":
    asyncio.run(main())
