# Secure Tool Runtime and Restricted Execution (YANTRA-004-V05)

YANTRA-004 adds an in-process authorization layer to the bounded YANTRA-003
agent loop. Logical capability scopes and an explicit tool-name allowlist are
independent requirements. Registration, model output, and provider schemas
never create authority.

## Threat model

The model and its tool-call fields are untrusted: it may claim approval, repeat
call IDs, substitute tools or arguments, or submit calls after policy changes.
The host-provided policy context, registry, approval provider, and Python
process are trusted. Trusted UUIDs, exact definition identity, canonical
digests, policy revalidation, expiry, and atomic consume prevent stale or
cross-invocation approvals from authorizing dispatch. Provider errors, malformed
responses, cancellation, and expiry fail closed. This does not defend against
a compromised host/provider, malicious in-process Python, or direct calls to a
handler by trusted application code.

These are separate guarantees: **authorization** decides whether policy permits
the exact call; **approval** records trusted consent when policy requires it;
**process isolation** runs eligible work in a separate OS process;
**sandboxing** requires OS-enforced restrictions on that process. YANTRA
implements the first three in the stated scope, but does not provide the fourth.

## Policy contracts

`PermissionScope` is a validated string identifier (3–128 lowercase ASCII
letters/digits and dot, colon, underscore, or hyphen separators). Wildcards and
prefix matching are unsupported. Every scope declared by a tool must be
granted. `ToolRiskLevel` classifies risk but never grants permission.

The host supplies a frozen per-run `PolicyContext` via
`AgentRunConfig.permission_context`:

```python
PolicyContext(
    granted_scopes={"filesystem.read", "filesystem.write"},
    denied_scopes={"filesystem.delete"},
    approval_required_scopes={"filesystem.write"},
    approval_required_risks={ToolRiskLevel.CRITICAL},
)
```

Explicit denial wins, missing grants deny, and policy `DENY` cannot be
overridden by approval. The injected evaluator can further restrict access.
Legacy unscoped tools retain V01 name-allowlist behavior only when
`allow_legacy_unscoped_tools` is enabled; scoped tools cannot use that path.

## Trusted approval lifecycle

For each proposed call, the engine enforces the name allowlist, resolves the
registered definition, evaluates policy, and handles `ALLOW`, `DENY`, or
`APPROVAL_REQUIRED`. For the latter, it asks the host-injected
`ApprovalProvider`; the provider is never exposed as a model tool. Without a
provider, or on provider error, malformed response, denial, or timeout, the
handler does not run.

The frozen `ApprovalRequest` contains trusted run, session, request, and
invocation UUIDs; tool name and in-process definition identity; required
scopes, risk and policy categories; expiry; and SHA-256 digests of arguments
and authorization context. Raw arguments and model call IDs are not approval
credentials and are not passed to the provider. Argument canonicalization
uses sorted compact JSON and strict UTF-8, rejecting NaN/infinity or unsupported
values. The approval decision must match both the request UUID and context
digest.

`InMemoryApprovalStore` binds a request to the original tool definition and
uses a thread lock to allow only one atomic consumption. Engine policy and
registry identity are revalidated immediately before consume/dispatch. The
engine-owned internal executor verifies an HMAC authorization bound to the
exact run, call ID, tool, argument digest, policy decision, approval state, and
registered definition identity, and consumes its invocation ID once. A public
`PolicyDecision(ALLOW)` or caller-created claims are insufficient. A standalone
public `ToolExecutor` has no verifier and fails closed; when supplied to the
engine, its registry and configured boundaries are wrapped by a new
engine-bound executor. HMAC keys are never returned by the executor API. This
closes both the V02 callable capability issuer and the V03 private key-binding
method for supported public API callers. Python is not a same-process security
boundary: code with private-member introspection, runtime monkeypatching, or
control of the host process remains trusted.

The default approval lifetime is 60 seconds (configurable up to one hour).
Cancellation revokes pending approval before dispatch. Approval is consumed
before dispatch, so a dispatch failure does not make it reusable. The store is
process-local, not durable, and provides no replay protection across restarts.
Policy authorization, human approval, and tool success remain distinct
outcomes; sanitized trace events record approval requested/granted/denied,
expiry, cancellation, mismatch, replay rejection, consumption, and dispatch.

## Side-effect and cancellation limits

Approval is required before handler dispatch. Tools may use either a trusted
in-process callable or the fixed YANTRA worker subprocess. Subprocess handlers
must use a statically registered identifier; the model cannot choose a module,
executable, source string, shell command, or worker path. The worker is started
with the current interpreter in isolated/no-site mode, receives only a
versioned bounded JSON request (never approval data), and returns bounded JSON.
The parent applies request/response/diagnostic byte limits, an execution
deadline, and a concurrent-worker cap. Errors are normalized and worker stderr
is not returned as tool output.

This is a restricted execution boundary, **not an OS sandbox**. The child still
runs as the same user and may access filesystem, network, OS credentials, and
other resources available to that user. Environment variables are reduced but
not all ambient OS authority is removed. Cancellation/timeout terminates and
reaps the direct child; descendants are not tracked or guaranteed to stop.
Process termination cannot roll back external effects. In-process synchronous
handlers run in a thread and cannot be forcibly stopped. `SideEffect` and risk
labels remain metadata unless trusted policy uses them to restrict access.

## V01–V04 security review

