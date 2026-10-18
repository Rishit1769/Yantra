# Tool Contract

Tool registration is a developer/runtime operation, not a model operation. A tool exposes namespace/name/immutable version, description, JSON Schema input and output, executor, required permission scopes, side-effect class (`read_only`, `reversible`, `irreversible`, `unknown`), timeout, input/output byte limits, dependencies, and declared idempotency behavior.

Proposed Python shape:

```python
@tool(name="catalog.lookup", input_schema=LookupInput, permissions={"catalog:read"})
async def lookup(args: LookupInput, context: ToolContext) -> LookupOutput:
    ...
```

This is pseudocode, not an existing decorator. YANTRA-003 implements typed
registration/execution and an explicit per-run name allowlist. YANTRA-004-V01
adds `ToolDefinition.permission_scopes` enforcement through an exact-match
`PolicyContext`; all declared scopes are required, and an empty name allowlist
still authorizes no tools. Existing unscoped tools retain an explicit legacy
compatibility mode. Registration does not grant permission, and execution
rechecks authorization independently from schema advertisement. This logical
policy is not a principal/tenant policy language, approval dispatcher, or OS
sandbox. Runtime validates schemas and arguments, executes sync functions in a
worker thread, and validates declared outputs; it does not implement
policy-based output truncation. Tool errors are structured observations, and
developer diagnostics expose only recognized safe error categories. Idempotency
is an adapter contract and cannot make arbitrary external effects exactly-once.
