# Skill Manifest and `SKILL.md`

**Status: Proposed.** A skill package contains `skill.yaml` (manifest), `SKILL.md` (human-readable instructions), and optional static resources. No executable code is accepted by default.

```yaml
schema_version: "1"
name: "public-document-research"
version: "1.0.0"
summary: "Collect and summarize permitted public documents"
maintainers: ["team@example.invalid"]
tags: ["research", "web"]
capabilities:
  tools: ["web.fetch@^1"]
permissions: ["network:public-web"]
dependencies: []
compatibility:
  yantra_api: ">=1.0,<2.0"
resources:
  - path: "references/extraction.md"
    media_type: "text/markdown"
    sha256: "<computed digest in a real package>"
trust: "untrusted"
```

Example is illustrative and not an approved package. Manifest validation rejects path traversal, duplicate/unpinned dependencies in reproducible mode, unknown permission scopes, unsupported API ranges, undeclared executable artifacts, oversized resources, and digest mismatch. `SKILL.md` should describe purpose, triggers, bounded procedure, expected evidence/output, limitations, and safe handling; it is context, not privileged instruction. Approval is a separate registry state and cannot be encoded by package self-assertion. Immutable versions are content-addressed; changes publish a new version. See [skill versioning](../features/skill-versioning.md).
