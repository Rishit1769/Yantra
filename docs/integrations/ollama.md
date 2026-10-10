# Ollama Integration (YANTRA-002)

The Ollama adapter is implemented for loopback HTTP and HTTPS endpoints, with normalized completion/streaming, tool calls, usage, model listing, and typed errors. Current protocol tests use mocked HTTP only; live compatibility is unverified. Capability and model metadata vary by installed server/model. Restrict reachable hosts, normalize incomplete usage, and apply the same tool authorization and budgets as hosted providers. Local inference does not make prompts or outputs trusted.
