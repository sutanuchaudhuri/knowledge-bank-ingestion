# PostgreSQL schema reference

## Evidence

- Evidence mode: source-derived only.
- Source revision: `43c3316d5b6f8a838874de4aa384cb28ef00aa1a`, with uncommitted worktree changes included (refreshed 2026-10-06 for migration 020).
- Sources: `mathbank-db/sql/001_schema.sql` through `020_live_fluid_platform.sql`, `mathbank-db/sql/ops/approve_learning_items_auto.sql`, `mathbank-db/Makefile`; agent session evidence from `mathbank-agent/session_config.py` and `server.py`.
- Migrations were not executed; this is the composite schema implied by source order.

## Migration order and ownership

| Migration | Ownership / effect |
|---|---|
| `001_schema.sql` | Base `core`, `knowledge`, `search`, `pipeline`, `audit`; contest corpus, taxonomy links, pipeline trackers, trigram extension. |
| `002_vector_schema.sql` | `pgvector` extension and `search.*` embedding pipeline. |
| `003_learner_schema.sql` | `learner.*` student profile, attempts, and mastery cache. |
| `004_admin_pipeline.sql` | Adds `pipeline.pdf_source.source_kind`; source-kind index. |
| `005_student_profile_names.sql` | Adds `first_name`, `last_name` to `learner.student_profile`. |
| `006_pedagogy.sql` | P0 skills/problem pedagogy authoring tables. |
| `007_pedagogy_review.sql` | Human review event and publication tables. |
| `008_automatic_metadata.sql` | Automatic approval event table, enrichment job table, review entity-kind expansion, approval triggers/functions, `approval_method` columns on metadata tables. |
| `009_relationship_enrichment.sql` | Relationship enrichment job/outbox and review-kind expansion. |
| `010_textbook_import.sql` | `ingest.*` content-package schema; `pedagogy.*` textbook taxonomy, solution DAG, learning items, diagrams; drops NOT NULL from `core.competition_edition.year`. |
| `011_step_vector_metadata.sql` | Adds step/learning-item/taxonomy-owner columns and indexes to `search.chunk`; adds `chunk_single_pedagogy_owner`; seeds `pedagogy_step_v2` preprocessing profile. |
| `012_step_runtime.sql` | Adds `tutor` schema, stateful step-solving runtime tables under `learner`, append-only events/idempotency, `tutor.runtime_state`, and transactional outbox tables under `pipeline`. |
| `013_step_hints.sql` | Adds shared per-step progressive hint cache `pedagogy.step_hint` for Phase 8 levels 1–4; Makefile target `migrate-step-hints-remote` applies it to the selected remote when an operator chooses to run it. |
| `014_gap_diagnosis.sql` | Adds Phase 9 `pedagogy.gap_diagnosis` and `pedagogy.knowledge_gap`; replaces `learner.event` CHECK constraint to include `GAP_DIAGNOSED` and `GAP_HYPOTHESIS_RESOLVED`; Makefile target `migrate-gap-diagnosis-remote` applies it to the selected remote when an operator chooses to run it. |
| `015_recovery_runtime.sql` | Adds Phase 10 recovery plans/items, approval provenance on learning items, AI re-rank storage on diagnoses, recovery FKs from learner/runtime state, partial learning-item visibility indexes, and recovery event types; Makefile target `migrate-recovery-remote` applies it to the selected remote when an operator chooses to run it. |
| `016_agent_session_link.sql` | Adds `learner.agent_session_link`: project-owned student ↔ ADK agent session mapping used to rebuild conversations; logical (not FK) reference into framework-owned `agent_sessions`; Makefile target `migrate-agent-session-link-remote` applies it to the selected remote when an operator chooses to run it. |
| `017_step_techniques.sql` | Adds `pedagogy.solution_step_technique` (derived step → technique tags with provenance) and `pedagogy.solution_step_technique_run` (per-step derivation outcome). Makefile `migrate-step-technique-remote`. |
| `018_outbox_consumers.sql` | Replaces `learner.event` CHECK to add `ATTEMPT_ABANDONED`; index `pipeline.outbox_event (event_type, created_at)`; creates schema `analytics` with `analytics.learner_daily_activity`; creates `pipeline.projection_request` with one-open-request partial unique index. Makefile `migrate-outbox-consumers-remote`. |
| `019_admin_import_review.sql` | Adds append-only `ingest.admin_review_action` (+ trigger function), `ingest.import_conflict.decision/decided_at` (+ CHECK), `pedagogy.solution_step.admin_edited_at`, `pedagogy.solution_dag_review`, column comment documenting the dependency vocabulary, and `pipeline.projection_request.requested_by`. |
| `020_live_fluid_platform.sql` | New `authoring`, `live`, `activity`, `visual` schemas for presentation plans, admin authoring chat/patches, live sessions with an append-only event log, activities/responses and validated widget specs (docs [27](../27_FLUID_WIDGET_LAYER.md), [28](../28_DISTRIBUTED_LIVE_PLATFORM.md)). Idempotent `IF NOT EXISTS` DDL. |
| `sql/ops/approve_learning_items_auto.sql` | Operator DML, not a migration: idempotently approves validated `PENDING_REVIEW` learning items as `approval_method='automatic'`, sets `student_visible`, and reports status counts. Makefile target `textbook-approve-learning-items-remote` runs it against the selected remote when an operator chooses to run it. |

Required extensions: `pg_trgm` and `vector`. The base schema uses `gen_random_uuid()`; the SQL assumes a Postgres installation where that function is available.

## Schemas

| Schema | Owner/purpose |
|---|---|
| `core` | Canonical competitions, papers, problems, solutions, solution steps, images. |
| `knowledge` | Concepts, techniques, skills, assertions, review/audit, enrichment jobs. |
| `search` | Representation/chunk/embedding/vector retrieval tables. |
| `pipeline` | Corpus run/work-item/source/projection status and transactional outbox. |
| `learner` | Student profiles, legacy answer attempts, derived mastery cache and step-runtime session/event state. |
| `ingest` | v2 textbook package registry/staging/conflicts/reconciliation. |
| `pedagogy` | Textbook source references, taxonomy nodes/edges, solution parts/steps/dependencies, learning items, diagrams. |
| `tutor` | Runtime checkpoint/state for the student step-solving tutor. |
| `authoring` | Migration 020: versioned presentation plans, topics, admin authoring chat, proposed patches. |
| `live` | Migration 020: live classroom sessions, participants, append-only session events, command receipts, topic runs, recommendations, takeovers. |
| `activity` | Migration 020: activity definitions, live instances, participant responses. |
| `visual` | Migration 020: validated widget specs, per-session widget state, visual assets (asset table currently unused). |
| `analytics` | Migration 018: rebuildable per-student activity rollups written by the outbox consumer. |
| `audit` | Created by base migration; no checked-in tables currently target it. |
| `agent_sessions` | Created at agent startup, framework-owned by Google ADK `DatabaseSessionService`; not part of MathBank migrations. |

## `core` schema

### `core.competition`

Purpose: contest/textbook family registry.

| Column | Type | Default | Null | Constraints/notes |
|---|---|---|---|---|
| `competition_id` | `uuid` | `gen_random_uuid()` | no | PK |
| `external_code` | `text` |  | yes | UNIQUE natural import key |
| `name` | `text` |  | no | also in `UNIQUE(name, organization)` |
| `organization` | `text` |  | yes |  |
| `country` | `text` |  | yes |  |
| `level` | `text` |  | yes |  |
| `created_at` | `timestamptz` | `now()` | no |  |

### `core.competition_edition`

| Column | Type | Default | Null | Constraints/notes |
|---|---|---|---|---|
| `edition_id` | `uuid` | `gen_random_uuid()` | no | PK |
| `competition_id` | `uuid` |  | no | FK `core.competition`; default FK action |
| `year` | `int` |  | yes after migration 010 | CHECK `1900..2200` remains; NULL used for textbooks |
| `season` | `text` |  | yes |  |
| `edition_label` | `text` |  | yes |  |

Unique: `(competition_id, year, season, edition_label)`.

### `core.paper`

