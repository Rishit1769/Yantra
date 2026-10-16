# Secure Tool Runtime and Restricted Execution (YANTRA-004-V03)

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
executor now verifies an engine-HMAC authorization bound to the exact run, call
ID, tool, arguments digest, policy decision, approval state, and registered
definition identity, and consumes its invocation ID once. A public
`PolicyDecision(ALLOW)` or fabricated claims are insufficient. The signing key
and token are process-local; this closes the V02 callable private-capability
issuer defect for ordinary API callers, but is not protection from malicious
Python code with introspection or control of the process.

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

## V01/V02 security review and V03 disposition

The V02 executor exposed a private capability-issuing method on the executor
object. Any ordinary caller able to invoke that method could mint dispatch
authority without passing through the engine's policy/approval flow. This was a
confirmed authorization defect, despite the method's underscore naming. V03
removes that issuer from the executor and adds engine-held HMAC signing,
executor-side signature/claim verification, exact definition and argument
binding, and atomic one-use consumption. Tests cover forged claims, replay,
and the public ALLOW-only path. This protects the supported API path, not a
hostile same-process Python adversary.

The review also confirmed that name allowlisting, scope denial precedence,
approval-provider fail-closed behavior, approval binding/expiry/atomic consume,
and policy/registry revalidation remain enforced before dispatch. Subprocess
mode adds process separation and killable direct-child cleanup but does not
claim filesystem, network, descendant, or OS-level isolation. The boundary
limits are protocol/lifecycle controls, not CPU, memory, or disk quotas.

## Offline example

Run `uv run python examples/secure_tool_approval.py` for the V02 approval
lifecycle. `examples/secure_tool_boundaries.py` demonstrates fixed-handler
subprocess execution and deadline cleanup without network or credentials.
`examples/secure_tool_policy.py` remains the V01 grant/deny demonstration.
