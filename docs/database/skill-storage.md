# Skill Storage

Local filesystem registry is suitable for development and offline use; it requires path confinement, manifest validation, and explicit trust state. Shared registry stores immutable manifests/content digests, versions, ownership/provenance, permission declarations, dependencies, validation results, and approval/revocation state in PostgreSQL. Large resources may be external artifacts with digest and access controls.

Never treat database registration as permission grant. Imported skill content is untrusted; validation and review state are separate. Immutable version rows prevent silent mutation; revocation prevents future resolution but does not alter already pinned run snapshots. Deletion and retention policy includes resources, indexes, and backups.