| Column | Type | Default | Null | Constraints/notes |
|---|---|---|---|---|
| `paper_id` | `uuid` | `gen_random_uuid()` | no | PK |
| `edition_id` | `uuid` |  | no | FK `core.competition_edition` |
| `external_code` | `text` |  | yes | UNIQUE natural key |
| `paper_code` | `text` |  | no |  |
| `paper_type` | `text` |  | yes |  |
| `duration_minutes` | `int` |  | yes |  |
| `question_count` | `int` |  | yes |  |
| `max_score` | `numeric` |  | yes |  |
| `official` | `boolean` | `true` | no |  |

Unique: `(edition_id, paper_code)`.

### `core.problem`

| Column | Type | Default | Null | Constraints/notes |
|---|---|---|---|---|
| `problem_id` | `uuid` | `gen_random_uuid()` | no | PK |
| `paper_id` | `uuid` |  | no | FK `core.paper` |
| `problem_number` | `int` |  | no | unique per paper |
| `canonical_code` | `text` |  | no | UNIQUE stable problem code |
| `statement_text` | `text` |  | no |  |
| `statement_latex` | `text` |  | yes |  |
| `answer_type` | `text` |  | yes |  |
| `official_answer` | `text` |  | yes |  |
| `source_url` | `text` |  | yes |  |
| `difficulty_band` | `text` |  | yes | added/ensured by 001 |
| `classification_status` | `text` |  | yes | added/ensured by 001 |
| `status` | `text` | `'ACTIVE'` | no | application status |
| `content_hash` | `text` |  | yes | source text hash |
| `created_at` | `timestamptz` | `now()` | no |  |
| `updated_at` | `timestamptz` | `now()` | no | app-updated, no trigger |

Unique: `(paper_id, problem_number)`. Indexes: `idx_problem_paper(paper_id, problem_number)`, GIN FTS on `statement_text`, GIN trigram on `statement_text`.

### `core.solution`

| Column | Type | Default | Null | Constraints/notes |
|---|---|---|---|---|
| `solution_id` | `uuid` | `gen_random_uuid()` | no | PK |
| `problem_id` | `uuid` |  | no | FK `core.problem ON DELETE CASCADE` |
| `solution_kind` | `text` | `'CURATED'` | no | part of natural key |
| `revision` | `int` | `1` | no | part of natural key |
| `body_markdown` | `text` |  | yes | solution content; not projected to graph |
| `body_latex` | `text` |  | yes |  |
| `verification_status` | `text` | `'UNVERIFIED'` | no |  |
| `created_at` | `timestamptz` | `now()` | no |  |

Unique: `(problem_id, solution_kind, revision)`.

### `core.solution_step`

Legacy/core solution steps.

| Column | Type | Default | Null | Constraints/notes |
|---|---|---|---|---|
| `solution_step_id` | `uuid` | `gen_random_uuid()` | no | PK |
| `solution_id` | `uuid` |  | no | FK `core.solution ON DELETE CASCADE` |
| `ordinal` | `int` |  | no | unique per solution |
| `step_type` | `text` |  | yes |  |
| `explanation` | `text` |  | yes |  |
| `formula_latex` | `text` |  | yes |  |

Unique: `(solution_id, ordinal)`.

### `core.problem_image`

| Column | Type | Default | Null | Constraints/notes |
|---|---|---|---|---|
| `problem_image_id` | `uuid` | `gen_random_uuid()` | no | PK |
| `problem_id` | `uuid` |  | no | FK `core.problem ON DELETE CASCADE` |
| `ordinal` | `int` |  | no | unique per problem |
| `local_path` | `text` |  | no | local asset path; avoid exposing blindly |
| `source` | `text` | `'PDF_PARSED'` | no | e.g. `AOPS_CRAWL`, `PDF_PROBLEM_PAGE`, `PDF_SOLUTION_PAGE` |

Unique: `(problem_id, ordinal)`.

## `knowledge` schema

### Taxonomy and corpus assertion tables

| Table | Columns and constraints |
|---|---|
| `knowledge.concept` | `concept_id uuid PK default gen_random_uuid()`, `slug text NOT NULL UNIQUE`, `name text NOT NULL`, `description text`, `level int`, `status text NOT NULL DEFAULT 'ACTIVE'`. |
| `knowledge.technique` | `technique_id uuid PK default gen_random_uuid()`, `slug text NOT NULL UNIQUE`, `name text NOT NULL`, `description text`, `status text NOT NULL DEFAULT 'ACTIVE'`. |
| `knowledge.problem_concept` | `problem_id uuid FK core.problem ON DELETE CASCADE`, `concept_id uuid FK knowledge.concept`, `role text NOT NULL DEFAULT 'PRIMARY'`, `confidence numeric(5,4)`, `assertion_source text NOT NULL`, `review_status text NOT NULL DEFAULT 'PENDING'`, `asserted_at timestamptz NOT NULL DEFAULT now()`, `approval_method text` added by 008; PK `(problem_id, concept_id, role)`. Automatic approval trigger applies after 008. |
| `knowledge.problem_technique` | `problem_id uuid FK core.problem ON DELETE CASCADE`, `technique_id uuid FK knowledge.technique`, `role text NOT NULL DEFAULT 'REQUIRED'`, `confidence numeric(5,4)`, `assertion_source text NOT NULL`, `review_status text NOT NULL DEFAULT 'PENDING'`, `approval_method text`; PK `(problem_id, technique_id, role)`. Automatic approval trigger applies after 008. |
| `knowledge.concept_relation` | `relation_id uuid PK default gen_random_uuid()`, `from_concept_id uuid FK knowledge.concept`, `to_concept_id uuid FK knowledge.concept`, `relation_type text NOT NULL`, `strength numeric(5,4)`, `assertion_source text NOT NULL`, `review_status text NOT NULL DEFAULT 'PENDING'`, `approval_method text`; UNIQUE `(from_concept_id, to_concept_id, relation_type)`. Automatic approval trigger applies after 008. |

### Pedagogy authoring tables (`006` plus `approval_method` from `008`)

| Table | Columns and constraints |
|---|---|
| `knowledge.skill` | `skill_id uuid PK default gen_random_uuid()`, `slug text NOT NULL UNIQUE CHECK btrim<>''`, `name text NOT NULL CHECK btrim<>''`, `objective text NOT NULL CHECK btrim<>''`, `level integer CHECK 1..5`, `source text NOT NULL CHECK btrim<>''`, `confidence numeric NOT NULL CHECK 0..1`, `review_status text NOT NULL DEFAULT 'PENDING' CHECK IN ('PENDING','REVIEWED','REJECTED')`, `approval_method text`. Automatic approval trigger applies after 008. |
| `knowledge.skill_concept` | `skill_id uuid FK knowledge.skill ON DELETE CASCADE`, `concept_id uuid FK knowledge.concept`, `source text NOT NULL`, `confidence numeric NOT NULL CHECK 0..1`, `review_status text NOT NULL DEFAULT 'PENDING' CHECK allowed`, `approval_method text`; PK `(skill_id, concept_id)`; index on `concept_id`. |
| `knowledge.skill_relation` | `from_skill_id uuid FK knowledge.skill ON DELETE CASCADE`, `to_skill_id uuid FK knowledge.skill ON DELETE CASCADE`, `relation_type text NOT NULL CHECK IN ('PREREQUISITE_OF','PART_OF','BUILDS_ON')`, `source text NOT NULL`, `confidence numeric NOT NULL CHECK 0..1`, `review_status text NOT NULL DEFAULT 'PENDING' CHECK allowed`, `approval_method text`, CHECK `from_skill_id <> to_skill_id`; PK `(from_skill_id, to_skill_id, relation_type)`; index on `to_skill_id`. |
| `knowledge.problem_skill` | `problem_id uuid FK core.problem ON DELETE CASCADE`, `skill_id uuid FK knowledge.skill`, `relation_type text CHECK IN ('REQUIRES','PRACTICES','TESTS')`, `role text CHECK IN ('primary','supporting')`, `required_level integer CHECK 1..5`, `importance numeric NOT NULL CHECK 0..1`, `source text NOT NULL`, `confidence numeric NOT NULL CHECK 0..1`, `review_status text NOT NULL DEFAULT 'PENDING' CHECK allowed`, `approval_method text`; PK `(problem_id, skill_id, relation_type, role)`; index on `skill_id`. |
| `knowledge.problem_pedagogy` | `problem_id uuid PK FK core.problem ON DELETE CASCADE`, integer dimensions `conceptual_depth`, `technical_load`, `algebraic_load`, `insight_required` CHECK 1..5, `number_of_steps integer CHECK >=0`, `prerequisite_depth integer CHECK >=0`, `estimated_contest_level text CHECK btrim<>''`, `source text NOT NULL`, `confidence numeric NOT NULL CHECK 0..1`, `review_status text NOT NULL DEFAULT 'PENDING' CHECK allowed`, `approval_method text`. |

