# mathbank-db

Postgres (`core.*`/`knowledge.*`/`search.*`/`pipeline.*`/`learner.*`) ETL and
schema management for the MathBank competition-math corpus — the local
PostgreSQL 16 + pgvector cluster, and the pipelines that load the CSV corpus
mirror into it, project it into Neo4j, and embed it for hybrid RAG search.

This directory owns the Postgres **schema** (`sql/*.sql`) and **load/embed
pipelines** (`etl/*.py`); it does not serve traffic — that's `mathbank-rest`.
See root [DATABASES.md](../DATABASES.md) for the full local-vs-remote
(Neon/AuraDB) picture and [GOTCHAS.md](../GOTCHAS.md) for environment
troubleshooting.

## Quick start (local cluster)

```bash
cp .env.example .env             # then edit the passwords
make install init start create-db status
make migrate migrate-vector migrate-learner migrate-admin migrate-student-names
```

## The full corpus pipeline

```
crawl-unmapped (mathbank_data_ingestion) → classify → export-classifications
  → etl-remote (this repo, Postgres core.*/knowledge.*)
  → project-remote (mathbank-graph, Neo4j TESTS/USES_TECHNIQUE/CONCEPT_RELATION)
  → vector-backfill-remote (this repo, Postgres search.* — representations/chunks/embeddings for hybrid RAG)
```

```bash
# After a new crawl/classify/export-classifications batch lands:
make etl-remote                   # CSV corpus mirror -> remote Neon Postgres (idempotent)

cd ../mathbank-graph && make project-remote   # Neon -> AuraDB graph (idempotent)

cd ../mathbank-db && make vector-backfill-remote   # Neon core.* -> search.* embeddings (idempotent, needs OPENAI_API_KEY)
```

Full command reference and idempotency guarantees for every stage:
[DATABASES.md § Full corpus pipeline](../DATABASES.md#full-corpus-pipeline-crawl--classify--export--etl--graph--vector).

### Vector/RAG commands (`etl/embed_corpus.py`)

| Command | What it does |
|---|---|
| `make vector-backfill` / `vector-backfill-remote` | Build `search.representation` + `search.chunk` rows from `core.problem`/`core.solution`, then call OpenAI (`text-embedding-3-small`) for any chunk missing an embedding. `LIMIT=N` for a small test batch. |
| `make vector-index` / `vector-index-remote` | Create the HNSW index for the active embedding model. |
| `make vector-status` / `vector-status-remote` | Print representation/chunk/embedding counts — run this after a backfill to confirm coverage matches `core.problem`/`core.solution` row counts. |

**Known performance characteristic**: `backfill` reprocesses every row in
`core.problem`/`core.solution` on every run (not just rows without a
representation yet), and the representation/chunk-building phase runs
inside a single uncommitted transaction until it finishes — so on a large
corpus this can take tens of minutes even when most rows are already
up to date, and nothing in `search.*` changes until that whole pass
completes. Check progress via Postgres directly, not the log (progress
counters only populate once the job finishes):

```sql
SELECT run_type, status, started_at, completed_items, expected_items
FROM pipeline.run WHERE run_type = 'EMBED_BACKFILL' ORDER BY started_at DESC LIMIT 1;
```

`status = 'IN_PROGRESS'` with no `completed_items` yet just means it's still
working — not stuck. `make vector-status-remote` once it finishes is the
source of truth for whether the new corpus batch is now searchable.

## Schema migrations (`sql/*.sql`)

| File | `make` target(s) | Covers |
|---|---|---|
| `001_schema.sql` | `migrate` / `migrate-remote` | `core.*`, `knowledge.*` — competitions, papers, problems, concepts, techniques |
| `002_vector_schema.sql` | `migrate-vector` | `search.*` — representations, chunks, embeddings, embedding_model |
| `003_learner_schema.sql` | `migrate-learner` / `migrate-learner-remote` | `learner.*` — student accounts, attempts, mastery |
| `004_admin_pipeline.sql` | `migrate-admin` / `migrate-admin-remote` | `pipeline.pdf_source.source_kind`, admin-registered paper tracking |
| `005_student_profile_names.sql` | `migrate-student-names` / `migrate-student-names-remote` | `learner.student_profile.first_name`/`last_name` |

Every migration is an idempotent `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN
IF NOT EXISTS` — safe to re-run.

## Local vs. remote

Every pipeline/migration command has a local variant (runs against the
Postgres cluster this repo manages on `$(PG_PORT)`) and a `-remote` variant
(targets the Neon Postgres in `mathbank-graph/remote.env` via `PG_ENV_FILE`
or `NEON_PG_*` env vars). Production/demo data lives on Neon — see
[DATABASES.md](../DATABASES.md) for when each is appropriate.
