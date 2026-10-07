# mathbank-db

### Retrying a repaired source during an active backlog

Use the batch runner's `--resume RUN_UUID --paper PAPER_CODE --wait-for-lock`
to queue a narrowly scoped retry. Multiple `--paper` options are supported,
but each must belong to the original run snapshot. The retry waits on the same
Postgres advisory lock as the main runner, so classification/export/graph
publication do not race. Already completed papers are skipped. Failed history
and logs remain; the retry increments attempts and only reports completion
after exact Postgres/Neo4j verification.

For SMT 2019 tiebreakers, the official archive's problem filenames are
`{subject}-tiebreaker.pdf`, not `{subject}-tiebreaker-problems.pdf`.
The five registered source URLs were corrected after official PDF validation.

Batch runners use Neon's direct endpoint (remove `-pooler` from the configured
Neon host) for session-scoped advisory locks. Transaction-pooled connections
cannot reliably hold these locks. A legacy already-running pooled runner must
exit before launching a new retry worker; merely acquiring a lock is not
evidence that the legacy process has stopped.

Official SMT 2004 sources include PostScript (`.ps`) for problems and solutions.
The crawler converts these with Ghostscript (`gs`, required for these sources),
logs the conversion, and validates PDF magic bytes before parsing. Conversion
failure is explicit and does not mark a paper complete.

The 2026-10-04 recovery validated all 15 failed SMT source pairs against the
official archive and parsed 157 nonempty, consecutive question artifacts.
This is parse evidence, not completed classification or graph publication.
Seven 2019 exam links use `-exam.pdf`; five tiebreakers omit `-problems`;
2014 Power uses `thuemorse-{problems,solutions}.pdf`. Native extraction warnings
remain visible and require formula/figure quality review.

The splitter now selects headings in forward consecutive order. Premature
numeric lines inside a question cannot create backwards/empty blocks (the
2004 General paper contained a false `15.` line inside question 10).

Postgres (`core.*`/`knowledge.*`/`search.*`/`pipeline.*`/`learner.*`) ETL and
schema management for the MathBank competition-math corpus — the local
PostgreSQL 16 + pgvector cluster, and the pipelines that load the CSV corpus
mirror into it, project it into Neo4j, and embed it for hybrid RAG search.

This directory owns the Postgres **schema** (`sql/*.sql`) and **load/embed
pipelines** (`etl/*.py`); it does not serve traffic — that's `mathbank-rest`.
See root [DATABASES.md](../DATABASES.md) for the full local-vs-remote
(Neon/AuraDB) picture and [GOTCHAS.md](../GOTCHAS.md) for environment
troubleshooting. The source-derived composite schema, SQL behavior, and API
contracts are in the [canonical implementation references](../requirements/reference/README.md);
the current schema includes migrations 021/022, but reference documentation
does not verify that either migration is applied to a database target.

## Quick start (local cluster)

```bash
cp .env.example .env             # then edit the passwords
make install init start create-db status
make migrate migrate-vector migrate-learner migrate-admin migrate-student-names
```

## The full corpus pipeline

### Repairing missing AMC/AIME text and vectors

Concept mapping and source-text ingestion are separate completion states.
The old unmapped-only crawler skipped already-mapped questions whose statements
were still placeholders. `crawl_unmapped.py --missing-text` now selects those
questions independently and persists source text without changing classification,
concept mappings, diagrams or existing reviewed solution/answer fields.

From the repository root:

```sh
# Read-only Neon audit; compares ACTIVE statement representations with current text.
make -C mathbank-db repair-question-text-remote
# REPORT paths are relative to mathbank-db, since make changes directory.
make -C mathbank-db repair-question-text-remote \
  REPORT=../mathbank_data_ingestion/data/question_text_gaps.json
# After source access is available: bounded, non-AI crawl. Stops on publisher blocking.
make -C mathbank_data_ingestion crawl-missing-text LEVEL=AIME LIMIT=20 DELAY=10
# Import validated local sources into Neon; no model calls or reclassification.
make -C mathbank-db repair-question-text-apply-remote
# Optional original-page bundle: JSON array of {code,url,status,html}.
# Every entry must be in the selected inventory, have its exact recorded URL,
# HTTP 200 and a nonempty Problem section; all entries are validated before writes.
make -C mathbank-db repair-question-text-apply-remote \
  SOURCE_BUNDLE=../mathbank_data_ingestion/data/source_text_batch.json
# Build search representations/chunks without paid embedding requests.
make -C mathbank-db vector-build-remote PAPER=AIME_1983
# Paid, explicitly scoped backfill. Refuses the request if its conservative
# $1/million-token input-cost ceiling exceeds the per-invocation cap.
make -C mathbank-db vector-backfill-remote PAPER=AIME_1983 MAX_COST_USD=20
```

