# YANTRA PostgreSQL Deployment Runbook

## Scope and status

This runbook deploys only the PostgreSQL database container. It does not deploy the YANTRA runtime, Prisma persistence service, Redis, or pgvector. The repository includes `compose.yaml`, `.env.example`, initialization SQL wrapper, and PostgreSQL-native backup/restore scripts. A deployment was completed on `staging-vm` on 2026-10-10; the verification report below records observed results and known limitations.

## Host access and inventory

Connect through the approved SSH path when reachable; do not put a password on a command line. Prefer an SSH key or an interactive prompt. First collect `uname -a`, `lsb_release -a`, `df -hT`, `free -h`, `lsblk -f`, `docker --version`, `docker compose version`, `docker ps -a`, and `docker volume ls`. Record existing services, mounts, disk availability, memory, Docker versions, and firewall/provider network rules. Stop if `yantra-postgres` or `yantra_postgres_data` already exists; inspect and obtain explicit approval before changing existing data.

If Docker is absent, use the official Docker Engine for Ubuntu instructions: <https://docs.docker.com/engine/install/ubuntu/>. Install only missing Engine/Compose components from Docker's official apt repository. Do not remove existing volumes or containers. Confirm Compose plugin availability and that Docker daemon is enabled/running only after reviewing impact on the host.

## Deploy

Copy these files preserving paths: `compose.yaml`, `.env.example`, `infra/postgres/init/10-create-application-role.sh`, `scripts/postgres-backup.sh`, and `scripts/postgres-restore.sh`. Then run from the deployment directory:

```sh
test ! -e yantra-postgres
docker ps -a --format '{{.Names}}' | awk '$0 == "yantra-postgres" { found=1 } END { exit found }'
docker volume ls --format '{{.Name}}' | awk '$0 == "yantra_postgres_data" { found=1 } END { exit found }'
cp .env.example .env
chmod 600 .env
```

Edit `.env` with unique randomly generated admin, migration, and runtime passwords using a protected editor. Do not use a password shared in chat, shell arguments, command-line flags, or committed files. `.gitignore` excludes `.env`. Verify the chosen port is unused and the host has sufficient free space/memory for PostgreSQL plus other services. Compose defaults to localhost port 55432, with 512 MiB memory and 0.5 CPU limits.

Validate and start only after the inventory shows no conflict:

```sh
docker compose config --quiet
docker compose pull postgres
docker compose up -d
docker compose ps
docker inspect --format '{{.State.Health.Status}}' yantra-postgres
docker port yantra-postgres
```

Pinned image is `postgres:16.13-bookworm` with its OCI manifest-list SHA-256 digest in `compose.yaml`, not `latest`. Update only through a reviewed patch/upgrade plan and backup. Confirm `docker port` reports `127.0.0.1:55432` (or the configured localhost port), not a wildcard/public interface. Confirm host firewall/cloud rules do not expose the configured port. The published port is loopback-only; a future Compose-hosted Prisma service can use the private `yantra_db` network instead.

Authenticated checks without printing secrets:

```sh
docker compose exec -T postgres pg_isready -U "$POSTGRES_ADMIN_USER" -d "$YANTRA_DB"
docker compose exec -T postgres psql -U "$POSTGRES_ADMIN_USER" -d "$YANTRA_DB" -Atc 'SELECT current_database(), version()'
docker compose exec -T postgres psql -U "$POSTGRES_ADMIN_USER" -d "$YANTRA_DB" -Atc "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname IN ('$YANTRA_MIGRATOR_USER', '$YANTRA_APP_USER')"
```

Do not use `set -x`, print environment values, or place passwords in command arguments. Verify migration and application role access with `psql` inside container, prompting securely; a safe automated verifier should use a protected `PGPASSFILE` with mode 0600 or a secret manager, never `PGPASSWORD` in shell tracing. Test `SELECT 1`, `current_user`, and `current_database()`. Confirm both roles have `rolsuper=false`; only the migration role owns the database/schema. Never use `docker compose down -v`.

## Persistence verification

Record the named volume mount from `docker inspect`. To prove persistence safely, create a uniquely named marker table/row in the YANTRA database as the application role, then recreate only the container (`docker compose up -d --force-recreate postgres`) after confirming the volume mapping and that no migration/update is in progress. Verify the marker remains and remove only that test marker. Do not delete the volume. Container recreation is not an upgrade and must not change the volume.