### Review/audit/enrichment tables

| Table | Columns and constraints |
|---|---|
| `knowledge.pedagogy_review_event` | `review_event_id uuid PK default gen_random_uuid()`, `entity_kind text NOT NULL` with final CHECK allowing `skill`, `skill_concept`, `skill_relation`, `concept_relation`, `problem_skill`, `problem_pedagogy`, `problem_concept`, `problem_technique`, `entity_key jsonb NOT NULL`, `before_snapshot jsonb NOT NULL`, `after_snapshot jsonb NOT NULL`, `reviewer text NOT NULL`, `review_note text NOT NULL CHECK length(btrim) BETWEEN 10 AND 2000`, `reviewed_at timestamptz DEFAULT now()`; index `(entity_kind, reviewed_at DESC)`. |
| `knowledge.pedagogy_publication` | `publication_id uuid PK default gen_random_uuid()`, `source_fingerprint text NOT NULL`, `publisher text NOT NULL`, `skills_projected integer NOT NULL`, `edges_projected integer NOT NULL`, `published_at timestamptz DEFAULT now()`. |
| `knowledge.metadata_approval_event` | `event_id uuid PK default gen_random_uuid()`, `entity_kind text NOT NULL`, `before_snapshot jsonb`, `after_snapshot jsonb NOT NULL`, `approved_at timestamptz DEFAULT now()`. Populated by automatic audit trigger. |
| `knowledge.enrichment_job` | `problem_id uuid PK FK core.problem ON DELETE CASCADE`, `status text CHECK IN ('IN_PROGRESS','COMPLETED','FAILED')`, `attempts integer NOT NULL DEFAULT 1`, `last_error text`, `updated_at timestamptz DEFAULT now()`, `published_at timestamptz`. |
| `knowledge.relationship_enrichment_job` | `entity_kind text CHECK IN ('skill','concept')`, `anchor_id uuid`, `input_hash text NOT NULL`, `status text CHECK IN ('IN_PROGRESS','COMPLETED','FAILED')`, `attempts integer NOT NULL DEFAULT 1`, `last_error text`, `evidence jsonb`, `edges_inserted integer NOT NULL DEFAULT 0`, `updated_at timestamptz DEFAULT now()`, `published_at timestamptz`; PK `(entity_kind, anchor_id)`; partial outbox index on `updated_at WHERE status='COMPLETED' AND published_at IS NULL`. |

Functions/triggers:

- `knowledge.apply_automatic_approval()` BEFORE INSERT/UPDATE trigger function on metadata tables. Unless `mathbank.human_review='on'`, PENDING rows become REVIEWED with `approval_method='automatic'`. It protects human-approved/human-rejected rows and rejected rows from automatic overwrites.
- `knowledge.record_automatic_approval()` AFTER INSERT/UPDATE trigger function records automatic changes in `knowledge.metadata_approval_event`.
- Triggers named `automatic_metadata` and `automatic_metadata_audit` are installed by dynamic DO block on `skill`, `skill_concept`, `skill_relation`, `problem_skill`, `problem_pedagogy`, `problem_concept`, `problem_technique`, and `concept_relation`.

## `search` schema

| Table | Columns and constraints |
|---|---|
| `search.embedding_model` | `embedding_model_id uuid PK`, `provider`, `model_name`, `model_revision`, `dimensions int CHECK >0`, `distance_metric text DEFAULT 'COSINE'`, `normalization`, `status DEFAULT 'REGISTERED'`, `activated_at`, `retired_at`, `metadata jsonb DEFAULT '{}'`; UNIQUE `(provider, model_name, model_revision)`. |
| `search.preprocessing_profile` | `preprocessing_profile_id uuid PK`, `name text`, `version int`, `configuration jsonb DEFAULT '{}'`, `code_revision`, `created_at`; UNIQUE `(name, version)`. `011` seeds `('pedagogy_step_v2',1)`. |
| `search.representation` | `representation_id uuid PK`, `source_entity_type text`, `source_entity_id uuid`, `representation_kind text`, `preprocessing_profile_id uuid FK`, `rendered_text text`, `content_hash text`, `source_updated_at`, `generated_at DEFAULT now()`, `status DEFAULT 'ACTIVE'`, `metadata jsonb DEFAULT '{}'`; UNIQUE `(source_entity_type, source_entity_id, representation_kind, preprocessing_profile_id, content_hash)`; index `(source_entity_type, source_entity_id, status)`. |
| `search.chunk` | `chunk_id uuid PK`, `representation_id uuid FK search.representation ON DELETE CASCADE`, `chunk_ordinal int`, `chunk_kind text`, `chunk_text text`, `chunk_hash text`, `token_count int`, `char_count int`, `parent_chunk_id uuid FK self`, `problem_id uuid FK core.problem`, `solution_id uuid FK core.solution`, `concept_id uuid FK knowledge.concept`, `technique_id uuid FK knowledge.technique`, `metadata jsonb DEFAULT '{}'`, generated `textsearch tsvector`, `created_at DEFAULT now()`, plus `solution_step_id text FK pedagogy.solution_step ON DELETE CASCADE`, `learning_item_id text FK pedagogy.learning_item ON DELETE CASCADE`, `skill_node_id text FK pedagogy.taxonomy_node ON DELETE SET NULL`, `subconcept_node_id text FK pedagogy.taxonomy_node ON DELETE SET NULL`, `concept_node_id text FK pedagogy.taxonomy_node ON DELETE SET NULL`; UNIQUE `(representation_id, chunk_ordinal)`; CHECK `chunk_single_pedagogy_owner` requires not both `solution_step_id` and `learning_item_id`. |
| `search.embedding` | `embedding_id uuid PK`, `chunk_id uuid FK search.chunk ON DELETE CASCADE`, `embedding_model_id uuid FK search.embedding_model`, `embedding vector NOT NULL`, `embedding_hash text`, `generated_at DEFAULT now()`, `status DEFAULT 'ACTIVE'`, `metadata jsonb DEFAULT '{}'`; UNIQUE `(chunk_id, embedding_model_id)`; index `(embedding_model_id, status)`. |
| `search.embedding_job` | `embedding_job_id uuid PK`, `run_id uuid FK pipeline.run`, `representation_id uuid FK`, `embedding_model_id uuid FK`, `status DEFAULT 'PENDING'`, `attempt_count DEFAULT 0`, `input_hash text NOT NULL`, timestamps, `worker_id`, `last_error`, `metrics jsonb DEFAULT '{}'`; UNIQUE `(representation_id, embedding_model_id, input_hash)`. |
| `search.retrieval_profile` | `retrieval_profile_id uuid PK`, `name`, `version`, `configuration jsonb`, `status DEFAULT 'ACTIVE'`, `created_at`; UNIQUE `(name, version)`. |

Indexes: GIN FTS/trigram on chunk text, btree problem/solution, partial btree on step/item/taxonomy columns, GIN `metadata jsonb_path_ops`, optional HNSW index created by `embed_corpus.py index` for active `text-embedding-3-small` embeddings.

## `pipeline` schema

