# Ollama Integration (Design)

Candidate local inference adapter only; no integration is implemented. Capability and model metadata may vary by installed server/model. Treat local endpoints as network boundaries, restrict reachable hosts, normalize incomplete usage, and apply the same tool authorization and budgets as hosted providers. Local inference does not itself make prompts or outputs trusted.
