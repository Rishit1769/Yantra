# Backups

Production deployment must define encrypted backups, retention, access control, recovery point/recovery time objectives, and periodic restore drills before claiming operational readiness. Backups include PostgreSQL data and required artifact objects/keys with consistent references. Secrets are managed separately. Validate Prisma schema/migration compatibility during restore; coordinate point-in-time restore with external side effects because database rewind cannot undo tools.

Document data deletion expectations against backups and legal retention. Restore drills record measured results; no RPO/RTO is asserted until tested.