| Table | Columns and constraints |
|---|---|
| `pipeline.run` | `run_id uuid PK`, `run_type text`, `requested_scope jsonb DEFAULT '{}'`, `status text`, `started_at`, `completed_at`, `heartbeat_at`, `worker_id`, `expected_items int`, `completed_items int DEFAULT 0`, `failed_items int DEFAULT 0`, `metadata jsonb DEFAULT '{}'`; index `(status, started_at DESC)`. |
| `pipeline.work_item` | `work_item_id uuid PK`, `run_id uuid FK pipeline.run ON DELETE CASCADE`, `item_type`, `item_key`, `status DEFAULT 'PENDING'`, `attempt_count DEFAULT 0`, lease/timestamp/error/hash fields, `metrics jsonb DEFAULT '{}'`; UNIQUE `(run_id, item_type, item_key)`; claim index `(status, lease_expires_at)`. |
| `pipeline.graph_projection` | `projection_run_id uuid PK`, `graph_name text`, `source_watermark DEFAULT now()`, `started_at DEFAULT now()`, `completed_at`, `nodes_upserted int DEFAULT 0`, `edges_upserted int DEFAULT 0`, `status DEFAULT 'IN_PROGRESS'`, `error text`. |
| `pipeline.pdf_source` | `pdf_source_id uuid PK`, `paper_external_code text UNIQUE`, `competition_external_code text`, `crawl_dir text`, `problem_url`, `solution_url`, `link_scope`, `download_status DEFAULT 'PENDING'`, `downloaded_at`, `parse_status DEFAULT 'PENDING'`, `parsed_at`, `questions_found int DEFAULT 0`, `ingest_status DEFAULT 'PENDING'`, `ingested_at`, `questions_ingested int DEFAULT 0`, `solutions_ingested int DEFAULT 0`, `last_error`, `created_at DEFAULT now()`, `updated_at DEFAULT now()`, `source_kind text NOT NULL DEFAULT 'PDF'`; indexes status tuple and `(source_kind, download_status)`. |
| `pipeline.outbox_event` | `outbox_event_id uuid PK DEFAULT gen_random_uuid()`, `event_type text NOT NULL`, `aggregate_type text NOT NULL`, `aggregate_id text NOT NULL`, `payload jsonb NOT NULL DEFAULT '{}'`, `created_at timestamptz NOT NULL DEFAULT clock_timestamp()`; index `(created_at)`. Written in the same transaction as runtime mutations for async consumers. |
| `pipeline.outbox_consumption` | `outbox_event_id uuid FK pipeline.outbox_event ON DELETE CASCADE`, `consumer_name text NOT NULL`, `processed_at timestamptz NOT NULL DEFAULT now()`; PK `(outbox_event_id, consumer_name)`. Used by `mathbank_rest.outbox_worker` consumers `learner_analytics` and `projection_requests`; the side effect and this row are written in one transaction (migration 018 behavior). |
| `pipeline.projection_request` | Migration 018 (+019). `projection_request_id uuid PK DEFAULT gen_random_uuid()`, `target text NOT NULL CHECK IN ('GRAPH_TEXTBOOK_STEPS','STEP_EMBEDDINGS','LEARNING_ITEM_EMBEDDINGS','GRAPH_LEARNING_ITEMS')`, `scope_type text NOT NULL CHECK IN ('BOOK','PACKAGE','PROBLEM','STEP','LEARNING_ITEM')`, `scope_id text NOT NULL`, `reason text NOT NULL`, `source_outbox_event_id uuid FK pipeline.outbox_event ON DELETE SET NULL`, `status text NOT NULL DEFAULT 'PENDING' CHECK IN ('PENDING','DONE','CANCELLED')`, `requested_at timestamptz NOT NULL DEFAULT now()`, `completed_at`, `completed_by text`, `requested_by text` (019); partial UNIQUE `projection_request_open_uq (target, scope_type, scope_id) WHERE status='PENDING'`. |

## `learner` schema

| Table | Columns and constraints |
|---|---|
| `learner.student_profile` | `student_id uuid PK`, `email text NOT NULL UNIQUE`, `password_hash text NOT NULL`, `display_name text`, `status text NOT NULL DEFAULT 'ACTIVE'`, `created_at DEFAULT now()`, `last_login_at`, `first_name text`, `last_name text`. |
| `learner.attempt` | `attempt_id uuid PK`, `student_id uuid FK learner.student_profile ON DELETE CASCADE`, `problem_id uuid FK core.problem`, `is_correct boolean`, `submitted_answer text`, `time_spent_seconds int CHECK null or >=0`, `hint_count int DEFAULT 0`, `attempted_at DEFAULT now()`, `source text DEFAULT 'web'`; indexes by student/time and problem. Append-only by application convention. |
| `learner.concept_mastery` | `(student_id, concept_id)` PK, FKs to profile `ON DELETE CASCADE` and concept, `mastery_score numeric CHECK 0..1`, counts, `last_attempt_at`, `updated_at DEFAULT now()`; index by student. |
| `learner.technique_mastery` | `(student_id, technique_id)` PK, FKs to profile `ON DELETE CASCADE` and technique, same score/count columns; index by student. |
| `learner.solve_attempt` | `solve_attempt_id uuid PK`, `student_id uuid FK learner.student_profile ON DELETE CASCADE`, `problem_id uuid FK core.problem`, `attempt_number integer CHECK >=1`, `status text DEFAULT 'IN_PROGRESS' CHECK IN ('IN_PROGRESS','SUBMITTED','COMPLETED','ABANDONED')`, start/submit/complete timestamps, current `pedagogy.solution_part`/`solution_step` refs, optional `recovery_plan_id uuid` with Phase 10 FK to `pedagogy.recovery_plan ON DELETE SET NULL`, `outcome_attempt_id uuid FK learner.attempt ON DELETE SET NULL`, `metadata jsonb DEFAULT '{}'`; UNIQUE `(student_id, problem_id, attempt_number)`; partial UNIQUE `(student_id, problem_id) WHERE status='IN_PROGRESS'`; index `(student_id, started_at DESC)`. |
| `learner.attempt_step_state` | PK `(solve_attempt_id, solution_step_id)`, FKs to solve attempt `ON DELETE CASCADE` and `pedagogy.solution_step`, state enum (`NOT_SEEN`, `PRESENTED`, `ATTEMPTED`, success/failure/retry/skip states), first/last timestamps, `independent_success`, `help_level_used integer DEFAULT 0 CHECK 0..5`, `attempt_count CHECK >=0`, last response/evaluation/evidence jsonb; CHECK independent success implies no help. |
| `learner.event` | `event_id uuid PK`, `student_id uuid FK learner.student_profile ON DELETE CASCADE`, optional `solve_attempt_id uuid FK learner.solve_attempt ON DELETE CASCADE`, constrained `event_type` enum for attempt/step/hint/gap-diagnosis/recovery lifecycle, including `GAP_DIAGNOSED`, `GAP_HYPOTHESIS_RESOLVED`, and the `RECOVERY_*` / return events after migration 015, `event_time DEFAULT clock_timestamp()`, `actor_type` enum, optional `solution_step_id FK pedagogy.solution_step`, `payload jsonb DEFAULT '{}'`, optional `idempotency_key text`; UNIQUE `(student_id, idempotency_key)`; indexes by attempt/time and student/time. BEFORE UPDATE OR DELETE trigger makes it append-only. Migration 018 re-creates the CHECK with `ATTEMPT_ABANDONED`. |
| `learner.idempotency_record` | PK `(student_id, idempotency_key)`, FK student `ON DELETE CASCADE`, `idempotency_key text CHECK length 1..200`, `operation text`, `request_hash text`, `response jsonb`, `created_at DEFAULT now()`. |
| `learner.agent_session_link` | `agent_session_link_id uuid PK DEFAULT gen_random_uuid()`, `agent_app_name text NOT NULL`, `agent_user_id text NOT NULL`, `agent_session_id text NOT NULL`, `student_id uuid NOT NULL FK learner.student_profile ON DELETE CASCADE`, `surface text NOT NULL DEFAULT 'HOME_CHAT' CHECK IN ('HOME_CHAT','SOLVE_WORKSPACE','OTHER')`, `context jsonb NOT NULL DEFAULT '{}'`, `created_at`/`last_seen_at timestamptz NOT NULL DEFAULT now()`; UNIQUE `(agent_app_name, agent_session_id)` (`agent_session_link_session_uq`); index `(student_id, created_at DESC)`. `(agent_app_name, agent_user_id, agent_session_id)` is a **logical** link to `agent_sessions.sessions(app_name, user_id, id)` with no FK (framework-owned schema). Migration 016. |

## `ingest` schema

