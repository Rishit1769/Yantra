# Configuration

There is no global configuration file or implicit provider selection in this
developer preview. Applications inject provider adapters, credentials,
`ModelGateway`, tool registry, policy, and runtime limits explicitly. See the
[agent runtime quickstart](../guides/agent-quickstart.md) for the Python API.

## CLI provider settings

The focused CLI currently registers these smoke-test providers:

| Provider | Configuration | Network behavior |
|---|---|---|
| `ollama` | Local endpoint defaults to `http://127.0.0.1:11434` in `yantra-smoke`; `--ollama-url` can override it there. | `yantra doctor` does not probe unless `--check-ollama` is supplied. `yantra models ollama --live` makes a bounded provider catalog operation. |
| `opencode-zen` | `OPENCODE_ZEN_API_KEY` by default. | Catalog lookup requires explicit `--live`; inference is available only through `yantra-smoke` and requires `--allow-billable`. |
| `opencode-go` | `OPENCODE_GO_API_KEY` by default. | Catalog lookup requires explicit `--live`; inference is available only through `yantra-smoke` and requires `--allow-billable`. |

The SDK contains additional adapters, but there is no application-wide
autoconfiguration registry. The smoke CLI provider list is not a statement of
live account entitlement or model compatibility. See the [provider evidence
matrix](../features/provider-verification.md).

Set credentials in the current shell; do not put values in command-line
arguments, source code, logs, or checked-in files. Example for macOS/zsh:

```zsh
read -s "OPENCODE_ZEN_API_KEY?OpenCode Zen API key: "
export OPENCODE_ZEN_API_KEY
printf '\n'
```

For Windows PowerShell, enter the value without echoing it:

```powershell
$secureValue = Read-Host "OpenCode Zen API key" -AsSecureString
$credential = [System.Net.NetworkCredential]::new("", $secureValue)
$env:OPENCODE_ZEN_API_KEY = $credential.Password
Remove-Variable secureValue, credential
```

This sets the variable only for that PowerShell process and its children. It
does not persist the secret to disk. Close the shell when finished. `yantra
doctor` and `yantra providers` show availability without displaying credential
values. The CLI doctor checks only the default environment references; it does
not unlock or inspect OS keyring entries.

The existing `yantra-smoke` supports alternate `env://` and `keyring://`
references using `--zen-credential-ref` and `--go-credential-ref`. Keyring
support is optional and requires the `credentials` extra plus a supported
macOS Keychain or Windows Credential Locker backend. Raw keys are rejected as
reference values. Environment references are read-only.

## Python application configuration

YANTRA does not read a default `.env` file, use PostgreSQL for local execution,
or create global registries. Construct the needed adapters with explicit
settings, register them in `ProviderRegistry`, and pass the registry to
`ModelGateway`. Supply `CredentialManager` and a trusted approval provider
from the host where required. Unknown model capabilities remain unknown and
fail closed where a capability is required.

Never assume that provider catalog listing proves inference access. A live
catalog lookup may transmit a request to the provider but is not an inference
request. No CLI command performs live model discovery unless `--live` is
present; no billable inference occurs in `yantra quickstart` or `yantra
doctor`.
