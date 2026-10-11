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
