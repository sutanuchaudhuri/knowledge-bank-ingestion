---
name: mathbank-db
description: 'Working in mathbank-db: PostgreSQL 16 + pgvector schema migrations and ETL scripts. Use when adding a SQL migration under sql/, editing an etl/*.py script, or asked about table/column/constraint details.'
argument-hint: 'Optional: migration number or etl script name to focus on'
---

# mathbank-db conventions

Full detail: [mathbank-db/README.md](../../../mathbank-db/README.md). The authoritative schema
reference is [documentation/requirements/reference/POSTGRES_SCHEMA.md](../../../documentation/requirements/reference/POSTGRES_SCHEMA.md)
and [POSTGRES_DML.md](../../../documentation/requirements/reference/POSTGRES_DML.md) — regenerate
those (via the **update-architecture-docs** skill) after a schema change, don't hand-maintain a
second copy of the schema in prose.

## Non-negotiables

- Migrations are sequential and numbered (`sql/NNN_*.sql`, 35 today) — never renumber or reorder an
  already-applied one; add a new file.
- `mathbank-rest` is the only runtime reader/writer of this schema — this project only migrates
  and ETLs, it never serves live traffic.
- ETL scripts read crawled source data from `mathbank-data-ingestion/data/` via hardcoded relative
  path strings (`INGESTION_ROOT`/`REPO_ROOT` + `"mathbank-data-ingestion"`) — if that sibling
  project's folder is ever renamed, grep every `etl/*.py` and `tests/test_*.py` here for the
  literal old name first; this exact class of bug (a bare-quoted-string path reference with no
  trailing slash) is easy to miss with a naive `grep "foldername/"` search.

## Before changing anything

1. `mathbank-rest/.venv/bin/python -m pytest -q mathbank-db/tests` (35 files) — some require
   explicit shared-database authorization and run against a real, rolled-back transaction; don't
   assume they're skipped by accident if they don't run locally.
2. Check [documentation/requirements/20_NOT_YET_IMPLEMENTED.md](../../../documentation/requirements/20_NOT_YET_IMPLEMENTED.md)
   for open v2-pack phases before assuming a gap is new.
3. [documentation/requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md](../../../documentation/requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md)
   documents several schema gaps (unenforced CHECK constraints, missing alias tables) that would
   need a new migration here if ever implemented — read it before designing one independently.

## Known pitfalls

- **One-row-at-a-time INSERT/UPDATE against Neon is catastrophically slow at scale.** Confirmed
  live: a naive per-row backfill loop (fetch id, `INSERT ... RETURNING`, repeat) measured at
  ~4 minutes per 1,000 rows — a 70,018-row backfill would have taken 4+ hours. The fix used in
  [mathbank-rest/scripts/backfill_misconception_catalog.py](../../../mathbank-rest/scripts/backfill_misconception_catalog.py)
  cut the identical workload to **under 90 seconds** (and a later, larger full-corpus dry run to
  ~28 seconds of pure Postgres read time) via two independent changes, both reusable for any
  future large backfill in this codebase:
  1. **Compute ids deterministically client-side** with `uuid.uuid5(fixed_namespace, canonical_key)`
     instead of letting Postgres generate them — this removes the need for a `RETURNING` round
     trip per row, since the caller already knows every id before issuing any SQL.
  2. **Batch multiple rows into one `INSERT ... VALUES (...), (...), ...` statement** (a few
     hundred to a couple thousand rows per statement, not per row), with globally-unique
     parameter-name suffixes per row (e.g. `:mid_0`, `:mid_1`, ...) rather than one round trip per
     row. The network round-trip latency, not server-side write throughput, is the actual
     bottleneck at this project's scale against a remote Neon instance — batching amortizes it.
- **A route re-projection succeeding does not guarantee its advisory-lock cleanup succeeds.**
  Neon has transiently killed the dedicated non-pooled connection used for
  `pg_advisory_lock`/`pg_advisory_unlock` in `mathbank_rest.route_projection.project()` with
  `psycopg.errors.AdminShutdown` *after* the real work completed and was already recorded as
  `COMPLETED` in `pipeline.graph_projection` — confirmed live twice. Don't assume a traceback from
  this function means the projection itself failed; check `pipeline.graph_projection` (by
  `started_at DESC`) for the actual `status`/`nodes_upserted`/`edges_upserted` before concluding
  anything was lost.