| Table | Columns and constraints |
|---|---|
| `ingest.content_package` | `content_package_id uuid PK`, `package_name`, `package_version`, `manifest_hash`, `book_code`, `source_root`, `status` CHECK package lifecycle enum, `status_detail`, `last_scope`, `report jsonb DEFAULT '{}'`, timestamps, `imported_at`; UNIQUE `(package_name, package_version, manifest_hash)`. |
| `ingest.package_status_event` | `event_id bigserial PK`, `content_package_id uuid FK ON DELETE CASCADE`, `from_status`, `to_status`, `scope`, `detail`, `created_at`. |
| `ingest.package_file` | `(content_package_id, relative_path)` PK, FK package `ON DELETE CASCADE`, `file_role`, `sha256`, `byte_size`, `row_count`. |
| `ingest.staging_row` | `staging_row_id bigserial PK`, `content_package_id uuid FK ON DELETE CASCADE`, `source_file`, `source_row_number`, `entity_type`, `external_id`, `source_row_json jsonb`, `validation_status` CHECK `PENDING/VALID/IMPORTED/REJECTED`, warnings/errors jsonb, `target_key`, timestamps; UNIQUE `(content_package_id, source_file, source_row_number)`; status index. |
| `ingest.import_conflict` | `conflict_id bigserial PK`, package FK, `entity_type`, `external_id`, `conflict_type`, `severity` CHECK `INFO/WARNING/ERROR`, `detail jsonb`, `resolution_status` CHECK enum, `resolution`, timestamps; UNIQUE `(content_package_id, entity_type, external_id, conflict_type)`. Migration 019 adds `decision text CHECK NULL or IN ('KEEP_EXISTING','ACCEPT_INCOMING','MERGE_MANUALLY')` and `decided_at timestamptz` (decision is recorded; applied by later re-import/DAG edit). |
| `ingest.reconciliation` | Composite PK `(content_package_id, scope, entity_type)`; source/valid/imported/created/updated/unchanged/rejected/conflict/present counts, `reconciled boolean`, `reconciled_at`. |
| `ingest.admin_review_action` | Migration 019. `action_id bigserial PK`, `target_type text NOT NULL CHECK IN ('IMPORT_CONFLICT','SOLUTION_STEP','STEP_DEPENDENCY','SOLUTION_DAG','LEARNING_ITEM','PROJECTION_REQUEST')`, `target_id text NOT NULL`, `action text NOT NULL`, `before_state jsonb`, `after_state jsonb`, `note text`, `actor text NOT NULL DEFAULT 'admin'`, `created_at timestamptz NOT NULL DEFAULT now()`; index `(target_type, target_id, created_at DESC)`; BEFORE UPDATE OR DELETE trigger `ingest.admin_review_action_append_only()` raises (append-only). |

## `pedagogy` schema

| Table | Columns and constraints |
|---|---|
| `pedagogy.source_book` | `book_code text PK`, `external_book_id text UNIQUE`, title/author/editor/source file, optional FK `core.competition`, FK `core.competition_edition`, `metadata jsonb`, `updated_at`. |
| `pedagogy.chapter_section` | PK `(book_code, chapter_number, section_number)`, FK book, titles, optional FK `core.paper`, FK content package. |
| `pedagogy.taxonomy_node` | `taxonomy_node_id text PK`, `node_type` CHECK `DOMAIN/CONCEPT/SUBCONCEPT/SKILL/TECHNIQUE`, name, parent/chapter/section/source/description, optional FKs to `knowledge.concept`, `knowledge.skill`, `knowledge.technique`, package FK, `updated_at`; CHECK at most one canonical bridge id. |
| `pedagogy.taxonomy_edge` | PK `(from_node_id, to_node_id, relationship_type)`, FKs to taxonomy nodes, `source_basis`, `confidence`, package FK, CHECK not self-loop. |
| `pedagogy.problem_source_ref` | PK `(book_code, source_problem_id)`, FK book, `problem_id uuid NOT NULL UNIQUE FK core.problem ON DELETE CASCADE`, chapter/section/source/page/difficulty fields, package FK. |
| `pedagogy.solution_source_ref` | PK `(book_code, source_solution_id)`, `solution_id uuid UNIQUE FK core.solution ON DELETE CASCADE`, `problem_id uuid FK core.problem ON DELETE CASCADE`, source fields, package FK. |
| `pedagogy.problem_enrichment` | `problem_id uuid PK FK core.problem ON DELETE CASCADE`, taxonomy-node FKs for concept/subconcept/primary skill, arrays `solution_step_skill_ids text[]`, `technique_ids text[]`, form/difficulty/count/confidence/source fields, package FK, `updated_at`. |
| `pedagogy.solution_part` | `solution_part_id text PK`, source id, occurrence, FK book, FK solution/problem `ON DELETE CASCADE`, labels/order/counts/page/text, package FK, `updated_at`; UNIQUE `(book_code, source_part_id, occurrence)`; index `(problem_id, part_ordinal)`. |
| `pedagogy.solution_step` | `solution_step_id text PK`, source id, occurrence, FK book, FK solution part `ON DELETE CASCADE`, FK solution/problem `ON DELETE CASCADE`, global and part indexes, `step_text`, `step_type`, `tutor_role`, taxonomy-node FKs, skill name, `hint_level` CHECK 1..4, checkpoint bool, source previous/next/page/metadata, `publication_status DEFAULT 'PUBLISHED'`, package FK, timestamps; UNIQUE `(problem_id, global_step_index)` and `(book_code, source_step_id, occurrence)`; indexes by part and skill. Migration 019 adds `admin_edited_at timestamptz` (re-import skips admin-edited rows). |
| `pedagogy.solution_step_dependency` | PK `(from_step_id, to_step_id, relationship_type)`, FKs to solution steps `ON DELETE CASCADE`, logical dependency, confidence CHECK null or 0..1, `source_type`, `review_status DEFAULT 'REVIEWED' CHECK PENDING/REVIEWED/REJECTED`, `approval_method`, `metadata jsonb`, package FK, CHECK not self-loop; index `to_step_id`. Migration 019 column comment: `relationship_type` vocabulary `NEXT | DEPENDS_ON | DERIVES_FROM | USES_RESULT_FROM | ALTERNATIVE_TO | BRANCHES_TO | JOINS_AT | JUSTIFIES` (documentation, not a CHECK); admin edits set `approval_method='human'`. |
| `pedagogy.solution_step_technique` | Migration 017. PK `(solution_step_id, technique_node_id)`; `solution_step_id text NOT NULL FK pedagogy.solution_step ON DELETE CASCADE`, `technique_node_id text NOT NULL FK pedagogy.taxonomy_node`, `confidence numeric(3,2) NOT NULL CHECK 0..1`, `source_type text NOT NULL CHECK IN ('RULE_STEP_TEXT_IN_PROBLEM','RULE_STEP_TEXT_NAMED','RULE_STEP_FORMULA','LLM','RUNTIME','HUMAN')`, `evidence text`, `derivation_version text NOT NULL`, `review_status text NOT NULL DEFAULT 'APPROVED' CHECK IN ('PENDING_REVIEW','APPROVED','REJECTED')`, `approval_method text CHECK NULL/automatic/human`, `approved_at`, `created_at`/`updated_at DEFAULT now()`; partial index `(technique_node_id) WHERE review_status='APPROVED'`. Only textbook steps have rows (non-Prasolov corpora empty by design). |
| `pedagogy.solution_step_technique_run` | Migration 017. PK `(solution_step_id, derivation_version)`; `solution_step_id FK pedagogy.solution_step ON DELETE CASCADE`, `outcome text NOT NULL CHECK IN ('TAGGED','NO_MATCH','NO_PROBLEM_TECHNIQUE')`, `candidate_ids text[] NOT NULL DEFAULT '{}'`, `created_at DEFAULT now()`. Measures coverage and the paid-tier backlog without re-running rules. |
| `pedagogy.solution_dag_review` | Migration 019. `solution_id uuid PK FK core.solution ON DELETE CASCADE`, `problem_id uuid NOT NULL FK core.problem ON DELETE CASCADE`, `status text NOT NULL CHECK IN ('APPROVED','NEEDS_REVISION')`, `note text`, `reviewed_by text NOT NULL DEFAULT 'admin'`, `reviewed_at timestamptz NOT NULL DEFAULT now()`. One current review per solution (upserted); history lives in `ingest.admin_review_action`. |
| `pedagogy.learning_item` | `learning_item_id text PK`, source transformation id, occurrence, FK book, `source_problem_id uuid FK core.problem ON DELETE CASCADE`, optional parent id, transformation/form/taxonomy target FKs, difficulty/question/choices/correct answer/seed/generation/part/diagram fields, `no_proof boolean NOT NULL CHECK(no_proof)`, `review_status DEFAULT 'PENDING_REVIEW' CHECK enum`, `student_visible boolean DEFAULT false`, `approval_method text CHECK NULL/automatic/human`, `approved_at timestamptz`, package FK, timestamps; UNIQUE `(book_code, source_transformation_id, occurrence)`; CHECK visible implies `APPROVED`; indexes source problem plus partial `(target_skill_node_id, transformation_type) WHERE student_visible` and `(target_subconcept_node_id, transformation_type) WHERE student_visible`. |
| `pedagogy.learning_item_step_anchor` | PK `(learning_item_id, solution_step_id)`, FKs learning item and solution step `ON DELETE CASCADE`, `anchor_ordinal`. |
| `pedagogy.diagram` | `diagram_id text PK`, source diagram id, FK book, FK problem `ON DELETE CASCADE`, usage, `visibility` CHECK `STUDENT_PROBLEM/SOLUTION_HIDDEN`, source page/figure/caption, asset/local paths, hash/method/status, optional FK `core.problem_image ON DELETE SET NULL`, package FK, `updated_at`; UNIQUE `(book_code, source_diagram_id)`; index `(problem_id, usage)`. |
| `pedagogy.step_hint` | Shared Phase 8 hint cache. PK `(solution_step_id, hint_level, prompt_version)`, `solution_step_id text NOT NULL FK pedagogy.solution_step ON DELETE CASCADE`, `hint_level integer NOT NULL CHECK 1..4`, `prompt_version text NOT NULL`, `hint_text text NOT NULL CHECK length>0`, `model text NOT NULL`, `leak_checked boolean NOT NULL DEFAULT true`, `created_at timestamptz NOT NULL DEFAULT now()`. Level 5 full reveal is the canonical step text and is deliberately not stored here. |
| `pedagogy.gap_diagnosis` | Phase 9 diagnosis run for one solve attempt and solution step, extended by Phase 10 optional re-rank. `gap_diagnosis_id uuid PK DEFAULT gen_random_uuid()`, `student_id uuid NOT NULL FK learner.student_profile ON DELETE CASCADE`, `solve_attempt_id uuid NOT NULL FK learner.solve_attempt ON DELETE CASCADE`, `solution_step_id text NOT NULL FK pedagogy.solution_step`, `trigger text NOT NULL CHECK AUTO/STUDENT_REQUEST/TUTOR`, `recommended_action text NOT NULL CHECK RETRY_WITH_HINT/DIAGNOSTIC_PROBE/RECOVERY_DETOUR`, `evidence_fingerprint text NOT NULL`, `evidence jsonb NOT NULL DEFAULT '{}'`, `probes jsonb NOT NULL DEFAULT '[]'`, `diagnoser_version text NOT NULL`, `ai_rerank jsonb`, `created_at timestamptz NOT NULL DEFAULT now()`; UNIQUE `(solve_attempt_id, solution_step_id, evidence_fingerprint)`; index `(student_id, created_at DESC)`. |
| `pedagogy.knowledge_gap` | Ranked hypothesis rows owned by a diagnosis. `knowledge_gap_id uuid PK DEFAULT gen_random_uuid()`, diagnosis/student/attempt FKs `ON DELETE CASCADE`, `solution_step_id text NOT NULL FK pedagogy.solution_step`, `rank integer NOT NULL CHECK >=1`, constrained `failure_location` and `failure_mode`, optional target concept/subconcept/skill IDs, optional logical `target_skill_node_id uuid` (knowledge skill link, not enforced), `target_label`, optional `source_step_id text FK pedagogy.solution_step`, `confidence numeric(4,3) CHECK 0..1`, `evidence jsonb NOT NULL DEFAULT '{}'`, `status text NOT NULL DEFAULT 'UNRESOLVED' CHECK UNRESOLVED/CONFIRMED/REJECTED/RESOLVED`, status reason/change/resolved timestamps; UNIQUE `(gap_diagnosis_id, rank)`; partial open-gap index `(student_id, target_skill_id)` for UNRESOLVED/CONFIRMED and attempt index `(solve_attempt_id)`. |
| `pedagogy.recovery_plan` | Phase 10 persisted detour from an origin solve attempt/step. `recovery_plan_id uuid PK DEFAULT gen_random_uuid()`, `student_id uuid NOT NULL FK learner.student_profile ON DELETE CASCADE`, `solve_attempt_id uuid NOT NULL FK learner.solve_attempt ON DELETE CASCADE`, `origin_problem_id uuid NOT NULL FK core.problem`, `origin_step_id text NOT NULL FK pedagogy.solution_step`, optional diagnosis/gap FKs (`gap_diagnosis_id ON DELETE SET NULL`, `knowledge_gap_id ON DELETE SET NULL`), optional `parent_recovery_plan_id uuid FK pedagogy.recovery_plan ON DELETE CASCADE`, `trigger CHECK DIAGNOSIS/STUDENT_REQUEST/TUTOR/BRANCH`, target skill/subconcept/label, `status DEFAULT 'ACTIVE' CHECK ACTIVE/SUSPENDED/COMPLETED/EXHAUSTED/ABORTED/SUPERSEDED`, optional `current_item_ordinal`, `mastery_policy jsonb NOT NULL DEFAULT` two independent successes + transfer, `outcome jsonb NOT NULL DEFAULT '{}'`, `planner_version`, timestamps. Partial unique index enforces at most one `ACTIVE` plan per solve attempt; `(student_id, created_at DESC)` index supports admin/student lists. |
| `pedagogy.recovery_plan_item` | Ordered items in a recovery plan. `recovery_plan_item_id uuid PK DEFAULT gen_random_uuid()`, `recovery_plan_id uuid NOT NULL FK pedagogy.recovery_plan ON DELETE CASCADE`, `ordinal integer CHECK >=1`, `stage CHECK FOUNDATION/RECOGNITION/ISOLATED_EXECUTION/GUIDED_APPLICATION/TRANSFER/RETURN_TO_STEP`, `item_kind CHECK LEARNING_ITEM/THEORY/RETURN`, optional `learning_item_id text FK pedagogy.learning_item`, optional `worked_step_id text FK pedagogy.solution_step`, `is_transfer boolean DEFAULT false`, `required boolean DEFAULT true`, `status DEFAULT 'PENDING' CHECK PENDING/PRESENTED/PASSED/FAILED/SKIPPED`, `tries integer DEFAULT 0`, optional `independent_success`, `last_response jsonb`, `last_result jsonb`, `added_reason DEFAULT 'PLANNED'`, presented/completed timestamps; UNIQUE `(recovery_plan_id, ordinal)`; CHECK ensures only `LEARNING_ITEM` rows have `learning_item_id`. |

