# ADR 0011: Skills as Versioned Content Packages

- Status: Proposed
- Context: Reusable procedures need instructions/resources/metadata distinct from executable tools.
- Decision: Skill is immutable versioned content with manifest, `SKILL.md`, resources, dependencies, and declared capabilities; code is disabled by default.
- Alternatives: Skills as prompt strings; executable bundles; tools only.
- Consequences: Reviewable portable reuse and provenance; registry/validation/compatibility required.
- Tradeoffs: Human review reduces automatic convenience; skill permissions never grant authority.
