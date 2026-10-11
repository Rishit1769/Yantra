# Gateway Smoke Testing (YANTRA-002)

`yantra-smoke` is a developer test runner over the existing public provider and gateway APIs. It does not create an agent, execute tools, or write request/response data to disk.

## Modes

| Command | Network behavior | Inference/billing |
|---|---|---|
| `yantra-smoke offline` | None; deterministic mock only | No provider call and no charge |
| `yantra-smoke providers` | None; checks credential-reference availability without displaying values | No inference |
| `yantra-smoke models PROVIDER` | Live provider catalog request | No inference request; provider may still apply its own catalog limits |
| `yantra-smoke complete PROVIDER/MODEL` | Live completion or stream | OpenCode requires `--allow-billable`; Ollama is loopback-only and does not require it |

`--tool-call` sends one harmless `smoke_echo` schema and displays the normalized proposal. YANTRA never executes the proposed tool. Tool testing fails closed when the selected model does not declare tool support. Stream output is buffered until the stream completes so known credential values can be redacted before anything is printed.

The runner supports local Ollama, OpenCode Zen, and OpenCode Go. Zen and Go use the existing `CredentialManager` with `env://` references by default; their references can instead be changed to `keyring://service/account`. The runner does not accept raw keys as arguments, write credentials, create configuration files, or persist requests and responses.

OpenCode Go smoke inference assigns a fresh session ID to the single smoke conversation and sends it in `x-opencode-session`. Go model discovery and inference are separate operations: the official Go `/models` route can return a static catalog, while POST inference separately checks the model, API key, region/data policy, and billing limits. A successful catalog listing therefore does not prove subscription, workspace, region, or model-specific inference access. The CLI displays HTTP status, a validated provider error code, and a safe request ID when returned; it also reports method, OpenCode endpoint path, request field names, header names, and protocol without values. It never prints prompt content, credentials, or the upstream error body. Paths for non-OpenCode hosts are omitted from diagnostics.

Non-streaming Chat Completions diagnostics, for successful as well as failed parsing, report only response field names and JSON types, choice count, finish reasons, and message/usage field shapes. They do not report response values, visible text, or private reasoning. A reasoning-only response is normalized into a provider extension and is not printed; refusal-only responses retain their visible refusal text; a genuinely empty response remains an error.

## macOS Setup

From the repository root, install the locked development environment and run a no-network test:

```zsh
uv sync --locked --all-groups
uv run yantra-smoke offline
uv run yantra-smoke offline --stream --tool-call
uv run yantra-smoke providers
```

### Ollama

Start Ollama using the Ollama app or `ollama serve` in another terminal. Pull a local model, list the models YANTRA can discover, then try completion, streaming, and tool normalization:

```zsh
ollama pull llama3.2
uv run yantra-smoke models ollama
uv run yantra-smoke complete ollama/llama3.2
uv run yantra-smoke complete ollama/llama3.2 --stream
uv run yantra-smoke complete ollama/llama3.2 --tool-call
```

Ollama requests go only to the loopback endpoint `http://127.0.0.1:11434` by default. The tool-call test only displays the model's normalized proposal. Use a model from `models ollama` if `llama3.2` is not installed or listed.

### OpenCode Zen and Go

Enter each key at a hidden prompt. Values are held in the current shell environment only; these commands do not add them to shell history or write them to disk. Keep the shell open for the following tests.

```zsh
read -s "OPENCODE_ZEN_API_KEY?OpenCode Zen API key: "
export OPENCODE_ZEN_API_KEY
printf '\n'
read -s "OPENCODE_GO_API_KEY?OpenCode Go API key: "
export OPENCODE_GO_API_KEY
printf '\n'

uv run yantra-smoke providers
uv run yantra-smoke models opencode-zen
uv run yantra-smoke models opencode-go
```

Choose a model ID from the corresponding catalog output. These interactive commands prompt for the model ID, then make a live request only after the explicit billing confirmation flag:

```zsh
read "ZEN_MODEL?Paste an exact model ID listed for OpenCode Zen: "
uv run yantra-smoke complete "opencode-zen/${ZEN_MODEL}" --allow-billable
uv run yantra-smoke complete "opencode-zen/${ZEN_MODEL}" --stream --allow-billable
uv run yantra-smoke complete "opencode-zen/${ZEN_MODEL}" --tool-call --allow-billable
unset ZEN_MODEL

read "GO_MODEL?Paste an exact model ID listed for OpenCode Go: "
uv run yantra-smoke complete "opencode-go/${GO_MODEL}" --allow-billable
uv run yantra-smoke complete "opencode-go/${GO_MODEL}" --stream --allow-billable
uv run yantra-smoke complete "opencode-go/${GO_MODEL}" --tool-call --allow-billable
unset GO_MODEL

unset OPENCODE_ZEN_API_KEY OPENCODE_GO_API_KEY
```

The catalog request is live but does not run inference. Every OpenCode completion, stream, or tool-call test requires `--allow-billable` and may incur provider charges or use subscription quota. Run only the commands you intend to authorize.

