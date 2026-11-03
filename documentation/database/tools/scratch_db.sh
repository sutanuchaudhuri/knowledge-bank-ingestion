#!/usr/bin/env bash
# Throwaway PostgreSQL 18 cluster with every mathbank-db migration applied, used only to
# introspect the schema for documentation. Never touches the local dev cluster or Neon.
#   tools/scratch_db.sh up     # initdb in /tmp, apply mathbank-db/sql/0*.sql in order
#   tools/scratch_db.sh down   # stop and delete the scratch cluster
set -euo pipefail
B=${PG_BIN:-/opt/homebrew/opt/postgresql@18/bin}
T=${MBDOC_PGROOT:-/tmp/mbdoc_pg}
PORT=${MBDOC_PORT:-55439}
SQL_DIR="$(cd "$(dirname "$0")/../../../mathbank-db/sql" && pwd)"
case "${1:-}" in
  up)
    rm -rf "$T"; mkdir -p "$T"
    "$B/initdb" -D "$T/data" -U postgres --auth=trust >/dev/null
    "$B/pg_ctl" -D "$T/data" -o "-p $PORT -k $T -c listen_addresses=''" -l "$T/log" start >/dev/null
    "$B/psql" -h "$T" -p "$PORT" -U postgres -qc "create role mathbank_app login" -c "create role mathbank_admin login superuser"
    "$B/psql" -h "$T" -p "$PORT" -U postgres -qc "create database mbdoc"
    for f in "$SQL_DIR"/0*.sql; do
      "$B/psql" -h "$T" -p "$PORT" -U postgres -d mbdoc -v ON_ERROR_STOP=1 -q -f "$f" >/dev/null
    done
    echo "scratch db ready: MBDOC_DSN='host=$T port=$PORT user=postgres dbname=mbdoc'" ;;
  down)
    "$B/pg_ctl" -D "$T/data" stop -m fast >/dev/null || true; rm -rf "$T"; echo "scratch db removed" ;;
  *) echo "usage: $0 up|down"; exit 2 ;;
esac
