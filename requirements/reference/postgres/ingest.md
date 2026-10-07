# PostgreSQL `ingest` schema

**Role:** Staging and human review. Package ledgers, conflicts, reconciliation, immutable review evidence and private corpus drafts.

**Access family:** `/v1/admin/imports/*`, `/v1/admin/corpus/*`; import CLI. Shared admin key, browser signed admin session.

**Evidence:** live catalog metadata at 2026-10-07T13:40:57.292324+00:00; source `375f3743357cef814c50e3c8752f7f4ce2d6ebe5`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `ingest.admin_review_action`

**Kind / use case:** table. Append-only before/after import/step/dependency review audit.

**Migration owner:** [019_admin_import_review.sql](../../../mathbank-db/sql/019_admin_import_review.sql#L7); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L3).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `action_id` | `bigint` | no | `nextval('ingest.admin_review_action_action_id_seq'::regclass)` | `- / -` |
| `target_type` | `text` | no | `-` | `- / -` |
| `target_id` | `text` | no | `-` | `- / -` |
| `action` | `text` | no | `-` | `- / -` |
| `before_state` | `jsonb` | yes | `-` | `- / -` |
| `after_state` | `jsonb` | yes | `-` | `- / -` |
| `note` | `text` | yes | `-` | `- / -` |
| `actor` | `text` | no | `'admin'::text` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `admin_review_action_action_id_not_null` / `n` | `NOT NULL action_id` | deferrable=False, initially deferred=False, validated=True |
| `admin_review_action_action_not_null` / `n` | `NOT NULL action` | deferrable=False, initially deferred=False, validated=True |
| `admin_review_action_actor_not_null` / `n` | `NOT NULL actor` | deferrable=False, initially deferred=False, validated=True |
| `admin_review_action_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `admin_review_action_pkey` / `p` | `PRIMARY KEY (action_id)` | deferrable=False, initially deferred=False, validated=True |
| `admin_review_action_target_id_not_null` / `n` | `NOT NULL target_id` | deferrable=False, initially deferred=False, validated=True |
| `admin_review_action_target_type_check` / `c` | `CHECK (target_type = ANY (ARRAY['IMPORT_CONFLICT'::text, 'SOLUTION_STEP'::text, 'STEP_DEPENDENCY'::text, 'SOLUTION_DAG'::text, 'LEARNING_ITEM'::text, 'PROJECTION_REQUEST'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `admin_review_action_target_type_not_null` / `n` | `NOT NULL target_type` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `admin_review_action_pkey`: `CREATE UNIQUE INDEX admin_review_action_pkey ON ingest.admin_review_action USING btree (action_id)`; valid=True, ready=True.
- `admin_review_action_target_idx`: `CREATE INDEX admin_review_action_target_idx ON ingest.admin_review_action USING btree (target_type, target_id, created_at DESC)`; valid=True, ready=True.

**Triggers:**

- `admin_review_action_append_only`: `CREATE TRIGGER admin_review_action_append_only BEFORE DELETE OR UPDATE ON ingest.admin_review_action FOR EACH ROW EXECUTE FUNCTION ingest.admin_review_action_append_only()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `ingest.admin_review_action_action_id_seq`

**Kind:** sequence; allocates identity values for associated serial columns.
No sequence current/last value was read. Column defaults and indexes identify its table use.

### `ingest.content_package`

**Kind / use case:** table. Registered content/version/book and import reconciliation ledger.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L24); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L68); [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L78); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L716); [mathbank-db/etl/embed_textbook_steps.py](../../../mathbank-db/etl/embed_textbook_steps.py#L198); [mathbank-graph/etl/project_textbook_steps.py](../../../mathbank-graph/etl/project_textbook_steps.py#L68).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `content_package_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `package_name` | `text` | no | `-` | `- / -` |
| `package_version` | `text` | no | `-` | `- / -` |
| `manifest_hash` | `text` | no | `-` | `- / -` |
| `book_code` | `text` | yes | `-` | `- / -` |
| `source_root` | `text` | yes | `-` | `- / -` |
| `status` | `text` | no | `'REGISTERED'::text` | `- / -` |
| `status_detail` | `text` | yes | `-` | `- / -` |
| `last_scope` | `text` | yes | `-` | `- / -` |
| `report` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `imported_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `content_package_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `content_package_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `content_package_manifest_hash_not_null` / `n` | `NOT NULL manifest_hash` | deferrable=False, initially deferred=False, validated=True |
| `content_package_package_name_not_null` / `n` | `NOT NULL package_name` | deferrable=False, initially deferred=False, validated=True |
| `content_package_package_name_package_version_manifest_hash_key` / `u` | `UNIQUE (package_name, package_version, manifest_hash)` | deferrable=False, initially deferred=False, validated=True |
| `content_package_package_version_not_null` / `n` | `NOT NULL package_version` | deferrable=False, initially deferred=False, validated=True |
| `content_package_pkey` / `p` | `PRIMARY KEY (content_package_id)` | deferrable=False, initially deferred=False, validated=True |
| `content_package_report_not_null` / `n` | `NOT NULL report` | deferrable=False, initially deferred=False, validated=True |
| `content_package_status_check` / `c` | `CHECK (status = ANY (ARRAY['REGISTERED'::text, 'VALIDATING'::text, 'INVALID'::text, 'IMPORTING'::text, 'RECONCILING'::text, 'POSTGRES_COMPLETE'::text, 'EMBEDDING'::text, 'GRAPH_PROJECTING'::text, 'COMPLETED'::text, 'FAILED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `content_package_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `content_package_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `ingest.import_conflict` / `import_conflict_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id) ON DELETE CASCADE`.
- `ingest.package_file` / `package_file_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id) ON DELETE CASCADE`.
- `ingest.package_status_event` / `package_status_event_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id) ON DELETE CASCADE`.
- `ingest.reconciliation` / `reconciliation_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id) ON DELETE CASCADE`.
- `ingest.staging_row` / `staging_row_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id) ON DELETE CASCADE`.
- `pedagogy.chapter_section` / `chapter_section_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)`.
- `pedagogy.diagram` / `diagram_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)`.
- `pedagogy.learning_item` / `learning_item_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)`.
- `pedagogy.problem_enrichment` / `problem_enrichment_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)`.
- `pedagogy.problem_source_ref` / `problem_source_ref_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)`.
- `pedagogy.solution_part` / `solution_part_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)`.
- `pedagogy.solution_source_ref` / `solution_source_ref_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)`.
- `pedagogy.solution_step` / `solution_step_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)`.
- `pedagogy.solution_step_dependency` / `solution_step_dependency_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)`.
- `pedagogy.taxonomy_edge` / `taxonomy_edge_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)`.
- `pedagogy.taxonomy_node` / `taxonomy_node_content_package_id_fkey`: `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `content_package_package_name_package_version_manifest_hash_key`: `CREATE UNIQUE INDEX content_package_package_name_package_version_manifest_hash_key ON ingest.content_package USING btree (package_name, package_version, manifest_hash)`; valid=True, ready=True.
- `content_package_pkey`: `CREATE UNIQUE INDEX content_package_pkey ON ingest.content_package USING btree (content_package_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `ingest.corpus_draft`

**Kind / use case:** table. Private question/image/new-practice draft, immutable origin and versioned review.

**Migration owner:** [025_corpus_authoring.sql](../../../mathbank-db/sql/025_corpus_authoring.sql#L2); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/corpus_authoring.py](../../../mathbank-rest/src/mathbank_rest/corpus_authoring.py#L82); [mathbank-rest/src/mathbank_rest/routers/admin_corpus.py](../../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L102).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `draft_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `kind` | `text` | no | `-` | `- / -` |
| `problem_id` | `uuid` | yes | `-` | `- / -` |
| `payload` | `jsonb` | no | `-` | `- / -` |
| `base_hash` | `text` | yes | `-` | `- / -` |
| `object_key` | `text` | yes | `-` | `- / -` |
| `state` | `text` | no | `'DRAFT'::text` | `- / -` |
| `origin` | `text` | no | `-` | `- / -` |
| `provenance` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `revision` | `integer` | no | `1` | `- / -` |
| `note` | `text` | no | `-` | `- / -` |
| `review_note` | `text` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `reviewed_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `corpus_draft_check` / `c` | `CHECK (kind = 'NEW_PROBLEM'::text OR problem_id IS NOT NULL)` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_check1` / `c` | `CHECK ((kind = 'IMAGE'::text) = (object_key IS NOT NULL))` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_draft_id_not_null` / `n` | `NOT NULL draft_id` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_kind_check` / `c` | `CHECK (kind = ANY (ARRAY['TEXT_EDIT'::text, 'IMAGE'::text, 'NEW_PROBLEM'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_kind_not_null` / `n` | `NOT NULL kind` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_note_not_null` / `n` | `NOT NULL note` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_origin_check` / `c` | `CHECK (origin = ANY (ARRAY['ADMIN'::text, 'AI'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_origin_not_null` / `n` | `NOT NULL origin` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_payload_not_null` / `n` | `NOT NULL payload` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_pkey` / `p` | `PRIMARY KEY (draft_id)` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE RESTRICT` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_provenance_not_null` / `n` | `NOT NULL provenance` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_revision_check` / `c` | `CHECK (revision > 0)` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_revision_not_null` / `n` | `NOT NULL revision` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_state_check` / `c` | `CHECK (state = ANY (ARRAY['DRAFT'::text, 'APPROVED'::text, 'REJECTED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `corpus_draft_state_not_null` / `n` | `NOT NULL state` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `corpus_draft_pkey`: `CREATE UNIQUE INDEX corpus_draft_pkey ON ingest.corpus_draft USING btree (draft_id)`; valid=True, ready=True.
- `corpus_draft_state_idx`: `CREATE INDEX corpus_draft_state_idx ON ingest.corpus_draft USING btree (state, created_at DESC)`; valid=True, ready=True.

**Triggers:**

- `protect_corpus_draft`: `CREATE TRIGGER protect_corpus_draft BEFORE DELETE OR UPDATE ON ingest.corpus_draft FOR EACH ROW EXECUTE FUNCTION ingest.protect_corpus_draft()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `ingest.import_conflict`

**Kind / use case:** table. Preserved import conflicts and human resolution decision.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L83); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L143); [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L72); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L776).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `conflict_id` | `bigint` | no | `nextval('ingest.import_conflict_conflict_id_seq'::regclass)` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |
| `entity_type` | `text` | no | `-` | `- / -` |
| `external_id` | `text` | no | `-` | `- / -` |
| `conflict_type` | `text` | no | `-` | `- / -` |
| `severity` | `text` | no | `-` | `- / -` |
| `detail` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `resolution_status` | `text` | no | `'OPEN'::text` | `- / -` |
| `resolution` | `text` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `decision` | `text` | yes | `-` | `- / -` |
| `decided_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `import_conflict_conflict_id_not_null` / `n` | `NOT NULL conflict_id` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_conflict_type_not_null` / `n` | `NOT NULL conflict_type` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_content_package_id_entity_type_external_id__key` / `u` | `UNIQUE (content_package_id, entity_type, external_id, conflict_type)` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_decision_check` / `c` | `CHECK (decision IS NULL OR (decision = ANY (ARRAY['KEEP_EXISTING'::text, 'ACCEPT_INCOMING'::text, 'MERGE_MANUALLY'::text])))` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_detail_not_null` / `n` | `NOT NULL detail` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_entity_type_not_null` / `n` | `NOT NULL entity_type` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_external_id_not_null` / `n` | `NOT NULL external_id` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_pkey` / `p` | `PRIMARY KEY (conflict_id)` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_resolution_status_check` / `c` | `CHECK (resolution_status = ANY (ARRAY['OPEN'::text, 'AUTO_RESOLVED'::text, 'RESOLVED'::text, 'IGNORED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_resolution_status_not_null` / `n` | `NOT NULL resolution_status` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_severity_check` / `c` | `CHECK (severity = ANY (ARRAY['INFO'::text, 'WARNING'::text, 'ERROR'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_severity_not_null` / `n` | `NOT NULL severity` | deferrable=False, initially deferred=False, validated=True |
| `import_conflict_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `import_conflict_content_package_id_entity_type_external_id__key`: `CREATE UNIQUE INDEX import_conflict_content_package_id_entity_type_external_id__key ON ingest.import_conflict USING btree (content_package_id, entity_type, external_id, conflict_type)`; valid=True, ready=True.
- `import_conflict_pkey`: `CREATE UNIQUE INDEX import_conflict_pkey ON ingest.import_conflict USING btree (conflict_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `ingest.import_conflict_conflict_id_seq`

**Kind:** sequence; allocates identity values for associated serial columns.
No sequence current/last value was read. Column defaults and indexes identify its table use.

### `ingest.package_file`

**Kind / use case:** table. Registered source-file checksum and entity inventory.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L53); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L147); [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L69); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L754).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `content_package_id` | `uuid` | no | `-` | `- / -` |
| `relative_path` | `text` | no | `-` | `- / -` |
| `file_role` | `text` | no | `-` | `- / -` |
| `sha256` | `text` | no | `-` | `- / -` |
| `byte_size` | `bigint` | no | `-` | `- / -` |
| `row_count` | `integer` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `package_file_byte_size_not_null` / `n` | `NOT NULL byte_size` | deferrable=False, initially deferred=False, validated=True |
| `package_file_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `package_file_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `package_file_file_role_not_null` / `n` | `NOT NULL file_role` | deferrable=False, initially deferred=False, validated=True |
| `package_file_pkey` / `p` | `PRIMARY KEY (content_package_id, relative_path)` | deferrable=False, initially deferred=False, validated=True |
| `package_file_relative_path_not_null` / `n` | `NOT NULL relative_path` | deferrable=False, initially deferred=False, validated=True |
| `package_file_sha256_not_null` / `n` | `NOT NULL sha256` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `package_file_pkey`: `CREATE UNIQUE INDEX package_file_pkey ON ingest.package_file USING btree (content_package_id, relative_path)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `ingest.package_status_event`

**Kind / use case:** table. Package stage/status history.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L43); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L116); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L725).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `event_id` | `bigint` | no | `nextval('ingest.package_status_event_event_id_seq'::regclass)` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |
| `from_status` | `text` | yes | `-` | `- / -` |
| `to_status` | `text` | no | `-` | `- / -` |
| `scope` | `text` | yes | `-` | `- / -` |
| `detail` | `text` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `package_status_event_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `package_status_event_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `package_status_event_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `package_status_event_event_id_not_null` / `n` | `NOT NULL event_id` | deferrable=False, initially deferred=False, validated=True |
| `package_status_event_pkey` / `p` | `PRIMARY KEY (event_id)` | deferrable=False, initially deferred=False, validated=True |
| `package_status_event_to_status_not_null` / `n` | `NOT NULL to_status` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `package_status_event_pkey`: `CREATE UNIQUE INDEX package_status_event_pkey ON ingest.package_status_event USING btree (event_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `ingest.package_status_event_event_id_seq`

**Kind:** sequence; allocates identity values for associated serial columns.
No sequence current/last value was read. Column defaults and indexes identify its table use.

### `ingest.reconciliation`

**Kind / use case:** table. Source/valid/imported/conflict counts by entity and package.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L99); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L76); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L1144).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `content_package_id` | `uuid` | no | `-` | `- / -` |
| `scope` | `text` | no | `-` | `- / -` |
| `entity_type` | `text` | no | `-` | `- / -` |
| `source_count` | `integer` | no | `0` | `- / -` |
| `valid_count` | `integer` | no | `0` | `- / -` |
| `imported_count` | `integer` | no | `0` | `- / -` |
| `created_count` | `integer` | no | `0` | `- / -` |
| `updated_count` | `integer` | no | `0` | `- / -` |
| `unchanged_count` | `integer` | no | `0` | `- / -` |
| `rejected_count` | `integer` | no | `0` | `- / -` |
| `conflict_count` | `integer` | no | `0` | `- / -` |
| `present_in_db` | `integer` | no | `0` | `- / -` |
| `reconciled` | `boolean` | no | `false` | `- / -` |
| `reconciled_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `reconciliation_conflict_count_not_null` / `n` | `NOT NULL conflict_count` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_created_count_not_null` / `n` | `NOT NULL created_count` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_entity_type_not_null` / `n` | `NOT NULL entity_type` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_imported_count_not_null` / `n` | `NOT NULL imported_count` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_pkey` / `p` | `PRIMARY KEY (content_package_id, scope, entity_type)` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_present_in_db_not_null` / `n` | `NOT NULL present_in_db` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_reconciled_at_not_null` / `n` | `NOT NULL reconciled_at` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_reconciled_not_null` / `n` | `NOT NULL reconciled` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_rejected_count_not_null` / `n` | `NOT NULL rejected_count` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_scope_not_null` / `n` | `NOT NULL scope` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_source_count_not_null` / `n` | `NOT NULL source_count` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_unchanged_count_not_null` / `n` | `NOT NULL unchanged_count` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_updated_count_not_null` / `n` | `NOT NULL updated_count` | deferrable=False, initially deferred=False, validated=True |
| `reconciliation_valid_count_not_null` / `n` | `NOT NULL valid_count` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `reconciliation_pkey`: `CREATE UNIQUE INDEX reconciliation_pkey ON ingest.reconciliation USING btree (content_package_id, scope, entity_type)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `ingest.staging_row`

**Kind / use case:** table. Raw staged import payload, validation outcome and source row identity.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L63); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L70); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L767).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `staging_row_id` | `bigint` | no | `nextval('ingest.staging_row_staging_row_id_seq'::regclass)` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |
| `source_file` | `text` | no | `-` | `- / -` |
| `source_row_number` | `integer` | no | `-` | `- / -` |
| `entity_type` | `text` | no | `-` | `- / -` |
| `external_id` | `text` | yes | `-` | `- / -` |
| `source_row_json` | `jsonb` | no | `-` | `- / -` |
| `validation_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `validation_errors` | `jsonb` | no | `'[]'::jsonb` | `- / -` |
| `validation_warnings` | `jsonb` | no | `'[]'::jsonb` | `- / -` |
| `target_key` | `text` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `staging_row_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_content_package_id_source_file_source_row_numbe_key` / `u` | `UNIQUE (content_package_id, source_file, source_row_number)` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_entity_type_not_null` / `n` | `NOT NULL entity_type` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_pkey` / `p` | `PRIMARY KEY (staging_row_id)` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_source_file_not_null` / `n` | `NOT NULL source_file` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_source_row_json_not_null` / `n` | `NOT NULL source_row_json` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_source_row_number_not_null` / `n` | `NOT NULL source_row_number` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_staging_row_id_not_null` / `n` | `NOT NULL staging_row_id` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_validation_errors_not_null` / `n` | `NOT NULL validation_errors` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_validation_status_check` / `c` | `CHECK (validation_status = ANY (ARRAY['PENDING'::text, 'VALID'::text, 'IMPORTED'::text, 'REJECTED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_validation_status_not_null` / `n` | `NOT NULL validation_status` | deferrable=False, initially deferred=False, validated=True |
| `staging_row_validation_warnings_not_null` / `n` | `NOT NULL validation_warnings` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `staging_row_content_package_id_source_file_source_row_numbe_key`: `CREATE UNIQUE INDEX staging_row_content_package_id_source_file_source_row_numbe_key ON ingest.staging_row USING btree (content_package_id, source_file, source_row_number)`; valid=True, ready=True.
- `staging_row_pkey`: `CREATE UNIQUE INDEX staging_row_pkey ON ingest.staging_row USING btree (staging_row_id)`; valid=True, ready=True.
- `staging_row_status_idx`: `CREATE INDEX staging_row_status_idx ON ingest.staging_row USING btree (content_package_id, entity_type, validation_status)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `ingest.staging_row_staging_row_id_seq`

**Kind:** sequence; allocates identity values for associated serial columns.
No sequence current/last value was read. Column defaults and indexes identify its table use.

## Functions and routines

Extension routines are owned by their installed extension, not project migration code.
Volatility: i=immutable, s=stable, v=volatile. No routine was invoked by this inspection.

| Signature | Returns | Language / volatility | Security definer | Owner / source |
|---|---|---|---|---|
| `admin_review_action_append_only(-)` | `trigger` | plpgsql / v | False | [019_admin_import_review.sql](../../../mathbank-db/sql/019_admin_import_review.sql) |
| `protect_corpus_draft(-)` | `trigger` | plpgsql / v | False | [025_corpus_authoring.sql](../../../mathbank-db/sql/025_corpus_authoring.sql) |

### Observed definition: `ingest.admin_review_action_append_only`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION ingest.admin_review_action_append_only()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    RAISE EXCEPTION 'ingest.admin_review_action is append-only';
END $function$
```

### Observed definition: `ingest.protect_corpus_draft`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION ingest.protect_corpus_draft()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_OP='DELETE' OR OLD.state <> 'DRAFT' THEN
        RAISE EXCEPTION 'Corpus review records cannot be deleted or changed after review';
    END IF;
    IF NEW.origin IS DISTINCT FROM OLD.origin OR NEW.provenance IS DISTINCT FROM OLD.provenance THEN
        RAISE EXCEPTION 'Corpus draft origin and creation provenance are immutable';
    END IF;
    RETURN NEW;
END $function$
```
