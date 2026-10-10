# ADR 0002: Custom Agent Kernel

- Status: Proposed
- Context: Framework needs authoritative state, policy, recovery, and model-neutral behavior.
- Decision: Build a small custom orchestration kernel; do not use LangChain, CrewAI, AutoGen, or LangGraph for core logic.
- Alternatives: Adopt one framework; wrap several; delegate loop to provider SDK.
- Consequences: Direct control and smaller dependency surface; YANTRA must implement and test semantics itself.
- Tradeoffs: Higher initial engineering burden for explicit contracts and replaceability.