Comments mark `pedagogy.diagram` solution-hidden diagrams as not student-facing and `pedagogy.learning_item` as not student-visible unless approved.

## `analytics` schema

| Table | Columns and constraints |
|---|---|
| `analytics.learner_daily_activity` | Migration 018. PK `(student_id, activity_date)`; `student_id uuid NOT NULL FK learner.student_profile ON DELETE CASCADE`, `activity_date date NOT NULL` (UTC day), integer counters `NOT NULL DEFAULT 0`: `attempts_started`, `attempts_completed`, `attempts_abandoned`, `steps_evaluated`, `steps_succeeded`, `gaps_diagnosed`, `knowledge_gaps_created`, `recovery_plans_created`, `recovery_plans_completed`; `updated_at DEFAULT now()`. Mutable, rebuildable cache — `learner.event` remains the source of truth. |

## `tutor` schema

| Table | Columns and constraints |
|---|---|
| `tutor.runtime_state` | PK `(student_id, solve_attempt_id)`, `student_id uuid FK learner.student_profile ON DELETE CASCADE`, `solve_attempt_id uuid FK learner.solve_attempt ON DELETE CASCADE`, `current_mode text DEFAULT 'SOLVING' CHECK IN ('SOLVING','DIAGNOSING','RECOVERY','REVIEW','COMPLETED')`, `current_problem_id uuid FK core.problem`, optional `current_step_id text FK pedagogy.solution_step`, optional `current_recovery_plan_id uuid` with Phase 10 FK to `pedagogy.recovery_plan ON DELETE SET NULL`, `last_agent_turn_id text`, `state_version bigint DEFAULT 1 CHECK >=1`, `updated_at DEFAULT now()`. |

## `authoring` schema (migration 020)