The CLI supports repeated `--paper` and `--competition` options. The budget is
per invocation, not an account-level or cumulative spending limit. Empty and
placeholder statements are never embedded. Existing valid statements/solutions
are preserved; missing originals are not generated by AI.
Apply-mode coverage describes the pre-write snapshot; rerun the read-only audit
after import and embedding to verify persistent results.

Latest verified repair: 22 AIME statements restored from original source pages;
122 statement/solution chunks embedded, zero failures, 33,946 input tokens and
a conservative $0.033946 cost ceiling (not an actual billing report).
All restored statements have current vectors. **517 statements remain missing**:
AIME 330, AMC10 76, AMC12 111. The source batch stopped on HTTP 429;
do not bypass publisher verification or repeatedly retry blocked sources.
Obtain authorized source PDFs/exports or wait for source access before continuing.
No graph publication, broad re-enrichment or schema migration is needed for this repair.

### Question-specific PDF figure repair

PDF diagrams must be cropped to the individual question's figure, not displayed
as whole pages. The ingestion-owned shared cropper uses spatial question boundaries and keeps
solution images separate. Ambiguous/incomplete layouts are logged, never
assigned proportionally. See [requirements 31](../requirements/31_QUESTION_SPECIFIC_DIAGRAMS.md).

```sh
# From the repository root; dry-run, no OCR/AI calls.
make -C mathbank_data_ingestion repair-diagrams
# Repair artifacts and existing SQLite staging metadata before importing manifests:
make -C mathbank_data_ingestion repair-diagrams-apply
PG_ENV_FILE=mathbank-graph/remote.env mathbank-db/.venv/bin/python \
  mathbank-db/etl/backfill_question_figures.py --paper PAPER_SMT_2010_GEOM
# Add --apply only after reviewing the selected source/crop.
```

The compatibility entry point `backfill_problem_images.py` now runs the
question-figure repair too. It no longer imports whole problem-page references.
The backfill also reconciles AoPS problem/solution provenance when no `--paper`
filter is supplied. Source manifests are authoritative, including verified empty
inventories; re-imports prune stale references only within the matching source
family. Native/textbook assets are not blindly replaced.
Student image endpoints refuse historic whole-page paths, unknown legacy
provenance and solution/answer images. This does not certify every imported PDF
layout or fill inaccessible downloads. No schema migration or model calls are involved.

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

### Resumable SMT/HMMT paper batches

The Postgres-driven runner reads registered PDF sources for `SMT`, `HMMT_FEB`,
`HMMT_NOV`, and `HMMT_INV` only. It does not depend on the older SQLite
`unparsed_papers` queue, and does not process CMM or auto-approve classifications.

```sh
# Paid model calls: explicitly authorize scope/cost and configure OPENAI_API_KEY first.
make -C mathbank-db paper-batches-remote BATCH_SIZE=5
# Bounded execution:
make -C mathbank-db paper-batches-remote BATCH_SIZE=2 LIMIT=2
# Resume failed/interrupted stages from the ORIGINAL snapshot, including papers
# already ingested but not yet classified/projected. Obtain UUID from /admin.
make -C mathbank-db paper-batches-remote BATCH_SIZE=5 RESUME=<run-uuid>
```

`PAPER_BATCH_PYTHON` defaults to the REST virtualenv (psycopg + Neo4j);
download/parse/classification subprocesses use the ingestion virtualenv.
Both `PG_ENV_FILE` and `GRAPH_ENV_FILE` must explicitly target the app's
Neon/Aura pair. The runner snapshots pending papers, takes a session advisory
lock to prevent duplicate runners, and processes a finite queue in batches.

