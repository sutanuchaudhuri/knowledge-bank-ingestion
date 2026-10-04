# Local databases — PostgreSQL + Neo4j on the external drive

> **As of 2026-10-03, the `mathbank-rest` service (and therefore mathbank-web)
> points at the REMOTE hosted stack by default** — Neon (Postgres + pgvector)
> and Neo4j AuraDB, not the local databases described below. See
> ["Remote (current) databases"](#remote-current-databases--neon--auradb)
> further down. The local setup below still works for offline dev/testing —
> just don't assume `mathbank-rest/.env` points at it without checking.

Both databases are free/open-source editions running **locally** on this Mac
(Apple Silicon, Homebrew `/opt/homebrew`), with all data stored on the
external APFS drive mounted at `/Volumes/External` — never on the internal
SSD and never inside this git repo.

```
/Volumes/External/Developer/databases/
├── postgres16/
│   ├── data/            # Postgres 16 cluster (PGDATA)
│   └── postgres.log
└── neo4j/
    ├── data/             # databases, dbms (auth), transaction state
    ├── logs/
    ├── import/           # LOAD CSV root
    └── transactions/
```

## Services

| Service    | Port(s)        | Admin user        | App user       | Database |
|------------|----------------|-------------------|----------------|----------|
| PostgreSQL | 5433 (TCP)     | `mathbank_admin`  | `mathbank_app` | `mathbank` |
| Neo4j      | 7687 (bolt), 7474 (http) | `neo4j` | — | (default `neo4j` db) |

Postgres listens only on `localhost`; the Unix socket uses `trust` auth
(convenient for local admin via `psql`), while TCP/host connections require
`scram-sha-256` (a password). Neo4j only binds locally by default and auth is
enabled.

## One-time bootstrap (idempotent — safe to re-run)

```bash
# 1. Postgres
cd mathbank-db
cp .env.example .env      # edit PG_SUPERUSER_PASSWORD / APP_DB_PASSWORD
make setup                # install -> initdb (on external drive) -> start -> create-db
make status

# 2. Neo4j
cd ../mathbank-graph
cp .env.example .env      # edit NEO4J_PASSWORD
make setup                # install -> configure (point conf at external drive) -> set-password -> start
make status

# 3. FastAPI connectivity test
cd ../mathbank-rest
cp .env.example .env      # must match the passwords above
make install
make test-connectivity    # pings both DBs directly, no server needed
make run                  # or: start the dev server and hit GET /health
```

Or from the repo root, using the delegating Makefile:

```bash
make db-setup
make graph-setup
make rest-install
make test-connectivity
```

## Day-to-day

```bash
make up         # start both databases
make down        # stop both databases
make db-status / make graph-status
```

## Notes / gotchas

- **Re-running `brew upgrade neo4j` or `brew reinstall neo4j` regenerates
  `neo4j.conf`** from the formula defaults, wiping the external-drive paths.
  Run `make -C mathbank-graph configure` again afterward.
- Postgres runs on port **5433**, not 5432, to avoid clashing with any other
  local Postgres (e.g. an Anaconda-bundled client was detected on PATH on
  this machine).
- All passwords live in gitignored `.env` files (`mathbank-db/.env`,
  `mathbank-graph/.env`, `mathbank-rest/.env`); `.env.example` files are
  committed with placeholders only.
- `make -C mathbank-db destroy` / `make -C mathbank-graph destroy` stop the
  server and **delete** the external-drive data directory — only for
  throwaway dev environments.

## Corpus data (schema + ETL + REST)

The `mathbank` Postgres database and the Neo4j corpus graph are populated
from the maths_corpus CSV mirror via:

```bash
cd mathbank-db    && make etl-venv && make etl       # Postgres schema + data
cd ../mathbank-graph && make etl-venv && make project  # Neo4j projection
cd ../mathbank-rest  && make install && make run       # REST API on :8000
```

See [mathematics_tutor_db_plan/00_implementation_progress.md](mathematics_tutor_db_plan/00_implementation_progress.md)
for the full schema-to-source mapping, row counts, and known gaps (full
problem statement text is not yet ingested — only metadata + source URLs).

## Remote (current) databases — Neon + AuraDB

The local databases above were migrated to hosted equivalents via
`pg_dump`/`pg_restore` (Postgres) and a full re-projection (Neo4j), with row
counts verified identical post-migration:

| | Local (this doc) | Remote (current default) |
|---|---|---|
| Postgres | `mathbank-db`, port 5433 | Neon (pooled, `sslmode=require`) |
| Neo4j | `mathbank-graph`, bolt://localhost:7687 | AuraDB (`neo4j+s://...databases.neo4j.io`) |

- **Credentials**: one consolidated file, `mathbank-graph/remote.env`
  (gitignored) — both the Neon Postgres and AuraDB Neo4j creds live there.
  `mathbank-rest/.env` and `mathbank-web/.env` are the files actually read by
  the running services; both now point at these remotes.
- **Re-running the graph projection against the remote stack**:
  `make -C mathbank-graph project-remote` (uses `GRAPH_ENV_FILE=remote.env`
  instead of the local `.env`).
- **Re-running the Postgres ETL against the remote stack**: see
  `mathbank-db/etl/load_corpus.py` — pass `PG_ENV_FILE=../mathbank-graph/remote.env`
  (or `make etl-remote`) to target Neon instead of the local cluster.
- **Rotate both passwords** in the Neon and Aura consoles — they were shared
  in plaintext over chat during migration and are not safe long-term as-is.
- GOTCHA: don't `set -a; source mathbank-graph/remote.env; set +a` in a
  terminal you'll keep using — the exported vars persist in that shell and
  silently override any `.env` file read by processes you later launch from
  it (pydantic-settings/python-dotenv give real env vars precedence over
  `.env` file values). Prefer `VAR=val command` scoped to one line, or open a
  fresh terminal.

### Full corpus pipeline (crawl → classify → export → ETL → graph)

```
crawl-unmapped  → data/crawl/<level>/<question_id>/parsed.json  (AoPS text + images)
classify        → SQLite mathbank.db (concepts, question_taxonomy_maps)
export-classifications → CSV corpus mirror (topic_taxonomy.csv, technique_catalog.csv,
                          question_taxonomy_map.csv, question_technique_map.csv)
etl / etl-remote → Postgres (core.*, knowledge.*)
project / project-remote → Neo4j graph (TESTS, USES_TECHNIQUE, CONCEPT_RELATION edges)
```

```bash
cd mathbank_data_ingestion
make crawl-unmapped LIMIT=3200           # AoPS problem/solution text + diagram images
make classify LIMIT=3200                 # OpenAI concept/technique tagging -> SQLite only
make export-classifications              # bridge SQLite -> CSV corpus mirror (idempotent)

cd ../mathbank-db
make etl-remote                          # CSV -> remote Neon Postgres (idempotent)

cd ../mathbank-graph
make project-remote                      # remote Neon -> remote AuraDB graph (idempotent)
```

`classify_crawled.py` writes new concepts/techniques and problem mappings
into **local SQLite only** — `scripts/export_classifications_to_csv.py`
(`make export-classifications`) is the bridge that makes them visible to
Postgres/Neo4j. It's append-only and keys off `Concept_ID`/`Technique_ID`/
`Mapping_ID` already present in each target CSV, so it's safe to re-run as
classification proceeds in batches — rerun it (then `etl-remote` then
`project-remote`) whenever you want the latest classifications reflected
remotely.

### Idempotency checks and balances

- **SQLite** (`mathbank.db`): every relevant table (`concepts`,
  `question_taxonomy_maps`, `questions`, `unmapped_questions`) has its
  natural ID as `PRIMARY KEY`, so `INSERT OR IGNORE`/`INSERT OR REPLACE`
  genuinely cannot duplicate a row.
- **`export-classifications`**: runs a duplicate-key audit on all four target
  CSVs both *before* writing (reports pre-existing corpus issues without
  blocking) and *after* (hard-fails with a non-zero exit if this run itself
  introduced a duplicate `Concept_ID`/`Technique_ID`/`Mapping_ID`).
- **Postgres** (`mathbank-db/etl/load_corpus.py`): every insert uses
  `ON CONFLICT (<natural key>) DO NOTHING/UPDATE` backed by a real `UNIQUE`
  constraint — duplicates are structurally impossible at the DB layer, not
  just app-logic-level. The concept/technique/mapping loaders report
  **true** insert counts (via `cursor.rowcount`) rather than counting every
  CSV row processed, so re-running `etl`/`etl-remote` gives an honest signal
  of how much was actually new vs. already present.
- **Neo4j** (`mathbank-graph/etl/project_from_postgres.py`): every node/edge
  write is a Cypher `MERGE` keyed on `canonical_id` (nodes) or the matched
  endpoint pair (edges) — also structurally idempotent, re-running
  `project`/`project-remote` never creates duplicate nodes or edges.

