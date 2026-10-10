#!/usr/bin/env bash
set -Eeuo pipefail

: "${YANTRA_DB:?YANTRA_DB must be set}"
: "${YANTRA_MIGRATOR_USER:?YANTRA_MIGRATOR_USER must be set}"
: "${YANTRA_MIGRATOR_PASSWORD:?YANTRA_MIGRATOR_PASSWORD must be set}"
: "${YANTRA_APP_USER:?YANTRA_APP_USER must be set}"
: "${YANTRA_APP_PASSWORD:?YANTRA_APP_PASSWORD must be set}"

# The official image runs this only when initializing an empty data directory.
# Identifiers are quoted; password is passed through psql's variable mechanism.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  <<'SQL'
\getenv db_name YANTRA_DB
\getenv migrator_user YANTRA_MIGRATOR_USER
\getenv migrator_password YANTRA_MIGRATOR_PASSWORD
\getenv app_user YANTRA_APP_USER
\getenv app_password YANTRA_APP_PASSWORD
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user')\gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'migrator_user', :'migrator_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'migrator_user')\gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', :'db_name', :'migrator_user')\gexec
GRANT CONNECT ON DATABASE :"db_name" TO :"app_user";
GRANT USAGE ON SCHEMA public TO :"app_user";
GRANT CREATE ON SCHEMA public TO :"migrator_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"migrator_user" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"migrator_user" IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO :"app_user";
SQL