OpenCode Go documents `/responses` for GPT 6 Luna and `/chat/completions` for DeepSeek-family models. Its client guidance calls for an OpenCode-branded user agent and a stable `x-opencode-session`. The Go chat adapter sends `max_tokens` (the documented DeepSeek Chat Completions parameter), while Responses requests use `max_output_tokens`. The current Go documentation lists DeepSeek V4 model IDs rather than `deepseek-flash`; model catalogs can change, so confirm that an ID is currently supported and entitled before inference. See the [OpenCode Go API guide](https://opencode.ai/docs/go.md), [DeepSeek Chat Completions reference](https://api-docs.deepseek.com/api/create-chat-completion), and [OpenAI Responses reference](https://platform.openai.com/docs/api-reference/responses/create).

The official [OpenCode Go model route](https://github.com/anomalyco/opencode/blob/7b3d4ce3a7dbd2a6d3637722a0d5f22a7d086937/packages/console/app/src/routes/zen/go/v1/models.ts) falls back to a static model catalog. Its [inference handler](https://github.com/anomalyco/opencode/blob/7b3d4ce3a7dbd2a6d3637722a0d5f22a7d086937/packages/console/app/src/routes/zen/util/handler.ts) performs separate POST-time model/account checks and forwards protocol requests. It uses `x-opencode-session` for sticky-provider selection but falls back to workspace/IP when absent, so omission alone is not a confirmed cause. The handler's own explicit region/data-policy 403 branches use typed error names; a generic `server_error` can instead originate downstream. Its [OpenAI-compatible request converter](https://github.com/anomalyco/opencode/blob/7b3d4ce3a7dbd2a6d3637722a0d5f22a7d086937/packages/console/app/src/routes/zen/util/provider/openai-compatible.ts) reads `max_tokens`. Without the non-sensitive request shape and provider request ID, the exact source of a live `server_error` remains unconfirmed.

The same Go converter passes responses that already have `choices` through unchanged. DeepSeek's [Chat Completions schema](https://api-docs.deepseek.com/api/create-chat-completion) permits nullable `message.content` and a separate `reasoning_content` field, so such a response must not be treated as text or rejected solely for missing visible text. YANTRA retains reasoning in the qualified provider extension without printing it. Truly empty responses still fail with safe response-shape diagnostics.

## Windows PowerShell

Run from the repository root:

```powershell
uv sync --locked --all-groups
uv run yantra-smoke offline
uv run yantra-smoke offline --stream --tool-call
uv run yantra-smoke providers
```

### Ollama

Start the Ollama application or run `ollama serve` in another PowerShell window:

```powershell
ollama pull llama3.2
uv run yantra-smoke models ollama
uv run yantra-smoke complete ollama/llama3.2
uv run yantra-smoke complete ollama/llama3.2 --stream
uv run yantra-smoke complete ollama/llama3.2 --tool-call
```

Use a model from `models ollama` if `llama3.2` is not installed or listed. The default endpoint is loopback-only and uses no credentials.

### OpenCode Zen and Go

PowerShell prompts for each key as a secure string and exposes it only to this shell process through the environment references consumed by YANTRA's `CredentialManager`:

```powershell
$ZenSecure = Read-Host "OpenCode Zen API key" -AsSecureString
$env:OPENCODE_ZEN_API_KEY = [System.Net.NetworkCredential]::new("", $ZenSecure).Password
Remove-Variable ZenSecure
$GoSecure = Read-Host "OpenCode Go API key" -AsSecureString
$env:OPENCODE_GO_API_KEY = [System.Net.NetworkCredential]::new("", $GoSecure).Password
Remove-Variable GoSecure

uv run yantra-smoke providers
uv run yantra-smoke models opencode-zen
uv run yantra-smoke models opencode-go
```

Copy a model ID from the matching catalog output when prompted:

```powershell
$ZenModel = Read-Host "Paste an exact model ID listed for OpenCode Zen"
uv run yantra-smoke complete "opencode-zen/$ZenModel" --allow-billable
uv run yantra-smoke complete "opencode-zen/$ZenModel" --stream --allow-billable
uv run yantra-smoke complete "opencode-zen/$ZenModel" --tool-call --allow-billable
Remove-Variable ZenModel

$GoModel = Read-Host "Paste an exact model ID listed for OpenCode Go"
uv run yantra-smoke complete "opencode-go/$GoModel" --allow-billable
uv run yantra-smoke complete "opencode-go/$GoModel" --stream --allow-billable
uv run yantra-smoke complete "opencode-go/$GoModel" --tool-call --allow-billable
Remove-Variable GoModel

Remove-Item Env:OPENCODE_ZEN_API_KEY
Remove-Item Env:OPENCODE_GO_API_KEY
```

OpenCode inference may incur provider charges or use subscription quota. The CLI rejects these inference commands unless `--allow-billable` is present. Catalog listing is live but does not run inference.

## Output And Limits

Completion output includes normalized text or tool proposals, finish reason, usage when returned, and elapsed request time. Streaming output includes normalized text/tool-call deltas and any usage event. Provider errors are sanitized; the CLI emits no traceback. It writes no response files, logs, transcripts, or credentials. The smoke runner tests the YANTRA adapter path, not provider account entitlements or production readiness. Windows instructions are documented but require execution on Windows before compatibility can be claimed.
