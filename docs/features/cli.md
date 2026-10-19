# Developer CLI

YANTRA provides a standard-library `argparse` developer CLI named `yantra`.
The existing `yantra-smoke` command remains available and backward compatible
for gateway-level smoke tests. Neither command installs services or starts a
background process.

## Commands

| Command | Network behavior | Result |
|---|---|---|
| `yantra --version` | None | Prints installed package version. |
| `yantra --help` | None | Lists commands and their usage. |
| `yantra doctor` | None | Checks Python, installed runtime distributions, and presence of default provider environment credentials without revealing values. |
| `yantra doctor --check-ollama` | Bounded loopback request only | Checks `http://127.0.0.1:11434/api/tags`; Ollama remains optional. |
| `yantra providers` | None | Lists CLI smoke providers and whether default credential variables are configured. |
| `yantra models` | None | Lists available CLI smoke providers and explains live discovery is opt-in. |
| `yantra models PROVIDER` | None | Confirms no request was made and prompts for `--live`. |
| `yantra models PROVIDER --live` | Live provider catalog request | Lists catalog models; does not run inference. |
| `yantra quickstart` | None | Runs a deterministic model → tool → model example using an in-process mock. |

`doctor` exits nonzero only for a Python-version or required-runtime-dependency
problem. Missing optional provider configuration and unavailable Ollama are
reported as optional conditions, not package installation failures. The
Ollama request uses a short timeout, `trust_env=False`, no credentials, and a
loopback-only URL.

The CLI smoke registry currently includes Ollama, OpenCode Zen, and OpenCode
Go. The SDK also exposes additional provider adapters, but those are not
automatically registered in this CLI. Catalog availability does not establish
account entitlement or model support.

## Offline quickstart

After installing a wheel or source archive into an environment, run:

```sh
yantra quickstart
```

It displays the mock model's tool proposal, the typed local calculator result,
and final model response. It uses the same bounded agent engine and explicit
tool registry as the SDK example; no API key, network, database, or provider
service is used. Tools proposed by an actual model are untrusted: this example
only registers and authorizes one local, read-only calculator.

## Legacy gateway smoke CLI

`yantra-smoke` remains the lower-level gateway diagnostic interface:

```sh
yantra-smoke --help
yantra-smoke offline
yantra-smoke providers
yantra-smoke models ollama
```

In the legacy smoke CLI, `models PROVIDER` already means a live catalog
request. The newer `yantra models` command requires explicit `--live` to make
that request. `yantra-smoke complete PROVIDER/MODEL` performs live inference;
OpenCode requires `--allow-billable`. Tool-call mode displays normalized
proposals and never executes them. See the [gateway smoke guide](../development/smoke-testing.md)
for provider limitations, token controls, and platform instructions.

## Compatibility and security

The `yantra` entry point is additive; `yantra-smoke` and its existing flags
remain available. CLI output does not include credential values or provider
reasoning. `doctor` checks only the default environment references and does
not query the keyring. Live model discovery is explicit and separate from
inference. Neither CLI makes YANTRA an OS sandbox: the Python host remains
trusted, and filesystem/network access are not isolated.

The API and CLI are pre-1.0 developer-preview interfaces and may change.
See the [stability policy](../development/developer-preview-policy.md),
[installation guide](../getting-started/installation.md), and
[troubleshooting guide](../getting-started/troubleshooting.md).
