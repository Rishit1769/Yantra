# Tool Contract

Tool registration is a developer/runtime operation, not a model operation. A tool exposes namespace/name/immutable version, description, JSON Schema input and output, executor, required permission scopes, side-effect class (`read_only`, `reversible`, `irreversible`, `unknown`), timeout, input/output byte limits, dependencies, and declared idempotency behavior.

Proposed Python shape:

```python
@tool(name="catalog.lookup", input_schema=LookupInput, permissions={"catalog:read"})
async def lookup(args: LookupInput, context: ToolContext) -> LookupOutput:
    ...
```

This is pseudocode, not an existing decorator. Runtime validates schema, principal, policy, approval requirement, limits, and exact version before dispatch. Model arguments never carry permission grants. Sync functions must execute in a bounded worker to avoid blocking the event loop. Outputs are validated, truncated/rejected by policy, and classified. Errors use stable categories and safe public messages; detailed diagnostics stay in protected telemetry. Idempotency is an adapter contract and cannot make arbitrary external effects exactly-once.
