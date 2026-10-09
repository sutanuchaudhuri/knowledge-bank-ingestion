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

### PostgreSQL 18 replacement (2026-10-08)

The user approved replacing the active local database from the remote Neon
snapshot, not creating a second app database. The new cluster lives under
`/Volumes/External/Developer/databases/postgres18/data`; the database remains
`mathbank`, with port 5433 after verified cutover. The PostgreSQL 16 cluster is
retained for rollback rather than deleted. The default database Makefile now
uses version 18; `PG_VERSION=16` explicitly selects the legacy cluster.

Exports are stored outside Git under
`/Volumes/External/Developer/databases/backups/2026-10-08-neon-snapshot/`:
`neon-full.dump` is the complete remote schema/data export, while
`local-mathbank-before.dump` preserves the previous local database.
Files/directories have restricted permissions because they include private
application/provider data. External object-store files are not included.

Local restore omits only the hosted `pg_session_jwt` extension and its comment;
the complete export retains these entries. Neon-managed authentication
services are not recreated by restoring their tables. PostgreSQL `vector`
is restored with the locally available pgvector version. Application REST/
agent connection settings remain remote; replacing the local database does
not silently redirect running applications or resume paid ingestion.

The PostgreSQL 16 layout and setup instructions below describe the legacy
cluster; current default lifecycle commands select PostgreSQL 18.

**Completed and verified:** PostgreSQL 18.6 now serves `127.0.0.1:5433/mathbank`.
Application-role TCP login works. Source/local table/view column inventories
match (1,405 columns compared), with matching key counts: 12,542 problems,
18,749 solutions, 7,814 original textbook steps, 146 REVIEWED route releases,
562 route steps, 2,810 hint rows and 18,756 compiler jobs. This is a point-in-time
copy, not continuous replication. Restoration used four workers and stopped
on errors; pgvector is locally 0.8.7 versus source 0.8.6.
`verification.json`, `SHA256SUMS` and the restore manifest accompany the backups.
The old PostgreSQL 16 server is stopped, its data retained. No paid generation
was restarted, and REST/agent remain pointed at the remote databases.

### Image and object-file export (2026-10-08)

User selected copying all referenced files locally without deleting remote
originals or changing application connections. The snapshot's companion
`backups/2026-10-08-neon-snapshot/assets/` contains:

- `runtime_objects/`: all **6 objects** from the configured private S3 bucket,
  retaining object keys for later filesystem-backend use.
- `repository_files/`: **1,230 distinct files** resolved from restored
  `core.problem_image.local_path`, `pedagogy.diagram.local_path` and
  `ingest.package_file` joined to its `content_package.source_root`.
- `manifest.json`: relative locations, sizes and SHA-256 hashes; **zero missing
  files**, **60,572,229 bytes** copied. All 1,236 files were independently
  rehashed after export. Provider SHA-256 metadata was checked where available.

The 989 problem-image and 250 textbook-diagram rows mostly referenced files
already on this machine, not S3. Deduplicated source/package references are
archived with their repository-relative directory layout. This is a private
backup, not a publicly served directory. Remote objects, local/remote SQL
references and REST settings are unchanged. Linked external problem/solution
URLs are not crawled: the export covers stored objects and referenced local
files, not arbitrary internet pages. No model calls were made.

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

### Full corpus pipeline (crawl → classify → export → ETL → graph → vector)

```
crawl-unmapped  → data/crawl/<level>/<question_id>/parsed.json  (AoPS text + images)
classify        → SQLite mathbank.db (concepts, question_taxonomy_maps)
export-classifications → CSV corpus mirror (topic_taxonomy.csv, technique_catalog.csv,
                          question_taxonomy_map.csv, question_technique_map.csv)
etl / etl-remote → Postgres (core.*, knowledge.*)
project / project-remote → Neo4j graph (TESTS, USES_TECHNIQUE, CONCEPT_RELATION edges)
vector-backfill-remote → Postgres search.* (representations, chunks, pgvector embeddings for hybrid RAG)
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

cd ../mathbank-db
make vector-backfill-remote              # remote Neon core.* -> search.* embeddings (idempotent; needs OPENAI_API_KEY)
```

`classify_crawled.py` writes new concepts/techniques and problem mappings
into **local SQLite only** — `scripts/export_classifications_to_csv.py`
(`make export-classifications`) is the bridge that makes them visible to
Postgres/Neo4j. It's append-only and keys off `Concept_ID`/`Technique_ID`/
`Mapping_ID` already present in each target CSV, so it's safe to re-run as
classification proceeds in batches — rerun it (then `etl-remote` then
`project-remote` then `vector-backfill-remote`) whenever you want the latest
classifications reflected remotely and searchable.

**`vector-backfill-remote` reprocesses the whole corpus every run, not just
new rows** — `embed_corpus.py backfill` queries ALL of `core.problem`/
`core.solution` (no "only rows without a representation yet" filter), and
the representation/chunk phase runs inside a single uncommitted transaction
until it finishes, so nothing in `search.*` changes until that entire pass
completes. On a corpus with ~19k problems+solutions, each needing 2 Neon
round-trips just for the representation step, expect this to take tens of
minutes even though most rows are already up to date (the row-level
`content_hash` check makes re-processing unchanged rows a no-op, but it's
still a full table scan + round-trip per row, not a skip). Check progress
via `pipeline.run` (`status='IN_PROGRESS'`, `run_type='EMBED_BACKFILL'`) —
`completed_items`/`expected_items` only populate once the job finishes, so
mid-run the only signal is "still IN_PROGRESS, started_at is X minutes ago."
Run `make vector-status-remote` afterward to confirm
`search.representation`/`search.embedding` counts now match
`core.problem`/`core.solution` counts.

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
- **Vector/RAG** (`mathbank-db/etl/embed_corpus.py`): representations are
  keyed on `(source_entity_type, source_entity_id, representation_kind,
  preprocessing_profile_id, content_hash)` — unchanged text re-processes as
  a no-op (`ON CONFLICT DO UPDATE` just re-marks it `ACTIVE`), changed text
  inserts a new row and marks the old one `SUPERSEDED`. Idempotent, but see
  the "reprocesses the whole corpus every run" performance caveat above.
