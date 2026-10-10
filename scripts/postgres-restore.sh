#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s path/to/backup.dump\n' "$0" >&2
  exit 2
fi

backup_file="$1"
if [[ ! -f "$backup_file" || ! -s "$backup_file" ]]; then
  printf 'Backup file is missing or empty.\n' >&2
  exit 2
fi

printf 'This restores into the configured YANTRA database and may overwrite objects.\n'
printf 'Type RESTORE to confirm: '
IFS= read -r confirmation
[[ "$confirmation" == RESTORE ]] || { printf 'Restore cancelled.\n'; exit 1; }

cd "$(dirname "$0")/.."
set -a
source ./.env
set +a

docker compose exec -T postgres pg_restore \
  --username="$YANTRA_MIGRATOR_USER" \
  --dbname="$YANTRA_DB" \
  --no-owner \
  --no-acl \
  --exit-on-error < "$backup_file"
printf 'Restore completed. Run application-level integrity checks before use.\n'
