# Local databases — PostgreSQL + Neo4j on the external drive

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

