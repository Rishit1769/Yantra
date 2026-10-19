# Installation

YANTRA requires Python 3.12 or newer. Version `0.2.0` is an unpublished
developer-preview candidate; it is **not available on PyPI**. The supported
package artifacts are produced by the release-candidate workflow when that
workflow has passed; a workflow definition alone is not evidence that an
artifact exists. Download artifacts from a successful GitHub Actions run
while retained. Installing a wheel or source archive does not require the
YANTRA checkout to remain present.

## Obtain an artifact

Open the successful **Release Candidate Verification** GitHub Actions run and
download its `yantra-<commit-sha>` artifact. It contains the wheel, source
distribution, and `SHA256SUMS.txt`. Verify checksums and archive contents with
the procedure in [release artifact verification](../development/release-artifact-verification.md).

## macOS (pip)

From the folder containing the downloaded wheel:

```zsh
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install ./yantra-0.2.0-py3-none-any.whl
.venv/bin/yantra --version
.venv/bin/yantra doctor
.venv/bin/yantra quickstart
```

## Windows (PowerShell, pip)

Install Python 3.12 or newer from python.org and enable the Python launcher.
From the folder containing the downloaded wheel:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install .\yantra-0.2.0-py3-none-any.whl
.\.venv\Scripts\yantra.exe --version
.\.venv\Scripts\yantra.exe doctor
.\.venv\Scripts\yantra.exe quickstart
```

Using the executables directly avoids PowerShell activation-policy changes.
If you prefer activation, use `.\.venv\Scripts\Activate.ps1`; see the
[Windows troubleshooting guide](troubleshooting.md) if your local policy blocks
that script.

## Optional uv workflow

Install uv using its official installer. Create an isolated environment and
install the downloaded wheel:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python ./yantra-0.2.0-py3-none-any.whl
.venv/bin/yantra quickstart
```

On Windows PowerShell, use the venv interpreter under `Scripts`:

```powershell
uv venv --python 3.12 .venv
uv pip install --python .\.venv\Scripts\python.exe .\yantra-0.2.0-py3-none-any.whl
.\.venv\Scripts\yantra.exe quickstart
```

To install the source archive instead, replace the wheel path with
`yantra-0.2.0.tar.gz`. For development from a clone, see
[development setup](../development/setup.md).

## Optional credentials

The offline CLI and quickstart need no key, service, database, or network.
For the currently smoke-tested OpenCode providers, set
`OPENCODE_ZEN_API_KEY` and/or `OPENCODE_GO_API_KEY` in the current shell. YANTRA
prints only whether a value is configured, never the value itself. Ollama uses
its local loopback endpoint and requires no API key. Live catalog requests are
separate from inference; model discovery is opt-in with `yantra models
PROVIDER --live`. See [configuration](configuration.md) and
[CLI reference](../features/cli.md).

The API remains experimental and may change before `1.0.0`. See the
[developer-preview stability policy](../development/developer-preview-policy.md)
for the compatibility contract and known security boundaries.
