# Message Schema

Messages are ordered typed content blocks with role (`system`, `developer`, `user`, `assistant`, `tool`), optional tool-call/result linkage, source/provenance, trust label, creation time, and schema version. Blocks may represent text, structured JSON, image references, tool proposals, or tool results; binary payloads use bounded references, not arbitrary inline blobs.

Provider-specific fields belong in a namespaced extension map with size limits and redaction rules. Tool arguments are untrusted JSON validated against the registered schema; tool results are untrusted observations. Tool results must link to exactly one tool execution ID, and provider response IDs are not authorization. Unknown major schema versions fail closed; unknown optional fields are ignored only if policy permits.

An assistant message may have no visible text when it contains tool calls or non-empty namespaced `reasoning_content`. Reasoning stays in provider metadata and is never promoted to user-facing text; a truly empty message without such structured content remains invalid.
