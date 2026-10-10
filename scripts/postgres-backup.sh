#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."
set -a
source ./.env
set +a

backup_dir="${YANTRA_BACKUP_DIR:-./backups}"
retention_days="${YANTRA_BACKUP_RETENTION_DAYS:-14}"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="$backup_dir/${YANTRA_DB}_${timestamp}.dump"
partial="${output}.partial"
umask 077

docker compose exec -T postgres pg_dump \
  --username="$YANTRA_APP_USER" \
  --dbname="$YANTRA_DB" \
  --format=custom \
  --no-owner \
  --no-acl > "$partial"
test -s "$partial"
mv "$partial" "$output"
find "$backup_dir" -type f -name '*.dump' -mtime "+$retention_days" -delete
printf 'Backup created: %s\n' "$output"
