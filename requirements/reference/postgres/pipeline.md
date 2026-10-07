# PostgreSQL `pipeline` schema

**Role:** Operational work and publications. Import/embedding/graph jobs, source registry, transactional outbox and projection requests.

**Access family:** `/v1/admin/pipeline/*`, `/v1/admin/papers`, `/v1/admin/imports/projection-requests`; CLI workers/projectors.

**Evidence:** live catalog metadata at 2026-10-07T13:40:57.292324+00:00; source `375f3743357cef814c50e3c8752f7f4ce2d6ebe5`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `pipeline.graph_projection`

**Kind / use case:** table. Publication-run ledger, target graph and completion/error metadata.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L185); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/routers/admin.py](../../../mathbank-rest/src/mathbank_rest/routers/admin.py#L10); [mathbank-rest/src/mathbank_rest/db/admin.py](../../../mathbank-rest/src/mathbank_rest/db/admin.py#L8); [mathbank-graph/etl/project_from_postgres.py](../../../mathbank-graph/etl/project_from_postgres.py#L5); [mathbank-graph/etl/project_textbook_steps.py](../../../mathbank-graph/etl/project_textbook_steps.py#L311).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `projection_run_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `graph_name` | `text` | no | `-` | `- / -` |
| `source_watermark` | `timestamp with time zone` | no | `now()` | `- / -` |
| `started_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `completed_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `nodes_upserted` | `integer` | no | `0` | `- / -` |
| `edges_upserted` | `integer` | no | `0` | `- / -` |
| `status` | `text` | no | `'IN_PROGRESS'::text` | `- / -` |
| `error` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `graph_projection_edges_upserted_not_null` / `n` | `NOT NULL edges_upserted` | deferrable=False, initially deferred=False, validated=True |
| `graph_projection_graph_name_not_null` / `n` | `NOT NULL graph_name` | deferrable=False, initially deferred=False, validated=True |
| `graph_projection_nodes_upserted_not_null` / `n` | `NOT NULL nodes_upserted` | deferrable=False, initially deferred=False, validated=True |
| `graph_projection_pkey` / `p` | `PRIMARY KEY (projection_run_id)` | deferrable=False, initially deferred=False, validated=True |
| `graph_projection_projection_run_id_not_null` / `n` | `NOT NULL projection_run_id` | deferrable=False, initially deferred=False, validated=True |
| `graph_projection_source_watermark_not_null` / `n` | `NOT NULL source_watermark` | deferrable=False, initially deferred=False, validated=True |
| `graph_projection_started_at_not_null` / `n` | `NOT NULL started_at` | deferrable=False, initially deferred=False, validated=True |
| `graph_projection_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `graph_projection_pkey`: `CREATE UNIQUE INDEX graph_projection_pkey ON pipeline.graph_projection USING btree (projection_run_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pipeline.outbox_consumption`

**Kind / use case:** table. Per-consumer receipts for idempotent event handling.

**Migration owner:** [012_step_runtime.sql](../../../mathbank-db/sql/012_step_runtime.sql#L132); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/outbox_worker.py](../../../mathbank-rest/src/mathbank_rest/outbox_worker.py#L3).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `outbox_event_id` | `uuid` | no | `-` | `- / -` |
| `consumer_name` | `text` | no | `-` | `- / -` |
| `processed_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `outbox_consumption_consumer_name_not_null` / `n` | `NOT NULL consumer_name` | deferrable=False, initially deferred=False, validated=True |
| `outbox_consumption_outbox_event_id_fkey` / `f` | `FOREIGN KEY (outbox_event_id) REFERENCES pipeline.outbox_event(outbox_event_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `outbox_consumption_outbox_event_id_not_null` / `n` | `NOT NULL outbox_event_id` | deferrable=False, initially deferred=False, validated=True |
| `outbox_consumption_pkey` / `p` | `PRIMARY KEY (outbox_event_id, consumer_name)` | deferrable=False, initially deferred=False, validated=True |
| `outbox_consumption_processed_at_not_null` / `n` | `NOT NULL processed_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `outbox_consumption_pkey`: `CREATE UNIQUE INDEX outbox_consumption_pkey ON pipeline.outbox_consumption USING btree (outbox_event_id, consumer_name)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pipeline.outbox_event`

**Kind / use case:** table. Transactional event payloads queued alongside canonical changes.

**Migration owner:** [012_step_runtime.sql](../../../mathbank-db/sql/012_step_runtime.sql#L122); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/attempt_media.py#L64); [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L4); [mathbank-rest/src/mathbank_rest/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/step_runtime.py#L162); [mathbank-rest/src/mathbank_rest/outbox_worker.py](../../../mathbank-rest/src/mathbank_rest/outbox_worker.py#L106); [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L4); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L731).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `outbox_event_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `event_type` | `text` | no | `-` | `- / -` |
| `aggregate_type` | `text` | no | `-` | `- / -` |
| `aggregate_id` | `text` | no | `-` | `- / -` |
| `payload` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `clock_timestamp()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `outbox_event_aggregate_id_not_null` / `n` | `NOT NULL aggregate_id` | deferrable=False, initially deferred=False, validated=True |
| `outbox_event_aggregate_type_not_null` / `n` | `NOT NULL aggregate_type` | deferrable=False, initially deferred=False, validated=True |
| `outbox_event_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `outbox_event_event_type_not_null` / `n` | `NOT NULL event_type` | deferrable=False, initially deferred=False, validated=True |
| `outbox_event_outbox_event_id_not_null` / `n` | `NOT NULL outbox_event_id` | deferrable=False, initially deferred=False, validated=True |
| `outbox_event_payload_not_null` / `n` | `NOT NULL payload` | deferrable=False, initially deferred=False, validated=True |
| `outbox_event_pkey` / `p` | `PRIMARY KEY (outbox_event_id)` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `pipeline.outbox_consumption` / `outbox_consumption_outbox_event_id_fkey`: `FOREIGN KEY (outbox_event_id) REFERENCES pipeline.outbox_event(outbox_event_id) ON DELETE CASCADE`.
- `pipeline.projection_request` / `projection_request_source_outbox_event_id_fkey`: `FOREIGN KEY (source_outbox_event_id) REFERENCES pipeline.outbox_event(outbox_event_id) ON DELETE SET NULL`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `outbox_event_created_idx`: `CREATE INDEX outbox_event_created_idx ON pipeline.outbox_event USING btree (created_at)`; valid=True, ready=True.
- `outbox_event_pkey`: `CREATE UNIQUE INDEX outbox_event_pkey ON pipeline.outbox_event USING btree (outbox_event_id)`; valid=True, ready=True.
- `outbox_event_type_idx`: `CREATE INDEX outbox_event_type_idx ON pipeline.outbox_event USING btree (event_type, created_at)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pipeline.pdf_source`

**Kind / use case:** table. Registered competition-paper HTML/PDF source stage/retry tracker.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L199); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/routers/admin.py](../../../mathbank-rest/src/mathbank_rest/routers/admin.py#L9); [mathbank-rest/src/mathbank_rest/db/problem_sources.py](../../../mathbank-rest/src/mathbank_rest/db/problem_sources.py#L27); [mathbank-rest/src/mathbank_rest/db/admin.py](../../../mathbank-rest/src/mathbank_rest/db/admin.py#L4); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L25); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L43); [mathbank-db/etl/pdf_pipeline.py](../../../mathbank-db/etl/pdf_pipeline.py#L3); [mathbank-db/etl/purple_comet.py](../../../mathbank-db/etl/purple_comet.py#L260); [mathbank-db/etl/paper_batches.py](../../../mathbank-db/etl/paper_batches.py#L190).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `pdf_source_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `paper_external_code` | `text` | no | `-` | `- / -` |
| `competition_external_code` | `text` | no | `-` | `- / -` |
| `crawl_dir` | `text` | no | `-` | `- / -` |
| `problem_url` | `text` | yes | `-` | `- / -` |
| `solution_url` | `text` | yes | `-` | `- / -` |
| `link_scope` | `text` | yes | `-` | `- / -` |
| `download_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `downloaded_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `parse_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `parsed_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `questions_found` | `integer` | no | `0` | `- / -` |
| `ingest_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `ingested_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `questions_ingested` | `integer` | no | `0` | `- / -` |
| `solutions_ingested` | `integer` | no | `0` | `- / -` |
| `last_error` | `text` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `source_kind` | `text` | no | `'PDF'::text` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `pdf_source_competition_external_code_not_null` / `n` | `NOT NULL competition_external_code` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_crawl_dir_not_null` / `n` | `NOT NULL crawl_dir` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_download_status_not_null` / `n` | `NOT NULL download_status` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_ingest_status_not_null` / `n` | `NOT NULL ingest_status` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_paper_external_code_key` / `u` | `UNIQUE (paper_external_code)` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_paper_external_code_not_null` / `n` | `NOT NULL paper_external_code` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_parse_status_not_null` / `n` | `NOT NULL parse_status` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_pdf_source_id_not_null` / `n` | `NOT NULL pdf_source_id` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_pkey` / `p` | `PRIMARY KEY (pdf_source_id)` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_questions_found_not_null` / `n` | `NOT NULL questions_found` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_questions_ingested_not_null` / `n` | `NOT NULL questions_ingested` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_solutions_ingested_not_null` / `n` | `NOT NULL solutions_ingested` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_source_kind_not_null` / `n` | `NOT NULL source_kind` | deferrable=False, initially deferred=False, validated=True |
| `pdf_source_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `idx_pdf_source_kind`: `CREATE INDEX idx_pdf_source_kind ON pipeline.pdf_source USING btree (source_kind, download_status)`; valid=True, ready=True.
- `idx_pdf_source_status`: `CREATE INDEX idx_pdf_source_status ON pipeline.pdf_source USING btree (download_status, parse_status, ingest_status)`; valid=True, ready=True.
- `pdf_source_paper_external_code_key`: `CREATE UNIQUE INDEX pdf_source_paper_external_code_key ON pipeline.pdf_source USING btree (paper_external_code)`; valid=True, ready=True.
- `pdf_source_pkey`: `CREATE UNIQUE INDEX pdf_source_pkey ON pipeline.pdf_source USING btree (pdf_source_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pipeline.projection_request`

**Kind / use case:** table. Explicit/coalesced graph or embedding work request; not execution.

**Migration owner:** [018_outbox_consumers.sql](../../../mathbank-db/sql/018_outbox_consumers.sql#L47); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/outbox_worker.py](../../../mathbank-rest/src/mathbank_rest/outbox_worker.py#L5); [mathbank-rest/src/mathbank_rest/routers/admin_imports.py](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L5); [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L86); [mathbank-db/etl/run_projection_requests.py](../../../mathbank-db/etl/run_projection_requests.py#L2).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `projection_request_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `target` | `text` | no | `-` | `- / -` |
| `scope_type` | `text` | no | `-` | `- / -` |
| `scope_id` | `text` | no | `-` | `- / -` |
| `reason` | `text` | no | `-` | `- / -` |
| `source_outbox_event_id` | `uuid` | yes | `-` | `- / -` |
| `status` | `text` | no | `'PENDING'::text` | `- / -` |
| `requested_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `completed_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `completed_by` | `text` | yes | `-` | `- / -` |
| `requested_by` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `projection_request_pkey` / `p` | `PRIMARY KEY (projection_request_id)` | deferrable=False, initially deferred=False, validated=True |
| `projection_request_projection_request_id_not_null` / `n` | `NOT NULL projection_request_id` | deferrable=False, initially deferred=False, validated=True |
| `projection_request_reason_not_null` / `n` | `NOT NULL reason` | deferrable=False, initially deferred=False, validated=True |
| `projection_request_requested_at_not_null` / `n` | `NOT NULL requested_at` | deferrable=False, initially deferred=False, validated=True |
| `projection_request_scope_id_not_null` / `n` | `NOT NULL scope_id` | deferrable=False, initially deferred=False, validated=True |
| `projection_request_scope_type_check` / `c` | `CHECK (scope_type = ANY (ARRAY['BOOK'::text, 'PACKAGE'::text, 'PROBLEM'::text, 'STEP'::text, 'LEARNING_ITEM'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `projection_request_scope_type_not_null` / `n` | `NOT NULL scope_type` | deferrable=False, initially deferred=False, validated=True |
| `projection_request_source_outbox_event_id_fkey` / `f` | `FOREIGN KEY (source_outbox_event_id) REFERENCES pipeline.outbox_event(outbox_event_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `projection_request_status_check` / `c` | `CHECK (status = ANY (ARRAY['PENDING'::text, 'DONE'::text, 'CANCELLED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `projection_request_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `projection_request_target_check` / `c` | `CHECK (target = ANY (ARRAY['GRAPH_TEXTBOOK_STEPS'::text, 'STEP_EMBEDDINGS'::text, 'LEARNING_ITEM_EMBEDDINGS'::text, 'GRAPH_LEARNING_ITEMS'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `projection_request_target_not_null` / `n` | `NOT NULL target` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `projection_request_open_uq`: `CREATE UNIQUE INDEX projection_request_open_uq ON pipeline.projection_request USING btree (target, scope_type, scope_id) WHERE (status = 'PENDING'::text)`; valid=True, ready=True.
- `projection_request_pkey`: `CREATE UNIQUE INDEX projection_request_pkey ON pipeline.projection_request USING btree (projection_request_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pipeline.run`

**Kind / use case:** table. Operational ETL/pipeline run status and timestamps.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L151); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/routers/admin.py](../../../mathbank-rest/src/mathbank_rest/routers/admin.py#L9); [mathbank-rest/src/mathbank_rest/db/admin.py](../../../mathbank-rest/src/mathbank_rest/db/admin.py#L8); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L92); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L34); [mathbank-db/etl/embed_corpus.py](../../../mathbank-db/etl/embed_corpus.py#L4); [mathbank-db/etl/pdf_pipeline.py](../../../mathbank-db/etl/pdf_pipeline.py#L23); [mathbank-db/etl/load_corpus.py](../../../mathbank-db/etl/load_corpus.py#L612); [mathbank-db/etl/paper_batches.py](../../../mathbank-db/etl/paper_batches.py#L138).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `run_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `run_type` | `text` | no | `-` | `- / -` |
| `requested_scope` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `status` | `text` | no | `-` | `- / -` |
| `started_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `completed_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `heartbeat_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `worker_id` | `text` | yes | `-` | `- / -` |
| `expected_items` | `integer` | yes | `-` | `- / -` |
| `completed_items` | `integer` | no | `0` | `- / -` |
| `failed_items` | `integer` | no | `0` | `- / -` |
| `metadata` | `jsonb` | no | `'{}'::jsonb` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `run_completed_items_not_null` / `n` | `NOT NULL completed_items` | deferrable=False, initially deferred=False, validated=True |
| `run_failed_items_not_null` / `n` | `NOT NULL failed_items` | deferrable=False, initially deferred=False, validated=True |
| `run_metadata_not_null` / `n` | `NOT NULL metadata` | deferrable=False, initially deferred=False, validated=True |
| `run_pkey` / `p` | `PRIMARY KEY (run_id)` | deferrable=False, initially deferred=False, validated=True |
| `run_requested_scope_not_null` / `n` | `NOT NULL requested_scope` | deferrable=False, initially deferred=False, validated=True |
| `run_run_id_not_null` / `n` | `NOT NULL run_id` | deferrable=False, initially deferred=False, validated=True |
| `run_run_type_not_null` / `n` | `NOT NULL run_type` | deferrable=False, initially deferred=False, validated=True |
| `run_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `pipeline.work_item` / `work_item_run_id_fkey`: `FOREIGN KEY (run_id) REFERENCES pipeline.run(run_id) ON DELETE CASCADE`.
- `search.embedding_job` / `embedding_job_run_id_fkey`: `FOREIGN KEY (run_id) REFERENCES pipeline.run(run_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `idx_run_status`: `CREATE INDEX idx_run_status ON pipeline.run USING btree (status, started_at DESC)`; valid=True, ready=True.
- `run_pkey`: `CREATE UNIQUE INDEX run_pkey ON pipeline.run USING btree (run_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pipeline.work_item`

**Kind / use case:** table. Scoped units of pipeline work and retry state.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L166); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/admin.py](../../../mathbank-rest/src/mathbank_rest/db/admin.py#L103); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L90); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L51); [mathbank-db/etl/pdf_pipeline.py](../../../mathbank-db/etl/pdf_pipeline.py#L23); [mathbank-db/etl/paper_batches.py](../../../mathbank-db/etl/paper_batches.py#L110).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `work_item_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `run_id` | `uuid` | no | `-` | `- / -` |
| `item_type` | `text` | no | `-` | `- / -` |
| `item_key` | `text` | no | `-` | `- / -` |
| `status` | `text` | no | `'PENDING'::text` | `- / -` |
| `attempt_count` | `integer` | no | `0` | `- / -` |
| `lease_owner` | `text` | yes | `-` | `- / -` |
| `lease_expires_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `started_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `completed_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `last_error` | `text` | yes | `-` | `- / -` |
| `input_hash` | `text` | yes | `-` | `- / -` |
| `output_hash` | `text` | yes | `-` | `- / -` |
| `metrics` | `jsonb` | no | `'{}'::jsonb` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `work_item_attempt_count_not_null` / `n` | `NOT NULL attempt_count` | deferrable=False, initially deferred=False, validated=True |
| `work_item_item_key_not_null` / `n` | `NOT NULL item_key` | deferrable=False, initially deferred=False, validated=True |
| `work_item_item_type_not_null` / `n` | `NOT NULL item_type` | deferrable=False, initially deferred=False, validated=True |
| `work_item_metrics_not_null` / `n` | `NOT NULL metrics` | deferrable=False, initially deferred=False, validated=True |
| `work_item_pkey` / `p` | `PRIMARY KEY (work_item_id)` | deferrable=False, initially deferred=False, validated=True |
| `work_item_run_id_fkey` / `f` | `FOREIGN KEY (run_id) REFERENCES pipeline.run(run_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `work_item_run_id_item_type_item_key_key` / `u` | `UNIQUE (run_id, item_type, item_key)` | deferrable=False, initially deferred=False, validated=True |
| `work_item_run_id_not_null` / `n` | `NOT NULL run_id` | deferrable=False, initially deferred=False, validated=True |
| `work_item_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `work_item_work_item_id_not_null` / `n` | `NOT NULL work_item_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `idx_work_claim`: `CREATE INDEX idx_work_claim ON pipeline.work_item USING btree (status, lease_expires_at)`; valid=True, ready=True.
- `work_item_pkey`: `CREATE UNIQUE INDEX work_item_pkey ON pipeline.work_item USING btree (work_item_id)`; valid=True, ready=True.
- `work_item_run_id_item_type_item_key_key`: `CREATE UNIQUE INDEX work_item_run_id_item_type_item_key_key ON pipeline.work_item USING btree (run_id, item_type, item_key)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

