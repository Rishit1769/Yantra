# Secure Tool Runtime Platform Validation

This procedure validates the actual subprocess lifecycle on a target OS. A
platform marker or mocked process object is not a substitute for running the
worker. Current local evidence is macOS with Python 3.12; Windows and Python
3.13/3.14 remain pending. Hosted CI is not part of this procedure.

## Windows

From a Windows checkout on `feat/yantra-004-secure-tools`, using an already
provisioned environment and installed locked dependencies, run in PowerShell:

```powershell
uv lock --check
uv run --offline --no-sync ruff check .
uv run --offline --no-sync ruff format --check .
uv run --offline --no-sync pyright src examples
uv run --offline --no-sync pytest -q -p no:cacheprovider
uv run --offline --no-sync python examples/secure_tool_policy.py
uv run --offline --no-sync python examples/secure_tool_approval.py
uv run --offline --no-sync python examples/secure_tool_boundaries.py
```

Record the actual Windows version, Python version, command outputs, and commit
hash. Confirm normal worker completion, timeout and cancellation cleanup,
startup failure, nonzero exit, capacity release, and repeated runs. Use the
lifecycle tests' retained process handles and assertions as cleanup evidence;
do not enumerate processes by PID or terminate unrelated processes.
If any command requires downloading dependencies or an interpreter, stop and
arrange provisioning separately; this check is intended to be offline.

## macOS

Run the same commands from an already provisioned checkout. Record macOS and
Python versions plus the exact commit. This verifies the direct worker lifecycle
on that machine only; it does not prove Windows behavior or descendant cleanup.

## Additional Python versions

Run the full offline suite separately under each project-supported interpreter
(currently declared as Python 3.12, 3.13, and 3.14). Record a result per
interpreter and OS. Do not infer compatibility from the project classifiers or
from a different interpreter's successful run.
