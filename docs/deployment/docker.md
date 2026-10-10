# PostgreSQL Docker Deployment

`compose.yaml` defines PostgreSQL 16.13 Bookworm pinned by multi-architecture image digest, localhost-only port binding, a named persistent volume, an initialization hook for separate migration/runtime roles, SCRAM host authentication, health check, restart policy, resource limits, and bounded JSON log rotation. pgvector, Redis, the Prisma service, and YANTRA application are not deployed by this configuration.

## Prerequisites and safe setup

The repository has not been connected to the target host from this environment. The commands below are intended to be run after SSH access is restored. First inspect the host and existing Docker resources. Do not remove or recreate existing containers/volumes as a shortcut. If a prior `yantra_postgres_data` volume or container exists, stop and inspect it; do not run initialization expecting it to alter an existing database.

1. Copy the repository deployment files to a dedicated directory on the Ubuntu host.
2. Inspect `docker ps -a`, `docker volume ls`, `df -h`, `free -h`, and `docker system df`. If the named container or volume already exists, stop. Do not overwrite or delete it.
3. Copy `.env.example` to `.env`, generate independent high-entropy passwords locally, and set `chmod 600 .env`. Do not commit or paste `.env` contents into support logs.
4. Verify the intended port is free, disk has sufficient capacity, and Docker daemon is installed and healthy.
5. Validate with `docker compose config --quiet`, then start using `docker compose up -d` only after reviewing existing container/volume state.
6. Check `docker compose ps` and `docker inspect` health status. Confirm `docker port yantra-postgres` shows `127.0.0.1:<port>`, never `0.0.0.0` or a public address.

## Ubuntu host preparation commands

Run inspection first and retain the output for the deployment record:

```sh
uname -a
lsb_release -a
df -hT
free -h
lsblk -f
docker --version 2>/dev/null || true
docker compose version 2>/dev/null || true
docker ps -a 2>/dev/null || true
docker volume ls 2>/dev/null || true
```

If Docker Engine or Compose plugin is missing, follow Docker's official Ubuntu instructions at <https://docs.docker.com/engine/install/ubuntu/>. Configure Docker's official apt repository and install `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, and `docker-compose-plugin` only after reviewing the host's existing package/service setup. Do not remove existing Docker packages or data as an installation shortcut. Re-check daemon, volumes, disk, and existing services after installation.

The entrypoint initialization script executes only when PostgreSQL initializes an empty data directory. It creates a non-superuser migration role, assigns that role database ownership, grants it schema creation rights, and gives the separate runtime role connection/schema usage and DML defaults on migration-created tables/sequences. Compose environment variables do not rotate credentials in an already initialized volume. Role/database changes on existing data require a separately reviewed, authenticated SQL operation and a backup first.

## Access from the future Prisma service

The database is bound to host loopback. A Prisma service running directly on the same host connects to `127.0.0.1:<POSTGRES_HOST_PORT>`. A future service running in Docker must join the `yantra_db` network and use host `postgres`, port `5432`; it should not publish PostgreSQL publicly. Build runtime `DATABASE_URL` from secret injection and use the migration identity only in a controlled migration job. URL-encode reserved characters and do not expose expanded URLs in logs.

## Backup, retention, and restore

Use [`scripts/postgres-backup.sh`](../../scripts/postgres-backup.sh) for a PostgreSQL-native custom-format `pg_dump`. The default local destination is `./backups/`, mode-restricted, with 14-day local retention. This is not off-host protection: configure an encrypted, access-controlled off-host copy and an explicit retention policy before production use. Backups may contain sensitive data. The script reads `.env`, so protect the environment and backup directory.

Restore with [`scripts/postgres-restore.sh`](../../scripts/postgres-restore.sh) and an existing dump; it requires typing `RESTORE` because restore can overwrite database objects. Test restoration into a separate disposable PostgreSQL instance/database before treating a backup as verified. A backup is **not verified** until a restore succeeds and application-level integrity checks are recorded. Never point a restore test at the only production database.

Custom-format dumps should be restored with a compatible `pg_restore`. Prefer the same PostgreSQL major version for restoration; PostgreSQL generally supports logical dump portability across versions, but restore into a newer major is the safer upgrade direction and extensions/types may constrain compatibility. Review PostgreSQL's version-specific dump/restore guidance before major upgrades. A sample restore was tested on the configured staging host; see the [deployment report](yantra-postgresql.md#deployment-verification-report-2026-10-10). No automated restore schedule is configured.

The container uses Docker's `json-file` log driver with 10 MiB files and five rotations. Memory/CPU limits are 512 MiB and 0.5 CPU to constrain impact on this small host; these are not capacity guarantees. A named volume survives container recreation, but volume removal destroys data. Docker is not a complete sandbox boundary for hostile code.
