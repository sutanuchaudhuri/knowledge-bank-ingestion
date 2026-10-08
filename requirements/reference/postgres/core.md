# PostgreSQL `core` schema

**Role:** Canonical corpus. Problems, competition identities, reference solutions and source images.

**Access family:** Public corpus `/v1/problems`, `/v1/competitions`; admin corpus/import/textbook routes; private tutor reference reads.

**Evidence:** live catalog metadata at 2026-10-08T01:57:54.421824+00:00; source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `core.competition`

**Kind / use case:** table. Stable competition catalog and organization identity.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L14); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/corpus_authoring.py](../../../mathbank-rest/src/mathbank_rest/corpus_authoring.py#L59); [mathbank-rest/src/mathbank_rest/pedagogy.py](../../../mathbank-rest/src/mathbank_rest/pedagogy.py#L123); [mathbank-rest/src/mathbank_rest/db/hybrid_search.py](../../../mathbank-rest/src/mathbank_rest/db/hybrid_search.py#L167); [mathbank-rest/src/mathbank_rest/db/vector_search.py](../../../mathbank-rest/src/mathbank_rest/db/vector_search.py#L100); [mathbank-rest/src/mathbank_rest/db/admin.py](../../../mathbank-rest/src/mathbank_rest/db/admin.py#L23); [mathbank-rest/src/mathbank_rest/db/queries.py](../../../mathbank-rest/src/mathbank_rest/db/queries.py#L50); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L24); [mathbank-rest/src/mathbank_rest/db/learner.py](../../../mathbank-rest/src/mathbank_rest/db/learner.py#L41); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L163); [mathbank-db/etl/pdf_pipeline.py](../../../mathbank-db/etl/pdf_pipeline.py#L188).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `competition_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `external_code` | `text` | yes | `-` | `- / -` |
| `name` | `text` | no | `-` | `- / -` |
| `organization` | `text` | yes | `-` | `- / -` |
| `country` | `text` | yes | `-` | `- / -` |
| `level` | `text` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `competition_competition_id_not_null` / `n` | `NOT NULL competition_id` | deferrable=False, initially deferred=False, validated=True |
| `competition_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `competition_external_code_key` / `u` | `UNIQUE (external_code)` | deferrable=False, initially deferred=False, validated=True |
| `competition_name_not_null` / `n` | `NOT NULL name` | deferrable=False, initially deferred=False, validated=True |
| `competition_name_organization_key` / `u` | `UNIQUE (name, organization)` | deferrable=False, initially deferred=False, validated=True |
| `competition_pkey` / `p` | `PRIMARY KEY (competition_id)` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `core.competition_edition` / `competition_edition_competition_id_fkey`: `FOREIGN KEY (competition_id) REFERENCES core.competition(competition_id)`.
- `pedagogy.source_book` / `source_book_competition_id_fkey`: `FOREIGN KEY (competition_id) REFERENCES core.competition(competition_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `competition_external_code_key`: `CREATE UNIQUE INDEX competition_external_code_key ON core.competition USING btree (external_code)`; valid=True, ready=True.
- `competition_name_organization_key`: `CREATE UNIQUE INDEX competition_name_organization_key ON core.competition USING btree (name, organization)`; valid=True, ready=True.
- `competition_pkey`: `CREATE UNIQUE INDEX competition_pkey ON core.competition USING btree (competition_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `core.competition_edition`

**Kind / use case:** table. Competition year/season/edition; nullable years accommodate textbooks.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L25); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/corpus_authoring.py](../../../mathbank-rest/src/mathbank_rest/corpus_authoring.py#L58); [mathbank-rest/src/mathbank_rest/pedagogy.py](../../../mathbank-rest/src/mathbank_rest/pedagogy.py#L122); [mathbank-rest/src/mathbank_rest/db/hybrid_search.py](../../../mathbank-rest/src/mathbank_rest/db/hybrid_search.py#L166); [mathbank-rest/src/mathbank_rest/db/vector_search.py](../../../mathbank-rest/src/mathbank_rest/db/vector_search.py#L99); [mathbank-rest/src/mathbank_rest/db/queries.py](../../../mathbank-rest/src/mathbank_rest/db/queries.py#L100); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L23); [mathbank-rest/src/mathbank_rest/db/learner.py](../../../mathbank-rest/src/mathbank_rest/db/learner.py#L40); [mathbank-db/etl/pdf_pipeline.py](../../../mathbank-db/etl/pdf_pipeline.py#L233); [mathbank-db/etl/load_corpus.py](../../../mathbank-db/etl/load_corpus.py#L131); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L866).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `edition_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `competition_id` | `uuid` | no | `-` | `- / -` |
| `year` | `integer` | yes | `-` | `- / -` |
| `season` | `text` | yes | `-` | `- / -` |
| `edition_label` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `competition_edition_competition_id_fkey` / `f` | `FOREIGN KEY (competition_id) REFERENCES core.competition(competition_id)` | deferrable=False, initially deferred=False, validated=True |
| `competition_edition_competition_id_not_null` / `n` | `NOT NULL competition_id` | deferrable=False, initially deferred=False, validated=True |
| `competition_edition_competition_id_year_season_edition_labe_key` / `u` | `UNIQUE (competition_id, year, season, edition_label)` | deferrable=False, initially deferred=False, validated=True |
| `competition_edition_edition_id_not_null` / `n` | `NOT NULL edition_id` | deferrable=False, initially deferred=False, validated=True |
| `competition_edition_pkey` / `p` | `PRIMARY KEY (edition_id)` | deferrable=False, initially deferred=False, validated=True |
| `competition_edition_year_check` / `c` | `CHECK (year >= 1900 AND year <= 2200)` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `core.paper` / `paper_edition_id_fkey`: `FOREIGN KEY (edition_id) REFERENCES core.competition_edition(edition_id)`.
- `pedagogy.source_book` / `source_book_edition_id_fkey`: `FOREIGN KEY (edition_id) REFERENCES core.competition_edition(edition_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `competition_edition_competition_id_year_season_edition_labe_key`: `CREATE UNIQUE INDEX competition_edition_competition_id_year_season_edition_labe_key ON core.competition_edition USING btree (competition_id, year, season, edition_label)`; valid=True, ready=True.
- `competition_edition_pkey`: `CREATE UNIQUE INDEX competition_edition_pkey ON core.competition_edition USING btree (edition_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `core.paper`

**Kind / use case:** table. Edition-owned paper and official/nonofficial identity.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L34); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/corpus_authoring.py](../../../mathbank-rest/src/mathbank_rest/corpus_authoring.py#L57); [mathbank-rest/src/mathbank_rest/pedagogy.py](../../../mathbank-rest/src/mathbank_rest/pedagogy.py#L121); [mathbank-rest/src/mathbank_rest/db/hybrid_search.py](../../../mathbank-rest/src/mathbank_rest/db/hybrid_search.py#L165); [mathbank-rest/src/mathbank_rest/db/vector_search.py](../../../mathbank-rest/src/mathbank_rest/db/vector_search.py#L98); [mathbank-rest/src/mathbank_rest/db/queries.py](../../../mathbank-rest/src/mathbank_rest/db/queries.py#L99); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L22); [mathbank-rest/src/mathbank_rest/db/learner.py](../../../mathbank-rest/src/mathbank_rest/db/learner.py#L39); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L69); [mathbank-db/etl/embed_corpus.py](../../../mathbank-db/etl/embed_corpus.py#L179); [mathbank-db/etl/pdf_pipeline.py](../../../mathbank-db/etl/pdf_pipeline.py#L250).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `paper_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `edition_id` | `uuid` | no | `-` | `- / -` |
| `external_code` | `text` | yes | `-` | `- / -` |
| `paper_code` | `text` | no | `-` | `- / -` |
| `paper_type` | `text` | yes | `-` | `- / -` |
| `duration_minutes` | `integer` | yes | `-` | `- / -` |
| `question_count` | `integer` | yes | `-` | `- / -` |
| `max_score` | `numeric` | yes | `-` | `- / -` |
| `official` | `boolean` | no | `true` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `paper_edition_id_fkey` / `f` | `FOREIGN KEY (edition_id) REFERENCES core.competition_edition(edition_id)` | deferrable=False, initially deferred=False, validated=True |
| `paper_edition_id_not_null` / `n` | `NOT NULL edition_id` | deferrable=False, initially deferred=False, validated=True |
| `paper_edition_id_paper_code_key` / `u` | `UNIQUE (edition_id, paper_code)` | deferrable=False, initially deferred=False, validated=True |
| `paper_external_code_key` / `u` | `UNIQUE (external_code)` | deferrable=False, initially deferred=False, validated=True |
| `paper_official_not_null` / `n` | `NOT NULL official` | deferrable=False, initially deferred=False, validated=True |
| `paper_paper_code_not_null` / `n` | `NOT NULL paper_code` | deferrable=False, initially deferred=False, validated=True |
| `paper_paper_id_not_null` / `n` | `NOT NULL paper_id` | deferrable=False, initially deferred=False, validated=True |
| `paper_pkey` / `p` | `PRIMARY KEY (paper_id)` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `core.problem` / `problem_paper_id_fkey`: `FOREIGN KEY (paper_id) REFERENCES core.paper(paper_id)`.
- `pedagogy.chapter_section` / `chapter_section_paper_id_fkey`: `FOREIGN KEY (paper_id) REFERENCES core.paper(paper_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `paper_edition_id_paper_code_key`: `CREATE UNIQUE INDEX paper_edition_id_paper_code_key ON core.paper USING btree (edition_id, paper_code)`; valid=True, ready=True.
- `paper_external_code_key`: `CREATE UNIQUE INDEX paper_external_code_key ON core.paper USING btree (external_code)`; valid=True, ready=True.
- `paper_pkey`: `CREATE UNIQUE INDEX paper_pkey ON core.paper USING btree (paper_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `core.problem`

**Kind / use case:** table. Canonical statement, answer/provenance/hash and reviewed-text protection.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L47); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/corpus_authoring.py](../../../mathbank-rest/src/mathbank_rest/corpus_authoring.py#L38); [mathbank-rest/src/mathbank_rest/enrichment.py](../../../mathbank-rest/src/mathbank_rest/enrichment.py#L71); [mathbank-rest/src/mathbank_rest/artifact_runtime.py](../../../mathbank-rest/src/mathbank_rest/artifact_runtime.py#L778); [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L290); [mathbank-rest/src/mathbank_rest/mastery.py](../../../mathbank-rest/src/mathbank_rest/mastery.py#L28); [mathbank-rest/src/mathbank_rest/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/step_runtime.py#L255); [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L207); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L281); [mathbank-rest/src/mathbank_rest/pedagogy.py](../../../mathbank-rest/src/mathbank_rest/pedagogy.py#L120); [mathbank-rest/src/mathbank_rest/route_runtime.py](../../../mathbank-rest/src/mathbank_rest/route_runtime.py#L19).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `problem_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `paper_id` | `uuid` | no | `-` | `- / -` |
| `problem_number` | `integer` | no | `-` | `- / -` |
| `canonical_code` | `text` | no | `-` | `- / -` |
| `statement_text` | `text` | no | `-` | `- / -` |
| `statement_latex` | `text` | yes | `-` | `- / -` |
| `answer_type` | `text` | yes | `-` | `- / -` |
| `official_answer` | `text` | yes | `-` | `- / -` |
| `source_url` | `text` | yes | `-` | `- / -` |
| `status` | `text` | no | `'ACTIVE'::text` | `- / -` |
| `content_hash` | `text` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `difficulty_band` | `text` | yes | `-` | `- / -` |
| `classification_status` | `text` | yes | `-` | `- / -` |
| `admin_edited_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `problem_canonical_code_key` / `u` | `UNIQUE (canonical_code)` | deferrable=False, initially deferred=False, validated=True |
| `problem_canonical_code_not_null` / `n` | `NOT NULL canonical_code` | deferrable=False, initially deferred=False, validated=True |
| `problem_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `problem_paper_id_fkey` / `f` | `FOREIGN KEY (paper_id) REFERENCES core.paper(paper_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_paper_id_not_null` / `n` | `NOT NULL paper_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_paper_id_problem_number_key` / `u` | `UNIQUE (paper_id, problem_number)` | deferrable=False, initially deferred=False, validated=True |
| `problem_pkey` / `p` | `PRIMARY KEY (problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_problem_number_not_null` / `n` | `NOT NULL problem_number` | deferrable=False, initially deferred=False, validated=True |
| `problem_statement_text_not_null` / `n` | `NOT NULL statement_text` | deferrable=False, initially deferred=False, validated=True |
| `problem_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `problem_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `artifact_runtime.artifact_request` / `artifact_request_linked_problem_id_fkey`: `FOREIGN KEY (linked_problem_id) REFERENCES core.problem(problem_id)`.
- `attempt_media.submission` / `submission_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id)`.
- `core.problem_image` / `problem_image_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `core.solution` / `solution_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `ingest.corpus_draft` / `corpus_draft_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE RESTRICT`.
- `knowledge.enrichment_job` / `enrichment_job_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `knowledge.problem_concept` / `problem_concept_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `knowledge.problem_pedagogy` / `problem_pedagogy_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `knowledge.problem_skill` / `problem_skill_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `knowledge.problem_technique` / `problem_technique_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `learner.attempt` / `attempt_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id)`.
- `learner.pedagogy_feedback` / `pedagogy_feedback_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `learner.solve_attempt` / `solve_attempt_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id)`.
- `pedagogy.diagram` / `diagram_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `pedagogy.learning_item` / `learning_item_source_problem_id_fkey`: `FOREIGN KEY (source_problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `pedagogy.problem_enrichment` / `problem_enrichment_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `pedagogy.problem_source_ref` / `problem_source_ref_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `pedagogy.recovery_plan` / `recovery_plan_origin_problem_id_fkey`: `FOREIGN KEY (origin_problem_id) REFERENCES core.problem(problem_id)`.
- `pedagogy.solution_dag_review` / `solution_dag_review_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `pedagogy.solution_part` / `solution_part_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `pedagogy.solution_route_release` / `solution_route_release_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id)`.
- `pedagogy.solution_source_ref` / `solution_source_ref_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `pedagogy.solution_step` / `solution_step_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE`.
- `search.chunk` / `chunk_problem_id_fkey`: `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id)`.
- `tutor.runtime_state` / `runtime_state_current_problem_id_fkey`: `FOREIGN KEY (current_problem_id) REFERENCES core.problem(problem_id)`.
- `visual.asset` / `asset_source_problem_id_fkey`: `FOREIGN KEY (source_problem_id) REFERENCES core.problem(problem_id) ON DELETE SET NULL`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `idx_problem_paper`: `CREATE INDEX idx_problem_paper ON core.problem USING btree (paper_id, problem_number)`; valid=True, ready=True.
- `idx_problem_statement_fts`: `CREATE INDEX idx_problem_statement_fts ON core.problem USING gin (to_tsvector('english'::regconfig, statement_text))`; valid=True, ready=True.
- `idx_problem_statement_trgm`: `CREATE INDEX idx_problem_statement_trgm ON core.problem USING gin (statement_text gin_trgm_ops)`; valid=True, ready=True.
- `problem_canonical_code_key`: `CREATE UNIQUE INDEX problem_canonical_code_key ON core.problem USING btree (canonical_code)`; valid=True, ready=True.
- `problem_paper_id_problem_number_key`: `CREATE UNIQUE INDEX problem_paper_id_problem_number_key ON core.problem USING btree (paper_id, problem_number)`; valid=True, ready=True.
- `problem_pkey`: `CREATE UNIQUE INDEX problem_pkey ON core.problem USING btree (problem_id)`; valid=True, ready=True.

**Triggers:**

- `protect_admin_statement`: `CREATE TRIGGER protect_admin_statement BEFORE UPDATE ON core.problem FOR EACH ROW EXECUTE FUNCTION core.protect_admin_statement()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `core.problem_image`

**Kind / use case:** table. Ordered source-image metadata; visibility checked before serving bytes.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L93); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/corpus_authoring.py](../../../mathbank-rest/src/mathbank_rest/corpus_authoring.py#L54); [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L287); [mathbank-rest/src/mathbank_rest/routers/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L446); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L122); [mathbank-rest/src/mathbank_rest/db/problem_images.py](../../../mathbank-rest/src/mathbank_rest/db/problem_images.py#L24); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L224); [mathbank-db/etl/backfill_question_figures.py](../../../mathbank-db/etl/backfill_question_figures.py#L28); [mathbank-db/etl/pdf_assets.py](../../../mathbank-db/etl/pdf_assets.py#L107); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L1073); [mathbank-db/etl/paper_batches.py](../../../mathbank-db/etl/paper_batches.py#L344).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `problem_image_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `ordinal` | `integer` | no | `-` | `- / -` |
| `local_path` | `text` | no | `-` | `- / -` |
| `source` | `text` | no | `'PDF_PARSED'::text` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `problem_image_local_path_not_null` / `n` | `NOT NULL local_path` | deferrable=False, initially deferred=False, validated=True |
| `problem_image_ordinal_not_null` / `n` | `NOT NULL ordinal` | deferrable=False, initially deferred=False, validated=True |
| `problem_image_pkey` / `p` | `PRIMARY KEY (problem_image_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_image_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `problem_image_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_image_problem_id_ordinal_key` / `u` | `UNIQUE (problem_id, ordinal)` | deferrable=False, initially deferred=False, validated=True |
| `problem_image_problem_image_id_not_null` / `n` | `NOT NULL problem_image_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_image_source_not_null` / `n` | `NOT NULL source` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `pedagogy.diagram` / `diagram_problem_image_id_fkey`: `FOREIGN KEY (problem_image_id) REFERENCES core.problem_image(problem_image_id) ON DELETE SET NULL`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `problem_image_pkey`: `CREATE UNIQUE INDEX problem_image_pkey ON core.problem_image USING btree (problem_image_id)`; valid=True, ready=True.
- `problem_image_problem_id_ordinal_key`: `CREATE UNIQUE INDEX problem_image_problem_id_ordinal_key ON core.problem_image USING btree (problem_id, ordinal)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `core.solution`

**Kind / use case:** table. Versioned reference solution body and mathematical verification status.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L70); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/corpus_authoring.py](../../../mathbank-rest/src/mathbank_rest/corpus_authoring.py#L231); [mathbank-rest/src/mathbank_rest/enrichment.py](../../../mathbank-rest/src/mathbank_rest/enrichment.py#L406); [mathbank-rest/src/mathbank_rest/route_runtime.py](../../../mathbank-rest/src/mathbank_rest/route_runtime.py#L20); [mathbank-rest/src/mathbank_rest/route_compiler.py](../../../mathbank-rest/src/mathbank_rest/route_compiler.py#L58); [mathbank-rest/src/mathbank_rest/solution_guidance.py](../../../mathbank-rest/src/mathbank_rest/solution_guidance.py#L79); [mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py](../../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py#L110); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L364); [mathbank-rest/src/mathbank_rest/db/queries.py](../../../mathbank-rest/src/mathbank_rest/db/queries.py#L159); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L121); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L70).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `solution_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `solution_kind` | `text` | no | `'CURATED'::text` | `- / -` |
| `revision` | `integer` | no | `1` | `- / -` |
| `body_markdown` | `text` | yes | `-` | `- / -` |
| `body_latex` | `text` | yes | `-` | `- / -` |
| `verification_status` | `text` | no | `'UNVERIFIED'::text` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solution_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `solution_pkey` / `p` | `PRIMARY KEY (solution_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_problem_id_solution_kind_revision_key` / `u` | `UNIQUE (problem_id, solution_kind, revision)` | deferrable=False, initially deferred=False, validated=True |
| `solution_revision_not_null` / `n` | `NOT NULL revision` | deferrable=False, initially deferred=False, validated=True |
| `solution_solution_id_not_null` / `n` | `NOT NULL solution_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_solution_kind_not_null` / `n` | `NOT NULL solution_kind` | deferrable=False, initially deferred=False, validated=True |
| `solution_verification_status_not_null` / `n` | `NOT NULL verification_status` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `core.solution_step` / `solution_step_solution_id_fkey`: `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id) ON DELETE CASCADE`.
- `pedagogy.route_compiler_job` / `route_compiler_job_solution_id_fkey`: `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id)`.
- `pedagogy.solution_dag_review` / `solution_dag_review_solution_id_fkey`: `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id) ON DELETE CASCADE`.
- `pedagogy.solution_part` / `solution_part_solution_id_fkey`: `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id) ON DELETE CASCADE`.
- `pedagogy.solution_route_release` / `solution_route_release_solution_id_fkey`: `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id)`.
- `pedagogy.solution_source_ref` / `solution_source_ref_solution_id_fkey`: `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id) ON DELETE CASCADE`.
- `pedagogy.solution_step` / `solution_step_solution_id_fkey`: `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id) ON DELETE CASCADE`.
- `search.chunk` / `chunk_solution_id_fkey`: `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `solution_pkey`: `CREATE UNIQUE INDEX solution_pkey ON core.solution USING btree (solution_id)`; valid=True, ready=True.
- `solution_problem_id_solution_kind_revision_key`: `CREATE UNIQUE INDEX solution_problem_id_solution_kind_revision_key ON core.solution USING btree (problem_id, solution_kind, revision)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `core.solution_step`

**Kind / use case:** table. Legacy UUID/ordinal steps; not the text-ID imported step runtime.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L82); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Important:** no imported-step-runtime writer/consumer was found for this legacy table.
Use `pedagogy.solution_step` for the current text-ID step runtime; do not substitute this UUID table.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `solution_step_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `solution_id` | `uuid` | no | `-` | `- / -` |
| `ordinal` | `integer` | no | `-` | `- / -` |
| `step_type` | `text` | yes | `-` | `- / -` |
| `explanation` | `text` | yes | `-` | `- / -` |
| `formula_latex` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solution_step_ordinal_not_null` / `n` | `NOT NULL ordinal` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_pkey` / `p` | `PRIMARY KEY (solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_solution_id_fkey` / `f` | `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_solution_id_not_null` / `n` | `NOT NULL solution_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_solution_id_ordinal_key` / `u` | `UNIQUE (solution_id, ordinal)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_solution_step_id_not_null` / `n` | `NOT NULL solution_step_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `solution_step_pkey`: `CREATE UNIQUE INDEX solution_step_pkey ON core.solution_step USING btree (solution_step_id)`; valid=True, ready=True.
- `solution_step_solution_id_ordinal_key`: `CREATE UNIQUE INDEX solution_step_solution_id_ordinal_key ON core.solution_step USING btree (solution_id, ordinal)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

## Functions and routines

Extension routines are owned by their installed extension, not project migration code.
Volatility: i=immutable, s=stable, v=volatile. No routine was invoked by this inspection.

| Signature | Returns | Language / volatility | Security definer | Owner / source |
|---|---|---|---|---|
| `protect_admin_statement(-)` | `trigger` | plpgsql / v | False | [025_corpus_authoring.sql](../../../mathbank-db/sql/025_corpus_authoring.sql) |

### Observed definition: `core.protect_admin_statement`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION core.protect_admin_statement()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF OLD.admin_edited_at IS NOT NULL AND NEW.statement_text IS DISTINCT FROM OLD.statement_text
        AND NEW.admin_edited_at IS NOT DISTINCT FROM OLD.admin_edited_at THEN
        RAISE EXCEPTION 'Reviewed admin text cannot be overwritten by ingestion';
    END IF;
    RETURN NEW;
END $function$
```
