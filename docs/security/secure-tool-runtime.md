# Secure Tool Runtime and Trusted Approvals (YANTRA-004-V02)

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
executor also requires a private capability bound to the exact call ID, tool,
arguments digest, and registered definition; a caller-supplied public
`PolicyDecision(ALLOW)` by itself is insufficient. This is an in-process
boundary, not protection from a compromised host or hostile code using Python
introspection or directly calling a handler.

The default approval lifetime is 60 seconds (configurable up to one hour).
Cancellation revokes pending approval before dispatch. Approval is consumed
before dispatch, so a dispatch failure does not make it reusable. The store is
process-local, not durable, and provides no replay protection across restarts.
Policy authorization, human approval, and tool success remain distinct
outcomes; sanitized trace events record approval requested/granted/denied,
expiry, cancellation, mismatch, replay rejection, consumption, and dispatch.

## Side-effect and cancellation limits

Approval is required before handler dispatch, but the runtime is not a process
or operating-system sandbox and does not enforce filesystem, network, or
subprocess boundaries. Python handlers can do anything the process identity
permits. The runtime cannot automatically roll back an approved external side
effect, guarantee exactly-once effects, or forcibly stop synchronous work once
it has started in a worker thread. Risk and `SideEffect` labels remain metadata
unless trusted policy uses them to restrict access.

## Offline example

Run `uv run python examples/secure_tool_approval.py` from the repository root.
It demonstrates one approved in-memory write, a denied request, a replayed
trusted response, and sanitized diagnostics without network or credentials.
`examples/secure_tool_policy.py` remains the V01 grant/deny demonstration.