For each paper: download and parse, validate nonempty contiguous numbered
questions and any registry-provided expected count, split artifacts, ingest
only verified question IDs, classify using the configured paid model, and
verify SQLite classification coverage. Each successful batch exports only its
paper mappings, loads Postgres concept/technique assertions, projects the corpus
and existing pedagogy, and checks that every classified problem has a graph
classification edge. `COMPLETED` is written only after that graph check.
Downloaded solutions may be unavailable; inspect solution counts and extraction
warnings rather than assuming every problem has a solution.

CPU extraction and an external-drive temporary directory are used for batch
children to avoid filling the Mac system volume with Apple GPU compilation
files. A rejected Docling parse gets one explicitly logged native-text retry,
subject to the same strict validation. Native text and figure associations
still require human quality review; no extraction method guarantees mathematical
fidelity. Failed sources remain explicit failures, not successful empty papers.

`pipeline.run` stores run UUID, original scope, heartbeat, completion/failure
counts and log directory. `pipeline.work_item` stores per-paper stage, attempts,
classification/graph status, warnings and errors. Detailed stage logs and
source manifests are under `mathbank_data_ingestion/logs/paper_batches/`.
The authenticated `/admin` dashboard refreshes every 15 seconds, has paper
pagination, and exposes classification and graph completion separately from
download/parse/ingest. `NOT_TRACKED` means no end-to-end batch evidence exists,
not a declaration that legacy classifications are missing.

New concept/technique assertions remain **PENDING** in Postgres and graph.
Existing reviewed pedagogical assertions are preserved. Embedding/vector
backfill is a separate paid operation, not included in paper-batch completion.
Graph web caches may take up to five minutes to reflect CLI publications.
Coordinate external projection with admin pedagogical publication.

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
| `010_textbook_import.sql` | `migrate-textbook-import-remote` | `ingest.*` package/staging/conflict/reconciliation; `pedagogy.*` taxonomy bridge, solution parts/steps/dependencies, learning items, diagrams |
| `011_step_vector_metadata.sql` | `migrate-step-vector-remote` | `search.*` step / learning-item chunk metadata (skill, subconcept, step type, …) and filter indexes for Phase 5 retrieval |
| `012_step_runtime.sql` | `migrate-step-runtime-remote` | `learner.solve_attempt`, `attempt_step_state`, append-only `learner.event`, `idempotency_record`; `tutor.runtime_state`; `pipeline.outbox_event`/`outbox_consumption` |
| `013_step_hints.sql` | `migrate-step-hints-remote` | `pedagogy.step_hint` — generated hint text cached per step, level (1–4) and prompt version |
| `014_gap_diagnosis.sql` | `migrate-gap-diagnosis-remote` | `pedagogy.gap_diagnosis` and ranked `pedagogy.knowledge_gap` hypotheses (Phase 9); adds `GAP_DIAGNOSED` / `GAP_HYPOTHESIS_RESOLVED` to the `learner.event` type CHECK |
| `015_recovery_runtime.sql` | `migrate-recovery-remote` | `pedagogy.recovery_plan` / `recovery_plan_item` (Phase 10 detours), `learning_item.approval_method`/`approved_at`, `gap_diagnosis.ai_rerank`, recovery FKs on `solve_attempt`/`runtime_state`, `RECOVERY_*` event types |
| `016_agent_session_link.sql` | `migrate-agent-session-link-remote` | `learner.agent_session_link` — student ↔ ADK agent session mapping used to rebuild conversations ([22](../requirements/22_AGENT_SESSION_TRANSCRIPTS.md)); logical link into framework-owned `agent_sessions`, cascades on learner deletion |
| `021_attempt_media.sql` | `migrate-attempt-media-remote` | `attempt_media.*` private, versioned learner media/evidence/transcription/approval and assessment records; makes `learner.attempt.is_correct` nullable so unassessed approved work is excluded from mastery |
| `022_artifact_runtime.sql` | `migrate-artifacts-remote` | `artifact_runtime.*` structured artifact requests/bundles, private asset metadata, validation/lineage, tags and explicit pgvector embeddings |

Migrations use idempotent DDL where appropriate; inspect each migration for
its exact operations and prerequisites before applying it. The inventory above
does not assert that any remote target has applied a migration.

