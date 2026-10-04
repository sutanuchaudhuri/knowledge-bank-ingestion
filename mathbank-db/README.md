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
# P0 pedagogy authoring (explicit rollout)

Migration `sql/006_pedagogy.sql` adds `knowledge.skill`, `skill_concept`,
`skill_relation`, `problem_skill`, and `problem_pedagogy`. It contains no seeds.
No migration, authoring write, or graph projection runs implicitly.
P1 semantic solution steps, stored hint ladders, misconception models, and
versioned courses remain later work. Existing authenticated learner records
are separate from the anonymous P0 practice flow.

Author a JSON object with integer `version: 1` and optional arrays `skills`,
`skill_concepts`, `skill_relations`, `problem_skills`, `problem_pedagogy`.
Every row **requires** `source` (nonempty trimmed string), `confidence` (finite
0..1), and `review_status` (`PENDING`, `REVIEWED`, `REJECTED`).
Unknown fields, duplicate natural keys, booleans as numbers, and invalid bounds
are errors. Missing optional values become SQL NULL on upsert (replacement, not
a patch). An empty manifest `{"version":1}` is valid and makes no assertions.

| Section / SQL table | Required authoring fields | Optional fields / bounds | SQL unique key |
| --- | --- | --- | --- |
| skills / skill | slug, name, objective | level: integer 1..5 or null | slug (UUID skill_id retained) |
| skill_concepts / skill_concept | skill_slug, concept_slug | none | skill_id, concept_id |
| skill_relations / skill_relation | from_skill_slug, to_skill_slug, relation_type | none | from_skill_id, to_skill_id, relation_type |
| problem_skills / problem_skill | problem_code, skill_slug, relation_type, role, importance: 0..1 | required_level: integer 1..5 or null | problem_id, skill_id, relation_type, role |
| problem_pedagogy / problem_pedagogy | problem_code | conceptual_depth, technical_load, algebraic_load, insight_required: integer 1..5 or null; number_of_steps, prerequisite_depth: integer >=0 or null; estimated_contest_level: nonempty trimmed text or null | problem_id |

Skill relation types are exactly `PREREQUISITE_OF`, `PART_OF`, `BUILDS_ON`.
`PREREQUISITE_OF` means prior -> dependent; `PART_OF` means child -> parent.
Problem relation types are exactly `REQUIRES`, `PRACTICES`, `TESTS`; role is
lowercase `primary` or `supporting`. Skill/concept/problem references use exact
skill slugs, existing concept slugs, and existing `core.problem.canonical_code`;
the importer never creates a concept/problem or invents corpus annotations.

```sh
make -C mathbank-db pedagogy-validate MANIFEST=/absolute/path/authoring.json
# Operator-approved local rollout, when ready:
make -C mathbank-db migrate-pedagogy
make -C mathbank-db pedagogy-dry-run MANIFEST=/absolute/path/authoring.json
make -C mathbank-db pedagogy-import MANIFEST=/absolute/path/authoring.json
make -C mathbank-db project-pedagogy
```

`PEDAGOGY_PYTHON` defaults to the DB service `.venv/bin/python`;
`PEDAGOGY_GRAPH_PYTHON` defaults to the graph service `.venv/bin/python`.
Override to another existing dependency-equipped venv if needed.
The importer uses `PG_ENV_FILE` (default service `.env`)
and environment overrides, including existing `APP_*`/`PG_PORT` and `NEON_PG_*`
names. Offline validation does not connect. Import `--dry-run` uses a read-only,
repeatable-read transaction: FK and existing reviewed cycle checks, no DML,
locks, or migration. Actual import validates then upserts in one transaction,
locking the authoring/reference tables to serialize cycle checks. Errors roll
back the entire import. Reviewed prerequisite and hierarchy cycles are checked
against both manifest replacement rows and existing SQL edges; existing concept
`HAS_SUBCONCEPT` edges are reversed for hierarchy checks. Pending/rejected edges
are not treated as approved facts. Direct SQL writers must enforce the same
cycle policy (the DDL enforces FK/bounds/enums but does not install cycle triggers).
### Remote rollout and verified starter metadata

The app's Neon/AuraDB pair was migrated and populated explicitly on
2026-10-04. The version-controlled
[counting starter manifest](data/pedagogy/counting-foundations.v1.json) contains
6 measurable skills, 6 skill-concept links, 6 skill relations, 6 problem-skill
mappings, and 3 multidimensional assessments. It covers `AMC10_2005B_Q18`,
`AMC10_2007B_Q20`, and `AMC10_2005B_Q21`, not the whole corpus.

Every starter assertion is **PENDING**, with versioned assistant-draft source
and explicit confidence. Required levels and difficulty axes are proposals,
not calibrated or expert-reviewed ratings. Step counts and prerequisite-depth
estimates are intentionally absent. Human review is still required before
these assertions can drive reviewed tutoring recommendations.

```sh
# Inspect remote.env and verify it targets the same Neon/Aura pair as the app.
make -C mathbank-db pedagogy-validate MANIFEST=data/pedagogy/counting-foundations.v1.json
make -C mathbank-db migrate-pedagogy-remote
make -C mathbank-db pedagogy-dry-run-remote MANIFEST=data/pedagogy/counting-foundations.v1.json
make -C mathbank-db pedagogy-import-remote MANIFEST=data/pedagogy/counting-foundations.v1.json
make -C mathbank-db project-pedagogy-remote
```

The migration is transactional and repeatable. Repeated live import preserved
all row values and skill UUIDs. Existing corpus counts remained 5,960 problems
and 13,168 solutions. Original corpus classification provenance is projected
alongside the new metadata, without relabeling pending assertions as reviewed.

For subsequent authoring, preserve the previous manifest before importing.
An authoring rollback means re-importing that version and reprojecting, not
dropping the schema or deleting corpus data. Reject withdrawn assertions using
`REJECTED` and keep their provenance. Postgres import and Neo4j projection are
separate commits; do not certify new teaching coverage until both succeed.
The graph's owned pedagogical layer is replaced in one Neo4j transaction:
a failed replacement leaves the previous projection intact.

Opt-in integration tests use the app's configured databases:

```sh
cd mathbank-rest
MATHBANK_LIVE_PEDAGOGY_TEST=1 .venv/bin/pytest -q tests/test_pedagogy_live.py
```

These tests check the pending gate, execute real reviewed-path/practice queries
inside an **uncommitted, rolled-back** graph fixture, test SQL constraint
rollback, and deliberately fail a graph replacement to verify atomic rollback.
They never persist reviewed fixture assertions. Run only with explicit shared
database authorization; ordinary tests skip them.
