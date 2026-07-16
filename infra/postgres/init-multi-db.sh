#!/usr/bin/env bash
# Runs once on first container init (docker-entrypoint-initdb.d).
# Creates extra databases alongside the main POSTGRES_DB app database:
# - "langfuse": used by the self-hosted Langfuse service (profile "ai").
# - "logica_test": dedicated database for `make test` / pytest, kept isolated
#   from dev data since integration tests TRUNCATE domain tables per test.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE langfuse'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec
    SELECT 'CREATE DATABASE logica_test'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'logica_test')\gexec
EOSQL