| Finding | Severity / category | Components and root cause | Evidence, correction, regression, status |
|---|---|---|---|
| V02 dispatch capability issuer was callable from a public executor object. | HIGH — authorization vulnerability | `ToolExecutor` exposed minting; callers did not need engine policy/approval. | Reproduced by direct method access. V03 removed the issuer and added HMAC dispatch authority. Tests reject public ALLOW-only and forged claims. Resolved for supported APIs. |
| V03 key-binding method allowed a caller to select a signing key for its executor. | HIGH — authorization vulnerability | `ToolExecutor._bind_authorization_key` accepted caller-provided bytes; combined with caller-created authority this enabled self-signed valid dispatch. | Regression constructs a caller-owned authority/token and confirms the public executor rejects it. V04 removes key binding; public executor has no verifier, and the engine wraps it with an engine-owned verifier. Resolved for supported APIs. |
| Name allowlist, exact scope grants and explicit-denial precedence. | No issue found | Engine checks run names and policy before issuance. | Denial-before-dispatch tests remain passing. |
| Approval provider spoofing, mismatch, expiry, cancellation, replay, and concurrency. | No issue found | Provider remains host-injected; approval is bound and atomically consumed. | Existing binding, expiry, cancellation, replay and atomicity tests remain passing; V04 adds a late-approval-after-cancellation test. |
| Registry substitution after authorization. | No issue found | Dispatch revalidates exact registered definition identity and policy. | Existing registry mutation regression remains passing. |
| JSON ambiguity, worker exception leakage, and model-selected executable/import. | No issue found | Strict JSON, static handler allowlist, and normalized errors are used. | Malformed/duplicate protocol tests pass; no shell or pickle path exists. |
| Process descendants and OS-level resource isolation. | LOW — documented limitation | Ordinary subprocess APIs only manage the direct child here. | Direct child cleanup is tested; process-tree cleanup and OS quotas/restrictions remain unimplemented. |

The HMAC key is generated randomly by the engine-owned authority. Canonical
sorted compact JSON encodes typed claims; HMAC-SHA256 uses constant-time
signature comparison. Claims bind run, invocation, call, tool definition,
arguments, decision and approval state. Consumption is atomic under a thread
lock. Python object internals are not secret from hostile code in the same
process; that code is outside the supported threat boundary.

Name allowlisting, scope denial precedence, fail-closed approval behavior,
approval binding/expiry/atomic consumption, and policy/registry revalidation
remain enforced before dispatch. Pre-observed cancellation is checked before an
operation starts; pending approval is revoked. Cancellation racing an already
completed operation follows asyncio task-completion ordering. Startup and
repeated cancellation now await shielded cleanup so a returned direct child is
reaped.

The implementation deliberately does not create process groups or Windows Job
Objects. Without actual Windows validation it cannot claim consistent
descendant cleanup across both target platforms. It uses no broad PID
enumeration. Protocol/lifecycle limits are not CPU, memory, or disk quotas.

## V05 final acceptance

V05 rechecked the model-to-handler authorization path and verified that signed
dispatch authority is rejected when arguments, run identity, or registered
definition are substituted. Existing offline tests cover public ALLOW claims,
caller-minted/replayed tokens, scope/approval denial, cross-run or digest
mismatch, registry mutation, late approval after cancellation, and subprocess
cleanup. The test matrix does not move the Python host process into the threat
boundary: same-process private-member access and monkeypatching remain trusted
host capabilities, not supported attacker APIs. See the [formal engineering
closure](../development/yantra-004-engineering-closure.md) for the final
security finding register, full validation evidence, and release blockers.

Legacy unscoped tools continue to default to
`allow_legacy_unscoped_tools=True` for compatibility. They still require the
independent tool-name allowlist. A future default change should follow an
explicit migration/deprecation decision; V05 does not silently change it.

## Security guarantees matrix

| Capability | Status | Evidence / boundary |
|---|---|---|
| Name/scope policy, approvals, exact-call HMAC authorization | Implemented and tested | RR-004 local regression suites pass on macOS/Python 3.12–3.14; public standalone executor calls fail closed. This is regression verification, not an independent security certification. |
| JSON protocol, static handlers, byte/time/concurrency limits | Implemented and tested | Full suite and offline worker tests pass locally on macOS/Python 3.12–3.14; hosted CI also passed the configured matrix. |
| Direct-child timeout/cancellation cleanup, including startup and repeated cancellation | Implemented and tested | Execution-boundary tests pass locally on macOS/Python 3.12–3.14 and in the hosted OS/Python matrix. Descendant cleanup is not guaranteed. |
| Subprocess startup, termination, handles, and environment behavior on Windows | CI-tested for the covered suite | RR-003 Actions run [39114896871](https://github.com/Rishit1769/Yantra/actions/runs/39114896871), commit `2f07ec9`: Windows Python 3.12/3.13/3.14 test/build/CLI jobs passed. This is not a process-tree or Windows Job Object guarantee. |
| Python 3.13 and 3.14 | Verified in hosted CI and RR-004 macOS tests | RR-004 full suite passed on macOS/Python 3.13.15 and 3.14.7; RR-003 hosted matrix passed those interpreters on Ubuntu, macOS, and Windows. |
| Descendant/process-tree cleanup | Planned, not implemented | No process groups or Windows Job Objects; direct-child guarantee only. |
| CPU/memory/disk quotas; filesystem/network restrictions; rollback | Explicitly unsupported | Needs separate OS-enforced design and platform evidence. |
| Containment of hostile in-process Python | Explicitly unsupported | Host code and registered handlers are trusted. |

## Offline example

Run `uv run python examples/secure_tool_approval.py` for the V02 approval
lifecycle. `examples/secure_tool_boundaries.py` demonstrates in-process and
fixed-handler subprocess execution, policy denial, timeout cleanup, and
sanitized diagnostics without network or credentials.
`examples/secure_tool_policy.py` remains the V01 grant/deny demonstration.
