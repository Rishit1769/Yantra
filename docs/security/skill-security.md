# Skill and Plugin Security

Imported/generated skills are untrusted until schema validation, digest/provenance checks, permission review, compatibility validation, and explicit approval. Skill instructions are context, not privileged policy; declared permissions do not grant access. Executable skill code is disabled by default. Candidate generation never auto-publishes or escalates permissions.

Plugins can be executable and therefore treated as trusted code unless isolated. Require allowlisting, pinned dependencies, provenance, integrity checking, least-privilege credentials, resource limits, and revocation. Archive extraction must prevent traversal and symlink escape. A registry approval does not guarantee benign behavior; maintainers document residual risks.