| Table | Columns and constraints |
|---|---|
| `authoring.presentation_plan` | PK `plan_id uuid DEFAULT gen_random_uuid()`; `plan_key text NOT NULL`; `version integer NOT NULL DEFAULT 1 CHECK >= 1`; `parent_plan_id uuid FK self ON DELETE SET NULL`; `title text NOT NULL`; `description text`; `status text NOT NULL DEFAULT 'DRAFT' CHECK IN (DRAFT, APPROVED, PUBLISHED, SUPERSEDED)`; `course_limit_seconds integer NOT NULL CHECK > 0`; `interaction_buffer_seconds integer NOT NULL DEFAULT 0 CHECK >= 0`; `hard_limit boolean NOT NULL DEFAULT false`; `created_by text NOT NULL DEFAULT 'admin'`; `created_at`/`updated_at timestamptz NOT NULL DEFAULT now()`; `approved_at`, `published_at timestamptz`; UNIQUE `(plan_key, version)`. Trigger `presentation_plan_guard` (BEFORE UPDATE OR DELETE → `authoring.guard_published_plan()`): PUBLISHED rows cannot be deleted; PUBLISHED/SUPERSEDED rows cannot be updated except PUBLISHED → SUPERSEDED with title/limits unchanged. |
| `authoring.plan_topic` | PK `topic_id uuid`; `plan_id uuid NOT NULL FK presentation_plan ON DELETE CASCADE`; `ordinal integer NOT NULL CHECK >= 0`; `title text NOT NULL`; `concept`, `problem_ref text`; `planned_seconds integer NOT NULL CHECK > 0`; `min_seconds`, `max_seconds integer` (NULL or > 0); `required boolean NOT NULL DEFAULT true`; `scenes jsonb NOT NULL DEFAULT '[]' CHECK array`; UNIQUE `(plan_id, ordinal) DEFERRABLE INITIALLY DEFERRED`. Trigger `plan_topic_guard` (BEFORE INSERT/UPDATE/DELETE → `guard_published_topic()`) rejects any change when the parent plan is PUBLISHED/SUPERSEDED. |
| `authoring.chat_session` | PK `chat_session_id uuid`; `plan_id uuid NOT NULL FK presentation_plan ON DELETE CASCADE`; `actor text NOT NULL DEFAULT 'admin'`; `created_at`. |
| `authoring.proposed_patch` | PK `patch_id uuid`; `chat_session_id FK chat_session ON DELETE CASCADE`; `plan_id FK presentation_plan ON DELETE CASCADE`; `summary text NOT NULL`; `operations jsonb NOT NULL CHECK array`; `impact`, `validation jsonb NOT NULL DEFAULT '{}'`; `proposer text NOT NULL DEFAULT 'DETERMINISTIC_PARSER'`; `status text NOT NULL DEFAULT 'PROPOSED' CHECK IN (PROPOSED, APPLIED, REJECTED, SUPERSEDED)`; `result_plan_id uuid FK presentation_plan ON DELETE SET NULL`; `decided_by text`, `decided_at`, `created_at`. Index `proposed_patch_chat_idx (chat_session_id, created_at)`. |
| `authoring.chat_message` | PK `message_id bigserial`; `chat_session_id FK chat_session ON DELETE CASCADE`; `role text NOT NULL CHECK IN (ADMIN, ASSISTANT, SYSTEM)`; `content text NOT NULL`; `patch_id uuid FK proposed_patch ON DELETE SET NULL`; `created_at`. Index `chat_message_session_idx (chat_session_id, message_id)`. |

Both guard functions honour the session setting `SET authoring.allow_purge = 'on'` as an explicit operator escape hatch (used for test cleanup); application code never sets it.

## `live` schema (migration 020)

| Table | Columns and constraints |
|---|---|
| `live.session` | PK `live_session_id uuid`; `plan_id uuid FK authoring.presentation_plan ON DELETE SET NULL`; `title text NOT NULL`; `join_code text NOT NULL UNIQUE`; `status text NOT NULL DEFAULT 'SCHEDULED' CHECK IN (SCHEDULED, ACTIVE, PAUSED, COMPLETED, CANCELLED)`; `control_mode text NOT NULL DEFAULT 'AI_ACTIVE' CHECK IN (AI_ACTIVE, INSTRUCTOR_ACTIVE)`; `controller text`; `agent_locked boolean NOT NULL DEFAULT false`; `state_version bigint NOT NULL DEFAULT 1 CHECK >= 1`; `last_sequence bigint NOT NULL DEFAULT 0 CHECK >= 0`; `current_topic_index`, `current_scene_index integer NOT NULL DEFAULT 0`; `course_limit_seconds integer NOT NULL CHECK > 0`; `interaction_buffer_seconds integer NOT NULL DEFAULT 0`; `hard_limit boolean NOT NULL DEFAULT false`; `extension_seconds integer NOT NULL DEFAULT 0`; `started_at`, `paused_at`, `topic_started_at`, `completed_at timestamptz`; `paused_total_seconds integer NOT NULL DEFAULT 0`; `stage jsonb NOT NULL DEFAULT '{}'`; `topics jsonb NOT NULL DEFAULT '[]'` (added by `ALTER … ADD COLUMN IF NOT EXISTS`; snapshot of the plan topics at session creation); `created_by text NOT NULL DEFAULT 'admin'`; `created_at`, `updated_at`. |
| `live.participant` | PK `(live_session_id, participant_id)`; `live_session_id FK session ON DELETE CASCADE`; `participant_id text NOT NULL`; `role text NOT NULL CHECK IN (STUDENT, INSTRUCTOR, OBSERVER)`; `student_id uuid FK learner.student_profile ON DELETE SET NULL`; `display_name text NOT NULL`; `group_id text`; `control_mode text NOT NULL DEFAULT 'AI_ACTIVE'` (same CHECK); `confused boolean NOT NULL DEFAULT false`; `joined_at`, `last_seen_at`. Partial index `participant_student_idx (student_id) WHERE student_id IS NOT NULL`. |
| `live.session_event` | PK `(live_session_id, sequence)`; `live_session_id FK session ON DELETE CASCADE`; `sequence bigint NOT NULL CHECK >= 1`; `event_id uuid NOT NULL UNIQUE DEFAULT gen_random_uuid()`; `event_type text NOT NULL`; `session_version bigint NOT NULL`; `correlation_id`, `causation_id text`; `actor_type text NOT NULL CHECK IN (STUDENT, INSTRUCTOR, ADMIN, AI_TUTOR, SYSTEM)`; `actor_id text`; `audience text NOT NULL DEFAULT 'SESSION' CHECK IN (SESSION, STUDENT, INSTRUCTOR, GROUP)`; `audience_id text`; `payload jsonb NOT NULL DEFAULT '{}'`; `created_at timestamptz NOT NULL DEFAULT clock_timestamp()`. Trigger `session_event_append_only` is **BEFORE UPDATE only** (raises); DELETE is not blocked, so session cascades still work. |
| `live.command_receipt` | PK `(live_session_id, client_command_id)`; `live_session_id FK session ON DELETE CASCADE`; `command_type text NOT NULL`; `actor_type text NOT NULL`; `actor_id text`; `status text NOT NULL CHECK IN (ACCEPTED, REJECTED)`; `result jsonb NOT NULL DEFAULT '{}'`; `created_at`. Idempotency store for live commands. |
| `live.topic_run` | PK `(live_session_id, topic_index)`; FK session ON DELETE CASCADE; `title text NOT NULL`; `planned_seconds integer NOT NULL`; `started_at`, `ended_at`; `actual_seconds integer`; `status text NOT NULL DEFAULT 'PENDING' CHECK IN (PENDING, ACTIVE, DONE, SKIPPED)`. |
| `live.recommendation` | PK `recommendation_id uuid`; FK session ON DELETE CASCADE; `source text NOT NULL CHECK IN (AI_TUTOR, INSTRUCTOR_NL, TIME_ORCHESTRATOR, POLL_BRANCH, VISUAL_AGENT)`; `action jsonb NOT NULL`; `rationale text`; `based_on_version bigint NOT NULL`; `status text NOT NULL DEFAULT 'PROPOSED' CHECK IN (PROPOSED, ACCEPTED, REJECTED, STALE)`; `decided_by`, `decided_at`, `created_at`. Index `recommendation_session_idx (live_session_id, created_at DESC)`. |
| `live.takeover` | PK `takeover_id uuid`; FK session ON DELETE CASCADE; `scope text NOT NULL CHECK IN (SESSION, STUDENT, GROUP)`; `scope_id text NOT NULL DEFAULT '*'`; `instructor text NOT NULL`; `handoff_packet jsonb NOT NULL DEFAULT '{}'`; `started_at`, `ended_at`. Partial unique index `takeover_active_uidx (live_session_id, scope, scope_id) WHERE ended_at IS NULL` (one active takeover per scope). |

