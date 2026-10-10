# Quickstart (Proposed)

This is a shape of the intended API only; none of the symbols currently exist.

```python
# Proposed pseudocode; not executable against this repository.
provider = Provider.from_config(config)
agent = Agent(name="researcher", instructions="Cite evidence", tools=[fetch_page])
async with Runtime(provider=provider) as runtime:
    result = await runtime.run(agent, "Summarize the public project page")
```

A publishable quickstart must include actual installation, credential setup through an environment/secret provider, tool permission configuration, bounded budgets, expected output, and a test command. It must not use real secrets or imply all providers support the same tool features.
