# Installation and CLI troubleshooting

## `yantra` or `yantra-smoke` is not found

Confirm installation succeeded in the intended virtual environment. Prefer
calling the venv executable directly instead of depending on the shell PATH:

```zsh
.venv/bin/yantra --version
.venv/bin/yantra quickstart
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\yantra.exe --version
.\.venv\Scripts\yantra.exe quickstart
```

If the command is absent, install the wheel again using that venv's Python
executable. Do not install the unreleased candidate with `pip install yantra`;
the package is not on PyPI.

## PowerShell activation is blocked

PowerShell execution policy can block `Activate.ps1`. YANTRA does not require
activation: invoke `\.venv\Scripts\python.exe`, `\.venv\Scripts\yantra.exe`,
or `\.venv\Scripts\yantra-smoke.exe` directly. If you choose to adjust a
policy, follow your organization's Windows guidance; do not weaken a
machine-wide policy just to activate a venv.

## Wrong Python version

Check `py --list` or `py -0p`, then create a fresh environment with Python
3.12 or newer (`py -3.12 -m venv .venv` on Windows,
`python3.12 -m venv .venv` on macOS). Do not reuse an environment created by a
different interpreter when debugging import or entry-point problems.

## `yantra doctor` reports missing dependencies

Use the Python executable belonging to the venv to install the downloaded
wheel. The wheel installation resolves its declared runtime dependencies; a
restricted network may require an approved package mirror. `httpx`, `httpcore`,
and `pydantic` are required runtime packages. The `keyring` package is optional
and is not required for offline use.

## Credentials are not configured

`yantra doctor` checks whether `OPENCODE_ZEN_API_KEY` and
`OPENCODE_GO_API_KEY` are non-empty in the current process environment. It
prints only configured/not configured status. Set the variable in the same
terminal from which the command runs, and never paste secret values into a
command argument or support log. No credentials are needed for `yantra
quickstart`.

## Ollama is unavailable

Ollama is optional. `yantra doctor` does not contact it unless
`--check-ollama` is passed. Start Ollama locally if desired; the check targets
only `127.0.0.1:11434` and stops after a bounded timeout. This diagnostic does
not download a model. `yantra models ollama --live` performs live catalog
discovery; use a model already installed in Ollama before running a completion
with `yantra-smoke`.

## Model catalog or provider request failed

Catalog discovery is live only when `yantra models PROVIDER --live` is used.
Check network access, provider service status, credential presence, and the
provider's own model identifiers/entitlements. A catalog entry does not prove
inference is permitted. YANTRA's mock tests and CI do not establish live
provider compatibility. Never share raw credentials or unredacted HTTP
headers.

## Artifact cannot be installed or verified

Confirm the wheel matches the running Python (YANTRA supports Python 3.12+),
download all files from the same Actions artifact, and verify the wheel and
sdist against `SHA256SUMS.txt`. For installation from a source archive, use a
clean environment and ensure build dependencies can be retrieved. See the
[artifact verification procedure](../development/release-artifact-verification.md).