Migrations 021/022 are described in the source-derived schema reference; this
table is not evidence that they have run. Attempt media and generated artifact
bytes use private object storage, independently configured from Neon Auth and
the AI Gateway. See [schema](../requirements/reference/POSTGRES_SCHEMA.md),
[DML behavior](../requirements/reference/POSTGRES_DML.md), and
[REST contracts](../requirements/reference/REST_API.md).

### Textbook package import (Prasolov geometry)

`etl/import_textbook_package.py` imports the enriched `pedagogy_v3` packages under
`math_tutor_new_requirements_copilot_pack_v2_expanded/GEOMETRY-TEXTBOOKS/`. It goes through
register → stage → validate → upsert → reconcile, and every step is idempotent. Source quirks are
recorded in `ingest.import_conflict` and do not abort the import. Learning items import as
`PENDING_REVIEW`; `make textbook-approve-learning-items-remote` auto-approves the structurally valid ones
(`approval_method='automatic'`, current product decision) so recovery detours and probes can use them.
Re-imports never overwrite an approval. After approving, run `textbook-vector-remote` and then
`textbook-graph-remote` so the item vectors and `:LearningItem` nodes catch up.

```bash
make textbook-import-dry-run [CHAPTER=1]   # offline validation
make textbook-import-remote  [CHAPTER=1]   # import into Neon
make textbook-import-status-remote         # status + reconciliation counts
make textbook-graph-remote                 # Aura: --pedagogy base, then SolutionPart/SolutionStep layer
make textbook-graph-status-remote          # Postgres vs Aura step-graph reconciliation (read-only)
make textbook-vector-remote                # build + embed step chunks (paid, idempotent)
make textbook-vector-status-remote         # eligible vs ACTIVE embeddings (read-only)
make textbook-problem-vector-remote        # embed Prasolov problem/solution statements (paid)
make migrate-step-runtime-remote           # student step runtime schema (migration 012)
make migrate-step-hints-remote             # step hint cache (migration 013)
make migrate-gap-diagnosis-remote          # gap diagnosis (migration 014)
make migrate-recovery-remote               # recovery plans + item approval columns (migration 015)
make migrate-agent-session-link-remote     # student ↔ agent session link for transcripts (migration 016)
make textbook-approve-learning-items-remote  # auto-approve valid learning items (idempotent)
```

Progress and verification SQL: `requirements/18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md`.
Pitfalls (BOM, duplicate IDs, lock order, projection kinds): `requirements/19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md`.

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

Every starter manifest assertion starts **PENDING**, with versioned assistant-draft source
and explicit confidence. Required levels and difficulty axes are proposals,
not calibrated ratings. Step counts and prerequisite-depth estimates are
intentionally absent. Following explicit operator authorization, the live
starter rows were bulk-approved through `/admin/pedagogy` on 2026-10-04.
All 27 are now REVIEWED in Postgres, with individual audit snapshots and the
operator's rationale. This is bootstrap approval, not independent expert certification.

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

### Admin approval UI

Open `http://localhost:5173/admin/pedagogy` after logging in as admin.
Migration 007 adds review history and publication records:

```sh
make -C mathbank-db migrate-pedagogy-review-remote
```

Review skills before dependent links, or use **Approve pending starter set**
to handle all pending starter rows in dependency order. **Select all assertions
on this page** supports selected-row bulk approval/rejection. Every individual
or bulk decision requires a rationale; approval also requires an explicit UI
confirmation. A stale row, invalid dependency or reviewed graph cycle rejects
the entire transaction. There is no automatic propagation to related rows.

Then explicitly select **Publish metadata to graph**. A source fingerprint
prevents publishing an unseen changed snapshot. Publishing retains statuses
and does not approve other pending corpus metadata. The current live publication
has 6 REVIEWED skills, 18 REVIEWED skill-related edges, 3 REVIEWED difficulty
assessments, and 65 PENDING legacy hierarchy edges.

The shared admin credential is recorded as `shared-admin-api-key`, not a
fabricated named reviewer. Audit events preserve original assistant sources,
confidence and all before/after fields. Review history is immutable via this
API. The system does not persist learner information during metadata review.

**Do not re-import the original PENDING starter manifest to refresh a reviewed
set.** Import is replacement semantics, so doing so intentionally downgrades
the live statuses. The manifest remains the original candidate proposal; admin
decisions live in Postgres history. For a revised assertion, reauthor it as
PENDING and review it again before publication.

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
