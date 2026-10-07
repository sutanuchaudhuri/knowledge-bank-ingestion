# PostgreSQL `search` schema

**Role:** Derived search representations. Lexical/chunk metadata and vector indexes/model profiles; separate from canonical solution truth.

**Access family:** `/v1/search/*`, similar-step and recovery retrieval; explicit corpus/step embedding jobs.

**Evidence:** live catalog metadata at 2026-10-07T13:40:57.292324+00:00; source `375f3743357cef814c50e3c8752f7f4ce2d6ebe5`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `search.chunk`

**Kind / use case:** table. Searchable text chunks linked to problems/solutions/steps/items.

**Migration owner:** [002_vector_schema.sql](../../../mathbank-db/sql/002_vector_schema.sql#L54); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/corpus_authoring.py](../../../mathbank-rest/src/mathbank_rest/corpus_authoring.py#L252); [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L108); [mathbank-rest/src/mathbank_rest/db/vector_search.py](../../../mathbank-rest/src/mathbank_rest/db/vector_search.py#L1); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L90); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L167); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L74); [mathbank-db/etl/embed_corpus.py](../../../mathbank-db/etl/embed_corpus.py#L3); [mathbank-db/etl/embed_textbook_steps.py](../../../mathbank-db/etl/embed_textbook_steps.py#L4); [mathbank-db/etl/repair_question_text.py](../../../mathbank-db/etl/repair_question_text.py#L179); [mathbank-agent/agents/mathbank_tutor/agent.py](../../../mathbank-agent/agents/mathbank_tutor/agent.py#L4).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `chunk_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `representation_id` | `uuid` | no | `-` | `- / -` |
| `chunk_ordinal` | `integer` | no | `-` | `- / -` |
| `chunk_kind` | `text` | no | `-` | `- / -` |
| `chunk_text` | `text` | no | `-` | `- / -` |
| `chunk_hash` | `text` | no | `-` | `- / -` |
| `token_count` | `integer` | yes | `-` | `- / -` |
| `char_count` | `integer` | no | `-` | `- / -` |
| `parent_chunk_id` | `uuid` | yes | `-` | `- / -` |
| `problem_id` | `uuid` | yes | `-` | `- / -` |
| `solution_id` | `uuid` | yes | `-` | `- / -` |
| `concept_id` | `uuid` | yes | `-` | `- / -` |
| `technique_id` | `uuid` | yes | `-` | `- / -` |
| `metadata` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `textsearch` | `tsvector` | yes | `to_tsvector('english'::regconfig, COALESCE(chunk_text, ''::text))` | `- / s` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `solution_step_id` | `text` | yes | `-` | `- / -` |
| `learning_item_id` | `text` | yes | `-` | `- / -` |
| `skill_node_id` | `text` | yes | `-` | `- / -` |
| `subconcept_node_id` | `text` | yes | `-` | `- / -` |
| `concept_node_id` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `chunk_char_count_not_null` / `n` | `NOT NULL char_count` | deferrable=False, initially deferred=False, validated=True |
| `chunk_chunk_hash_not_null` / `n` | `NOT NULL chunk_hash` | deferrable=False, initially deferred=False, validated=True |
| `chunk_chunk_id_not_null` / `n` | `NOT NULL chunk_id` | deferrable=False, initially deferred=False, validated=True |
| `chunk_chunk_kind_not_null` / `n` | `NOT NULL chunk_kind` | deferrable=False, initially deferred=False, validated=True |
| `chunk_chunk_ordinal_not_null` / `n` | `NOT NULL chunk_ordinal` | deferrable=False, initially deferred=False, validated=True |
| `chunk_chunk_text_not_null` / `n` | `NOT NULL chunk_text` | deferrable=False, initially deferred=False, validated=True |
| `chunk_concept_id_fkey` / `f` | `FOREIGN KEY (concept_id) REFERENCES knowledge.concept(concept_id)` | deferrable=False, initially deferred=False, validated=True |
| `chunk_concept_node_id_fkey` / `f` | `FOREIGN KEY (concept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `chunk_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `chunk_learning_item_id_fkey` / `f` | `FOREIGN KEY (learning_item_id) REFERENCES pedagogy.learning_item(learning_item_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `chunk_metadata_not_null` / `n` | `NOT NULL metadata` | deferrable=False, initially deferred=False, validated=True |
| `chunk_parent_chunk_id_fkey` / `f` | `FOREIGN KEY (parent_chunk_id) REFERENCES search.chunk(chunk_id)` | deferrable=False, initially deferred=False, validated=True |
| `chunk_pkey` / `p` | `PRIMARY KEY (chunk_id)` | deferrable=False, initially deferred=False, validated=True |
| `chunk_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `chunk_representation_id_chunk_ordinal_key` / `u` | `UNIQUE (representation_id, chunk_ordinal)` | deferrable=False, initially deferred=False, validated=True |
| `chunk_representation_id_fkey` / `f` | `FOREIGN KEY (representation_id) REFERENCES search.representation(representation_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `chunk_representation_id_not_null` / `n` | `NOT NULL representation_id` | deferrable=False, initially deferred=False, validated=True |
| `chunk_single_pedagogy_owner` / `c` | `CHECK (solution_step_id IS NULL OR learning_item_id IS NULL)` | deferrable=False, initially deferred=False, validated=True |
| `chunk_skill_node_id_fkey` / `f` | `FOREIGN KEY (skill_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `chunk_solution_id_fkey` / `f` | `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id)` | deferrable=False, initially deferred=False, validated=True |
| `chunk_solution_step_id_fkey` / `f` | `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `chunk_subconcept_node_id_fkey` / `f` | `FOREIGN KEY (subconcept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `chunk_technique_id_fkey` / `f` | `FOREIGN KEY (technique_id) REFERENCES knowledge.technique(technique_id)` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `search.chunk` / `chunk_parent_chunk_id_fkey`: `FOREIGN KEY (parent_chunk_id) REFERENCES search.chunk(chunk_id)`.
- `search.embedding` / `embedding_chunk_id_fkey`: `FOREIGN KEY (chunk_id) REFERENCES search.chunk(chunk_id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `chunk_pkey`: `CREATE UNIQUE INDEX chunk_pkey ON search.chunk USING btree (chunk_id)`; valid=True, ready=True.
- `chunk_representation_id_chunk_ordinal_key`: `CREATE UNIQUE INDEX chunk_representation_id_chunk_ordinal_key ON search.chunk USING btree (representation_id, chunk_ordinal)`; valid=True, ready=True.
- `idx_search_chunk_fts`: `CREATE INDEX idx_search_chunk_fts ON search.chunk USING gin (textsearch)`; valid=True, ready=True.
- `idx_search_chunk_learning_item`: `CREATE INDEX idx_search_chunk_learning_item ON search.chunk USING btree (learning_item_id) WHERE (learning_item_id IS NOT NULL)`; valid=True, ready=True.
- `idx_search_chunk_metadata`: `CREATE INDEX idx_search_chunk_metadata ON search.chunk USING gin (metadata jsonb_path_ops)`; valid=True, ready=True.
- `idx_search_chunk_problem`: `CREATE INDEX idx_search_chunk_problem ON search.chunk USING btree (problem_id)`; valid=True, ready=True.
- `idx_search_chunk_skill_node`: `CREATE INDEX idx_search_chunk_skill_node ON search.chunk USING btree (skill_node_id) WHERE (skill_node_id IS NOT NULL)`; valid=True, ready=True.
- `idx_search_chunk_solution`: `CREATE INDEX idx_search_chunk_solution ON search.chunk USING btree (solution_id)`; valid=True, ready=True.
- `idx_search_chunk_solution_step`: `CREATE INDEX idx_search_chunk_solution_step ON search.chunk USING btree (solution_step_id) WHERE (solution_step_id IS NOT NULL)`; valid=True, ready=True.
- `idx_search_chunk_subconcept_node`: `CREATE INDEX idx_search_chunk_subconcept_node ON search.chunk USING btree (subconcept_node_id) WHERE (subconcept_node_id IS NOT NULL)`; valid=True, ready=True.
- `idx_search_chunk_trgm`: `CREATE INDEX idx_search_chunk_trgm ON search.chunk USING gin (chunk_text gin_trgm_ops)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `search.embedding`

**Kind / use case:** table. Model/dimension-coupled stored vectors for representations/chunks.

**Migration owner:** [002_vector_schema.sql](../../../mathbank-db/sql/002_vector_schema.sql#L79); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L121); [mathbank-rest/src/mathbank_rest/db/vector_search.py](../../../mathbank-rest/src/mathbank_rest/db/vector_search.py#L1); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L88); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L168); [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L196); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L76); [mathbank-db/etl/embed_corpus.py](../../../mathbank-db/etl/embed_corpus.py#L4); [mathbank-db/etl/embed_textbook_steps.py](../../../mathbank-db/etl/embed_textbook_steps.py#L4); [mathbank-db/etl/repair_question_text.py](../../../mathbank-db/etl/repair_question_text.py#L181); [mathbank-agent/agents/mathbank_tutor/agent.py](../../../mathbank-agent/agents/mathbank_tutor/agent.py#L4).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `embedding_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `chunk_id` | `uuid` | no | `-` | `- / -` |
| `embedding_model_id` | `uuid` | no | `-` | `- / -` |
| `embedding` | `vector` | no | `-` | `- / -` |
| `embedding_hash` | `text` | yes | `-` | `- / -` |
| `generated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `status` | `text` | no | `'ACTIVE'::text` | `- / -` |
| `metadata` | `jsonb` | no | `'{}'::jsonb` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `embedding_chunk_id_embedding_model_id_key` / `u` | `UNIQUE (chunk_id, embedding_model_id)` | deferrable=False, initially deferred=False, validated=True |
| `embedding_chunk_id_fkey` / `f` | `FOREIGN KEY (chunk_id) REFERENCES search.chunk(chunk_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `embedding_chunk_id_not_null` / `n` | `NOT NULL chunk_id` | deferrable=False, initially deferred=False, validated=True |
| `embedding_embedding_id_not_null` / `n` | `NOT NULL embedding_id` | deferrable=False, initially deferred=False, validated=True |
| `embedding_embedding_model_id_fkey` / `f` | `FOREIGN KEY (embedding_model_id) REFERENCES search.embedding_model(embedding_model_id)` | deferrable=False, initially deferred=False, validated=True |
| `embedding_embedding_model_id_not_null` / `n` | `NOT NULL embedding_model_id` | deferrable=False, initially deferred=False, validated=True |
| `embedding_embedding_not_null` / `n` | `NOT NULL embedding` | deferrable=False, initially deferred=False, validated=True |
| `embedding_generated_at_not_null` / `n` | `NOT NULL generated_at` | deferrable=False, initially deferred=False, validated=True |
| `embedding_metadata_not_null` / `n` | `NOT NULL metadata` | deferrable=False, initially deferred=False, validated=True |
| `embedding_pkey` / `p` | `PRIMARY KEY (embedding_id)` | deferrable=False, initially deferred=False, validated=True |
| `embedding_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `embedding_chunk_id_embedding_model_id_key`: `CREATE UNIQUE INDEX embedding_chunk_id_embedding_model_id_key ON search.embedding USING btree (chunk_id, embedding_model_id)`; valid=True, ready=True.
- `embedding_pkey`: `CREATE UNIQUE INDEX embedding_pkey ON search.embedding USING btree (embedding_id)`; valid=True, ready=True.
- `idx_embedding_model_status`: `CREATE INDEX idx_embedding_model_status ON search.embedding USING btree (embedding_model_id, status)`; valid=True, ready=True.
- `idx_search_embedding_text_embedding_3_small_hnsw`: `CREATE INDEX idx_search_embedding_text_embedding_3_small_hnsw ON search.embedding USING hnsw (((embedding)::vector(1536)) vector_cosine_ops) WHERE ((embedding_model_id = '6184909e-e887-426b-9f49-13f228346633'::uuid) AND (status = 'ACTIVE'::text))`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `search.embedding_job`

**Kind / use case:** table. Resumable embedding work, attempts/errors/status.

**Migration owner:** [002_vector_schema.sql](../../../mathbank-db/sql/002_vector_schema.sql#L93); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L171); [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L198); [mathbank-db/etl/embed_corpus.py](../../../mathbank-db/etl/embed_corpus.py#L4).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `embedding_job_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `run_id` | `uuid` | yes | `-` | `- / -` |
| `representation_id` | `uuid` | yes | `-` | `- / -` |
| `embedding_model_id` | `uuid` | yes | `-` | `- / -` |
| `status` | `text` | no | `'PENDING'::text` | `- / -` |
| `attempt_count` | `integer` | no | `0` | `- / -` |
| `input_hash` | `text` | no | `-` | `- / -` |
| `started_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `heartbeat_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `completed_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `worker_id` | `text` | yes | `-` | `- / -` |
| `last_error` | `text` | yes | `-` | `- / -` |
| `metrics` | `jsonb` | no | `'{}'::jsonb` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `embedding_job_attempt_count_not_null` / `n` | `NOT NULL attempt_count` | deferrable=False, initially deferred=False, validated=True |
| `embedding_job_embedding_job_id_not_null` / `n` | `NOT NULL embedding_job_id` | deferrable=False, initially deferred=False, validated=True |
| `embedding_job_embedding_model_id_fkey` / `f` | `FOREIGN KEY (embedding_model_id) REFERENCES search.embedding_model(embedding_model_id)` | deferrable=False, initially deferred=False, validated=True |
| `embedding_job_input_hash_not_null` / `n` | `NOT NULL input_hash` | deferrable=False, initially deferred=False, validated=True |
| `embedding_job_metrics_not_null` / `n` | `NOT NULL metrics` | deferrable=False, initially deferred=False, validated=True |
| `embedding_job_pkey` / `p` | `PRIMARY KEY (embedding_job_id)` | deferrable=False, initially deferred=False, validated=True |
| `embedding_job_representation_id_embedding_model_id_input_ha_key` / `u` | `UNIQUE (representation_id, embedding_model_id, input_hash)` | deferrable=False, initially deferred=False, validated=True |
| `embedding_job_representation_id_fkey` / `f` | `FOREIGN KEY (representation_id) REFERENCES search.representation(representation_id)` | deferrable=False, initially deferred=False, validated=True |
| `embedding_job_run_id_fkey` / `f` | `FOREIGN KEY (run_id) REFERENCES pipeline.run(run_id)` | deferrable=False, initially deferred=False, validated=True |
| `embedding_job_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `embedding_job_pkey`: `CREATE UNIQUE INDEX embedding_job_pkey ON search.embedding_job USING btree (embedding_job_id)`; valid=True, ready=True.
- `embedding_job_representation_id_embedding_model_id_input_ha_key`: `CREATE UNIQUE INDEX embedding_job_representation_id_embedding_model_id_input_ha_key ON search.embedding_job USING btree (representation_id, embedding_model_id, input_hash)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `search.embedding_model`

**Kind / use case:** table. Registered embedding provider/model dimensions and metadata.

**Migration owner:** [002_vector_schema.sql](../../../mathbank-db/sql/002_vector_schema.sql#L10); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/vector_search.py](../../../mathbank-rest/src/mathbank_rest/db/vector_search.py#L28); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L169); [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L196); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L76); [mathbank-db/etl/embed_corpus.py](../../../mathbank-db/etl/embed_corpus.py#L71); [mathbank-db/etl/repair_question_text.py](../../../mathbank-db/etl/repair_question_text.py#L182).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `embedding_model_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `provider` | `text` | no | `-` | `- / -` |
| `model_name` | `text` | no | `-` | `- / -` |
| `model_revision` | `text` | no | `-` | `- / -` |
| `dimensions` | `integer` | no | `-` | `- / -` |
| `distance_metric` | `text` | no | `'COSINE'::text` | `- / -` |
| `normalization` | `text` | yes | `-` | `- / -` |
| `status` | `text` | no | `'REGISTERED'::text` | `- / -` |
| `activated_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `retired_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `metadata` | `jsonb` | no | `'{}'::jsonb` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `embedding_model_dimensions_check` / `c` | `CHECK (dimensions > 0)` | deferrable=False, initially deferred=False, validated=True |
| `embedding_model_dimensions_not_null` / `n` | `NOT NULL dimensions` | deferrable=False, initially deferred=False, validated=True |
| `embedding_model_distance_metric_not_null` / `n` | `NOT NULL distance_metric` | deferrable=False, initially deferred=False, validated=True |
| `embedding_model_embedding_model_id_not_null` / `n` | `NOT NULL embedding_model_id` | deferrable=False, initially deferred=False, validated=True |
| `embedding_model_metadata_not_null` / `n` | `NOT NULL metadata` | deferrable=False, initially deferred=False, validated=True |
| `embedding_model_model_name_not_null` / `n` | `NOT NULL model_name` | deferrable=False, initially deferred=False, validated=True |
| `embedding_model_model_revision_not_null` / `n` | `NOT NULL model_revision` | deferrable=False, initially deferred=False, validated=True |
| `embedding_model_pkey` / `p` | `PRIMARY KEY (embedding_model_id)` | deferrable=False, initially deferred=False, validated=True |
| `embedding_model_provider_model_name_model_revision_key` / `u` | `UNIQUE (provider, model_name, model_revision)` | deferrable=False, initially deferred=False, validated=True |
| `embedding_model_provider_not_null` / `n` | `NOT NULL provider` | deferrable=False, initially deferred=False, validated=True |
| `embedding_model_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `search.embedding` / `embedding_embedding_model_id_fkey`: `FOREIGN KEY (embedding_model_id) REFERENCES search.embedding_model(embedding_model_id)`.
- `search.embedding_job` / `embedding_job_embedding_model_id_fkey`: `FOREIGN KEY (embedding_model_id) REFERENCES search.embedding_model(embedding_model_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `embedding_model_pkey`: `CREATE UNIQUE INDEX embedding_model_pkey ON search.embedding_model USING btree (embedding_model_id)`; valid=True, ready=True.
- `embedding_model_provider_model_name_model_revision_key`: `CREATE UNIQUE INDEX embedding_model_provider_model_name_model_revision_key ON search.embedding_model USING btree (provider, model_name, model_revision)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `search.preprocessing_profile`

**Kind / use case:** table. Versioned input normalization/chunking profile.

**Migration owner:** [002_vector_schema.sql](../../../mathbank-db/sql/002_vector_schema.sql#L25); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L110); [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L211); [mathbank-db/etl/embed_corpus.py](../../../mathbank-db/etl/embed_corpus.py#L83); [mathbank-db/etl/embed_textbook_steps.py](../../../mathbank-db/etl/embed_textbook_steps.py#L294).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `preprocessing_profile_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `name` | `text` | no | `-` | `- / -` |
| `version` | `integer` | no | `-` | `- / -` |
| `configuration` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `code_revision` | `text` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `preprocessing_profile_configuration_not_null` / `n` | `NOT NULL configuration` | deferrable=False, initially deferred=False, validated=True |
| `preprocessing_profile_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `preprocessing_profile_name_not_null` / `n` | `NOT NULL name` | deferrable=False, initially deferred=False, validated=True |
| `preprocessing_profile_name_version_key` / `u` | `UNIQUE (name, version)` | deferrable=False, initially deferred=False, validated=True |
| `preprocessing_profile_pkey` / `p` | `PRIMARY KEY (preprocessing_profile_id)` | deferrable=False, initially deferred=False, validated=True |
| `preprocessing_profile_preprocessing_profile_id_not_null` / `n` | `NOT NULL preprocessing_profile_id` | deferrable=False, initially deferred=False, validated=True |
| `preprocessing_profile_version_not_null` / `n` | `NOT NULL version` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `search.representation` / `representation_preprocessing_profile_id_fkey`: `FOREIGN KEY (preprocessing_profile_id) REFERENCES search.preprocessing_profile(preprocessing_profile_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `preprocessing_profile_name_version_key`: `CREATE UNIQUE INDEX preprocessing_profile_name_version_key ON search.preprocessing_profile USING btree (name, version)`; valid=True, ready=True.
- `preprocessing_profile_pkey`: `CREATE UNIQUE INDEX preprocessing_profile_pkey ON search.preprocessing_profile USING btree (preprocessing_profile_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `search.representation`

**Kind / use case:** table. Source-entity representation/version/hash and freshness status.

**Migration owner:** [002_vector_schema.sql](../../../mathbank-db/sql/002_vector_schema.sql#L35); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/corpus_authoring.py](../../../mathbank-rest/src/mathbank_rest/corpus_authoring.py#L250); [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L109); [mathbank-rest/src/mathbank_rest/db/vector_search.py](../../../mathbank-rest/src/mathbank_rest/db/vector_search.py#L112); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L90); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L164); [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L211); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L72); [mathbank-db/etl/embed_corpus.py](../../../mathbank-db/etl/embed_corpus.py#L3); [mathbank-db/etl/embed_textbook_steps.py](../../../mathbank-db/etl/embed_textbook_steps.py#L4); [mathbank-db/etl/repair_question_text.py](../../../mathbank-db/etl/repair_question_text.py#L180).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `representation_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `source_entity_type` | `text` | no | `-` | `- / -` |
| `source_entity_id` | `uuid` | no | `-` | `- / -` |
| `representation_kind` | `text` | no | `-` | `- / -` |
| `preprocessing_profile_id` | `uuid` | no | `-` | `- / -` |
| `rendered_text` | `text` | no | `-` | `- / -` |
| `content_hash` | `text` | no | `-` | `- / -` |
| `source_updated_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `generated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `status` | `text` | no | `'ACTIVE'::text` | `- / -` |
| `metadata` | `jsonb` | no | `'{}'::jsonb` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `representation_content_hash_not_null` / `n` | `NOT NULL content_hash` | deferrable=False, initially deferred=False, validated=True |
| `representation_generated_at_not_null` / `n` | `NOT NULL generated_at` | deferrable=False, initially deferred=False, validated=True |
| `representation_metadata_not_null` / `n` | `NOT NULL metadata` | deferrable=False, initially deferred=False, validated=True |
| `representation_pkey` / `p` | `PRIMARY KEY (representation_id)` | deferrable=False, initially deferred=False, validated=True |
| `representation_preprocessing_profile_id_fkey` / `f` | `FOREIGN KEY (preprocessing_profile_id) REFERENCES search.preprocessing_profile(preprocessing_profile_id)` | deferrable=False, initially deferred=False, validated=True |
| `representation_preprocessing_profile_id_not_null` / `n` | `NOT NULL preprocessing_profile_id` | deferrable=False, initially deferred=False, validated=True |
| `representation_rendered_text_not_null` / `n` | `NOT NULL rendered_text` | deferrable=False, initially deferred=False, validated=True |
| `representation_representation_id_not_null` / `n` | `NOT NULL representation_id` | deferrable=False, initially deferred=False, validated=True |
| `representation_representation_kind_not_null` / `n` | `NOT NULL representation_kind` | deferrable=False, initially deferred=False, validated=True |
| `representation_source_entity_id_not_null` / `n` | `NOT NULL source_entity_id` | deferrable=False, initially deferred=False, validated=True |
| `representation_source_entity_type_not_null` / `n` | `NOT NULL source_entity_type` | deferrable=False, initially deferred=False, validated=True |
| `representation_source_entity_type_source_entity_id_represen_key` / `u` | `UNIQUE (source_entity_type, source_entity_id, representation_kind, preprocessing_profile_id, content_hash)` | deferrable=False, initially deferred=False, validated=True |
| `representation_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `search.chunk` / `chunk_representation_id_fkey`: `FOREIGN KEY (representation_id) REFERENCES search.representation(representation_id) ON DELETE CASCADE`.
- `search.embedding_job` / `embedding_job_representation_id_fkey`: `FOREIGN KEY (representation_id) REFERENCES search.representation(representation_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `idx_representation_source`: `CREATE INDEX idx_representation_source ON search.representation USING btree (source_entity_type, source_entity_id, status)`; valid=True, ready=True.
- `representation_pkey`: `CREATE UNIQUE INDEX representation_pkey ON search.representation USING btree (representation_id)`; valid=True, ready=True.
- `representation_source_entity_type_source_entity_id_represen_key`: `CREATE UNIQUE INDEX representation_source_entity_type_source_entity_id_represen_key ON search.representation USING btree (source_entity_type, source_entity_id, representation_kind, preprocessing_profile_id, content_hash)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `search.retrieval_profile`

**Kind / use case:** table. Configured retrieval model, weights and candidate settings.

**Migration owner:** [002_vector_schema.sql](../../../mathbank-db/sql/002_vector_schema.sql#L110); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `retrieval_profile_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `name` | `text` | no | `-` | `- / -` |
| `version` | `integer` | no | `-` | `- / -` |
| `configuration` | `jsonb` | no | `-` | `- / -` |
| `status` | `text` | no | `'ACTIVE'::text` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `retrieval_profile_configuration_not_null` / `n` | `NOT NULL configuration` | deferrable=False, initially deferred=False, validated=True |
| `retrieval_profile_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `retrieval_profile_name_not_null` / `n` | `NOT NULL name` | deferrable=False, initially deferred=False, validated=True |
| `retrieval_profile_name_version_key` / `u` | `UNIQUE (name, version)` | deferrable=False, initially deferred=False, validated=True |
| `retrieval_profile_pkey` / `p` | `PRIMARY KEY (retrieval_profile_id)` | deferrable=False, initially deferred=False, validated=True |
| `retrieval_profile_retrieval_profile_id_not_null` / `n` | `NOT NULL retrieval_profile_id` | deferrable=False, initially deferred=False, validated=True |
| `retrieval_profile_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `retrieval_profile_version_not_null` / `n` | `NOT NULL version` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `retrieval_profile_name_version_key`: `CREATE UNIQUE INDEX retrieval_profile_name_version_key ON search.retrieval_profile USING btree (name, version)`; valid=True, ready=True.
- `retrieval_profile_pkey`: `CREATE UNIQUE INDEX retrieval_profile_pkey ON search.retrieval_profile USING btree (retrieval_profile_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

