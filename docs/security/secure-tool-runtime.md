# Secure Tool Runtime Foundation (YANTRA-004-V01)

YANTRA-004-V01 adds a small in-process authorization layer to the bounded
YANTRA-003 agent loop. It enforces declared logical capability scopes at the
tool dispatch boundary while preserving `AgentRunConfig.tool_names` as a
separate, mandatory name allowlist. Registration, model output, and provider
tool schemas never create authority.

## Contracts

`PermissionScope` is a validated string identifier: 3–128 characters, lowercase
ASCII letters/digits, with dot, colon, underscore, or hyphen separators
between non-empty segments. For example: `filesystem.read`, `network.request`,
`process.execute`, and the existing compatible form `demo:read`. Wildcards and
implicit prefix matching are not supported; matching is exact. Every scope
declared by a tool must be granted (logical AND).

`ToolRiskLevel` classifies a registered tool as `low`, `medium`, `high`, or
`critical`. Risk is metadata, never a grant. `PolicyEffect` is `allow`, `deny`,
or `approval_required`. Approval-required decisions are non-executable because
V01 has no trusted approval mechanism. `PolicyDecision` carries only a safe
`PolicyReason` category; arbitrary evaluator text is not returned.

The application supplies a frozen per-run `PolicyContext` through
`AgentRunConfig.permission_context`:

```python
PolicyContext(
    granted_scopes={"filesystem.read"},
    denied_scopes={"filesystem.delete"},
    approval_required_scopes={"filesystem.write"},
    approval_required_risks={ToolRiskLevel.CRITICAL},
)
```

Explicit denials take precedence over grants. Missing required grants deny.
Scopes marked as requiring approval, or configured risk classifications,
return `approval_required` and do not execute. Risk alone never authorizes a
tool. Context and grants must come from trusted application configuration;
model names, call IDs, descriptions, and arguments are not passed to the
evaluator and cannot alter the context.

## Evaluation and dispatch

For each proposed invocation, the engine:

1. Checks the existing per-run tool-name allowlist. A name denial cannot be
   overridden by a scope grant or evaluator.
2. Resolves the registered `ToolDefinition` and reads its trusted required
   scopes and risk classification.
3. Checks explicit scope denials, requires every scope to be granted, and
   applies configured approval restrictions.
4. Calls the synchronous `PolicyEvaluator`. The injected evaluator may further
   deny or require approval; it cannot bypass the preceding authority checks.
5. Passes the resulting decision to `ToolExecutor`, which refuses to validate
   or invoke a handler unless the decision is `ALLOW`.
6. Validates arguments and proceeds through the existing timeout, execution,
   and output-validation path.

Eligible schemas are filtered using the same static checks, but advertisement
is only a usability feature: execution repeats authorization for every
individual call. Mixed batches are decided independently and in order. A
policy exception or invalid evaluator result fails closed with a safe category
and does not expose exception text.

Calling `ToolExecutor.execute()` directly without an explicit ALLOW decision
also denies execution. This is an in-process API boundary, not protection from
trusted Python code that can call a handler directly.

## Legacy compatibility

Existing YANTRA-003 tools without `permission_scopes` retain the previous
explicit-name-allowlist behavior when
`AgentRunConfig.allow_legacy_unscoped_tools` is enabled (the compatibility
default). The tool must still appear in `tool_names`; an empty allowlist denies
all tools. Applications can set the flag to `False` to deny unscoped tools.
This compatibility mode cannot satisfy a scoped tool's missing grants or
override a name-list denial. New tools should declare their required scopes.

Scoped tools are denied when `permission_context` is absent. A policy evaluator
without explicit run grants cannot authorize them.

## Deterministic example

Run `uv run python examples/secure_tool_policy.py` from the repository root.
The offline example runs the same registered scoped tool once with an explicit
grant and once without one; it reports one successful handler invocation and
one denial. It makes no network or credential requests.

## Limits and security boundary

- This is not a process or operating-system sandbox. Python tool handlers can
  perform any operation their process identity permits once invoked.
- Scopes are logical authorization checks; V01 has no filesystem, network, or
  process enforcement backend.
- There is no approval UI, trusted approval token, or approval lifecycle.
- Synchronous handlers execute in a worker thread and cannot necessarily be
  forcibly terminated after timeout or cancellation.
- Policy decisions do not provide durable run recovery or exactly-once
  external side effects.
- Risk labels and `SideEffect` classifications are metadata unless a trusted
  policy explicitly uses them as a restriction.
- V01 is a focused policy foundation, not a general-purpose policy language.

V02 should add the smallest trusted approval boundary needed for
`approval_required` decisions, including explicit binding to the tool call and
run context. It should not add UI or OS sandboxing until those interfaces and
threat boundaries are separately specified.