## `activity` schema (migration 020)

| Table | Columns and constraints |
|---|---|
| `activity.definition` | PK `activity_id uuid`; `activity_type text NOT NULL CHECK IN (MCQ, MULTISELECT, NUMERIC, SHORT_RESPONSE, SUBPROBLEM, STEP_ORDERING, ERROR_DIAGNOSIS, CONFIDENCE_CHECK, LIVE_POLL)`; `prompt text NOT NULL`; `options jsonb NOT NULL DEFAULT '[]' CHECK array`; `correctness_policy jsonb NOT NULL DEFAULT '{}'`; `target_skill text` (logical, no FK); `estimated_seconds integer NOT NULL DEFAULT 60 CHECK > 0`; `source_type text NOT NULL CHECK IN (PRECOMPILED, CORPUS_DERIVED, LIVE_AGENT_CREATED, INSTRUCTOR_CREATED)`; `source_lineage jsonb NOT NULL DEFAULT '{}'`; `persistence_mode text NOT NULL DEFAULT 'SESSION' CHECK IN (STATIC, SESSION, EPHEMERAL)`; `created_by text NOT NULL`; `created_at`. |
| `activity.instance` | PK `activity_instance_id uuid`; `live_session_id FK live.session ON DELETE CASCADE`; `activity_id FK definition ON DELETE RESTRICT`; `status text NOT NULL DEFAULT 'OPEN' CHECK IN (OPEN, CLOSED, REVEALED)`; `anonymous boolean NOT NULL DEFAULT true`; `opened_by text NOT NULL`; `opened_at`, `closes_at`, `closed_at`. Index `activity_instance_session_idx (live_session_id, opened_at DESC)`. |
| `activity.response` | PK `response_id uuid`; `activity_instance_id FK instance ON DELETE CASCADE`; `participant_id text NOT NULL` (logical link to `live.participant`, no FK); `response jsonb NOT NULL`; `confidence smallint` (NULL or 1–5); `is_correct boolean`; `client_command_id text`; `submitted_at`; UNIQUE `(activity_instance_id, participant_id)`. |

## `visual` schema (migration 020)

| Table | Columns and constraints |
|---|---|
| `visual.widget_spec` | PK `widget_spec_id uuid`; `widget_type text NOT NULL` (validated against the registry in code, not by CHECK); `spec_version text NOT NULL DEFAULT '1'`; `title text`; `spec jsonb NOT NULL`; `lifecycle text NOT NULL DEFAULT 'VALIDATED' CHECK IN (REQUESTED, SPEC_GENERATED, VALIDATED, READY, SHOWN, EXPIRED, REJECTED, PROMOTION_CANDIDATE, PROMOTED_TO_TEMPLATE)`; `persistence text NOT NULL DEFAULT 'SESSION' CHECK IN (STATIC, SESSION, EPHEMERAL)`; `live_session_id uuid FK live.session ON DELETE CASCADE` (NULL for gallery/static specs); `source_type` (same CHECK as activity); `source_lineage`, `validation jsonb NOT NULL DEFAULT '{}'`; `content_hash text NOT NULL`; `created_by text NOT NULL`; `created_at`, `expires_at`; `reviewed_by`, `reviewed_at`. Indexes `widget_spec_session_idx (live_session_id, created_at DESC)`, `widget_spec_lifecycle_idx (lifecycle, created_at DESC)`. |
| `visual.widget_state` | PK `(live_session_id, widget_instance_id)`; `live_session_id FK live.session ON DELETE CASCADE`; `widget_instance_id text NOT NULL`; `widget_spec_id uuid NOT NULL FK widget_spec ON DELETE CASCADE`; `state jsonb NOT NULL DEFAULT '{}'`; `state_version bigint NOT NULL DEFAULT 1`; `visible boolean NOT NULL DEFAULT true`; `updated_at`. |
| `visual.asset` | PK `asset_id uuid`; `uri`, `mime_type`, `content_hash text NOT NULL`; `source_problem_id uuid FK core.problem ON DELETE SET NULL`; `diagram_id text FK pedagogy.diagram ON DELETE SET NULL`; `created_by_agent text`; `persistence_mode` (STATIC/SESSION/EPHEMERAL, default SESSION); `validation_status text NOT NULL DEFAULT 'PENDING' CHECK IN (PENDING, VALID, REJECTED)`; `created_at`, `expires_at`. Index `asset_hash_idx (content_hash)`. **No code path writes this table yet** (NYI). |

## Relationships and cascades

- Deleting a `core.problem` cascades to `core.solution`, `core.problem_image`, learner attempts via student profile only not problem, many `knowledge.*` assertion rows, pedagogy source refs/enrichment/solution DAG/learning items/diagrams, and search chunks that reference deleted pedagogy steps/items.
- `knowledge.skill` deletion cascades to skill-concept and skill-relation rows where it is the source/target in FK definitions using `ON DELETE CASCADE`; problem-skill references do not specify cascade for `skill_id`.
- `learner.student_profile` deletion cascades legacy attempts, step-runtime solve attempts, events, idempotency records, runtime state, mastery rows and agent session links (ADK `agent_sessions` rows are not deleted by the project).
- `ingest.content_package` deletion cascades package files, status events, staging rows, conflicts/reconciliations only where specified; many pedagogy rows reference package without cascade defaults.
- `search.representation` deletion cascades chunks; `search.chunk` deletion cascades embeddings.
- `learner.event` is append-only by trigger; normal runtime code inserts new rows and never updates/deletes them. A hard student-profile delete would conflict with the trigger unless an audited admin action disables it.
- `pipeline.outbox_consumption` cascades when the corresponding outbox event is deleted.
- `pedagogy.step_hint` rows cascade when their `pedagogy.solution_step` is deleted; no learner or attempt foreign key exists because levels 1–4 are shared across students for a `(step, level, prompt_version)` cache key.
- `pedagogy.gap_diagnosis` cascades with its learner profile or solve attempt; `pedagogy.knowledge_gap` cascades with its diagnosis, learner profile or solve attempt. `target_skill_node_id` is a logical UUID link to `knowledge.skill` and is intentionally not enforced by migration 014.
- `pedagogy.recovery_plan` cascades with student profiles, solve attempts and parent plans; its optional diagnosis/gap links are set NULL if those rows are removed. `pedagogy.recovery_plan_item` cascades with its plan. `learner.solve_attempt.recovery_plan_id` and `tutor.runtime_state.current_recovery_plan_id` are nullable pointers cleared on plan deletion.
- Migration 020: deleting an `authoring.presentation_plan` cascades its topics, chat sessions, proposed patches and chat messages, sets `live.session.plan_id`, `parent_plan_id` and `proposed_patch.result_plan_id` to NULL, and is blocked for PUBLISHED plans by trigger. Deleting a `live.session` cascades participants, session events, command receipts, topic runs, recommendations, takeovers, activity instances (and their responses), session widget specs and widget states. `activity.instance → activity.definition` is `ON DELETE RESTRICT`. Deleting a student profile sets `live.participant.student_id` to NULL (the participant row and its events remain). `visual.asset` links to problems/diagrams are SET NULL. Live events are also written to `pipeline.outbox_event` (no FK).

## Agent session schema

`mathbank-agent/session_config.py` sets `SESSION_SCHEMA = 'agent_sessions'`. `prepare_session_schema()` executes `CREATE SCHEMA IF NOT EXISTS agent_sessions`; `create_session_service()` creates a SQLAlchemy async engine and uses `SET LOCAL search_path TO agent_sessions` on transaction begin. The actual session tables are created/managed by Google ADK `DatabaseSessionService`, not by MathBank migrations. `server.py` verifies storage by listing sessions at startup and registers the service under `mathbank-postgres://sessions` for the ADK FastAPI app.

Table shapes as read by MathBank code (`mathbank-rest/src/mathbank_rest/agent_transcripts.py`), not a framework DDL guarantee: `agent_sessions.sessions(app_name, user_id, id, create_time, update_time, …)` and `agent_sessions.events(app_name, user_id, session_id, timestamp, event_data jsonb, …)`. Timestamps are `timestamp without time zone` holding UTC; the REST layer appends an explicit UTC offset. The project links sessions to students in `learner.agent_session_link` (migration 016) and reads events read-only to rebuild transcripts ([22](../22_AGENT_SESSION_TRANSCRIPTS.md)).
