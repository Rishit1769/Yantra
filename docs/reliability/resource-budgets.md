# Resource Budgets

Every run has finite wall-clock deadline, steps, provider calls, tool calls, concurrency, input/output bytes, and optional tokens/cost. Each child receives a conserved sub-budget; no child can increase aggregate allocation. Tools and workers have CPU, memory, process, storage, network, and response limits where supported. Budget exhaustion is a typed event and deterministic termination/suspension condition.

Token/cost estimates may be incomplete or provider-dependent; document unknown values and reserve conservatively. Enforce limits at the closest resource boundary rather than trusting the model. Metrics monitor utilization and rejected admission without unbounded label cardinality.
