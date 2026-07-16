#!/usr/bin/env bash
# Runs once on first container init (docker-entrypoint-initdb.d).
# Creates the extra "langfuse" database used by the self-hosted Langfuse
# service (profile "ai"), alongside the main POSTGRES_DB app database.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE langfuse'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec
EOSQL