## Future Prisma connection

For a Prisma service on the same host, use host `127.0.0.1`, configured host port, database `yantra`, and role `yantra_app` for runtime. If Prisma runs as another Compose service, attach it to `yantra_db` and use host `postgres`, port `5432`. The `yantra_migrator` role owns the database and is used only by a controlled Prisma Migrate job; it is not the runtime identity. Inject secrets at runtime; do not commit a `DATABASE_URL`. URL-encode credentials. Prisma Migrate runs only from a controlled deployment job, not every service replica.

## Backups and restore drills

Run `scripts/postgres-backup.sh` daily via a protected scheduler. It uses `pg_dump --format=custom --no-owner --no-acl`, stores under `backups/`, applies 14-day local retention, and sets restrictive directory/file modes. Local backups on the same disk do not protect against disk/server loss. Copy encrypted backups off-host to access-controlled storage with a separately selected retention policy (suggested starting policy: 14 daily, 8 weekly, 12 monthly; confirm applicable privacy/legal needs). Restrict access and test backup integrity.

Restore with `scripts/postgres-restore.sh <dump-file>` only after confirming the target is a disposable restore-test database or an approved recovery target. Script demands typing `RESTORE`. Prefer a separate instance with the same PostgreSQL major version, then run schema/application integrity checks. Record timestamp, dump checksum, source server/image version, target version, restore duration/result, and validation result. A backup is not verified until this restore drill succeeds. A major-version upgrade requires separate compatibility testing; use matching `pg_dump`/`pg_restore` major where practical and review official PostgreSQL upgrade guidance.

## Report template

Record Docker Engine/Compose versions, host OS/kernel, PostgreSQL image digest and server version, health, authenticated admin/app-role checks, database existence, volume name/mount, persistence-marker test, published address/firewall review, disk/memory before and after, backup file/checksum, restore test status, and any changed services. Redact secrets. Unknown/unperformed checks must be marked **Not verified**, not passed.

## Deployment verification report (2026-10-10)

- Host: `staging-vm`, Ubuntu 26.04 LTS, kernel `7.0.0-38-generic`.
- Existing Docker Engine 29.1.3 and Compose v5.4.0 were used; no software packages were installed.
- YANTRA container: PostgreSQL 16.13 Bookworm, pinned by OCI manifest-list digest in Compose; healthy after startup/recreation; restart policy `unless-stopped`.
- Bind: `127.0.0.1:55432 -> 5432/tcp` only for `yantra-postgres`.
- Storage: named volume `yantra_postgres_data` mounted at `/var/lib/postgresql/data`; no existing volume was reused or removed.
- Database `yantra` exists. Runtime role authenticated over TCP/SCRAM, can connect and use `public`, has DML access to the migration-created probe table, is not a superuser, and cannot create schema objects. The separate migration role is non-superuser and owns the database.
- Persistence: a temporary marker survived `docker compose up -d --force-recreate postgres`; the test table was then removed.
- Backup/restore: created a custom-format PostgreSQL dump and restored it successfully into a temporary validation database; marker data matched. The temporary validation database was removed. A sample backup remains in the host's ignored `backups/` directory. This verifies one restore test, not an ongoing backup service.
- Resources: root filesystem reported 6.4 GiB free before pull and 5.8 GiB immediately after pull (88% used); container is limited to 512 MiB and 0.5 CPU. Continue monitoring disk and memory; database growth is not quota-limited.
- Existing services: the deployed YANTRA database is separate. No existing containers or volumes were intentionally modified or removed.
- **Security finding:** pre-existing container `prometheus-postgres` remains published on `0.0.0.0:5432` and `[::]:5432`. It was not changed to avoid disrupting another service. This deployment confirms only that the new YANTRA container is loopback-bound; it does not establish that the host has no publicly reachable PostgreSQL service. Review firewall/cloud exposure and remediate the pre-existing binding in a separately approved change.
- Not configured: scheduled backups, encrypted off-host backup replication, restore drill automation, firewall changes, or an automated capacity alert. The provided backup script and retention behavior require an operator scheduler and off-host policy.
- Credentials: generated randomly on the host and stored only in `/home/rishit/yantra-postgres/.env` with mode `0600`; values are intentionally not reported. Rotate the SSH password shared in the conversation and prefer key-based SSH.
