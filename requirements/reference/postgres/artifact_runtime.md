# PostgreSQL `artifact_runtime` schema

**Role:** Declarative artifact bundles. Requests, assets, overlays/frames, validation, immutable lineage and explicit artifact indexing.

**Access family:** `/v1/artifacts/*`; staff generate/publish/index; authenticated preview/read/requests with route-specific ownership.

**Evidence:** live catalog metadata at 2026-10-07T13:40:57.292324+00:00; source `375f3743357cef814c50e3c8752f7f4ce2d6ebe5`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `artifact_runtime.artifact_annotation`

**Kind / use case:** table. Element-level explanation/concept/hint annotations.

**Migration owner:** [022_artifact_runtime.sql](../../../mathbank-db/sql/022_artifact_runtime.sql#L86); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/artifact_runtime.py](../../../mathbank-rest/src/mathbank_rest/artifact_runtime.py#L1071).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `artifact_annotation_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `artifact_bundle_id` | `uuid` | no | `-` | `- / -` |
| `ordinal` | `integer` | no | `-` | `- / -` |
| `step_number` | `integer` | no | `-` | `- / -` |
| `caption` | `text` | no | `-` | `- / -` |
| `concept_tag` | `text` | no | `-` | `- / -` |
| `hint_tag` | `text` | yes | `-` | `- / -` |
| `explanation_text` | `text` | no | `-` | `- / -` |
| `linked_step_id` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `artifact_annotation_artifact_annotation_id_not_null` / `n` | `NOT NULL artifact_annotation_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_annotation_artifact_bundle_id_fkey` / `f` | `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `artifact_annotation_artifact_bundle_id_not_null` / `n` | `NOT NULL artifact_bundle_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_annotation_artifact_bundle_id_ordinal_key` / `u` | `UNIQUE (artifact_bundle_id, ordinal)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_annotation_caption_not_null` / `n` | `NOT NULL caption` | deferrable=False, initially deferred=False, validated=True |
| `artifact_annotation_concept_tag_not_null` / `n` | `NOT NULL concept_tag` | deferrable=False, initially deferred=False, validated=True |
| `artifact_annotation_explanation_text_not_null` / `n` | `NOT NULL explanation_text` | deferrable=False, initially deferred=False, validated=True |
| `artifact_annotation_ordinal_not_null` / `n` | `NOT NULL ordinal` | deferrable=False, initially deferred=False, validated=True |
| `artifact_annotation_pkey` / `p` | `PRIMARY KEY (artifact_annotation_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_annotation_step_number_check` / `c` | `CHECK (step_number > 0)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_annotation_step_number_not_null` / `n` | `NOT NULL step_number` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `artifact_annotation_artifact_bundle_id_ordinal_key`: `CREATE UNIQUE INDEX artifact_annotation_artifact_bundle_id_ordinal_key ON artifact_runtime.artifact_annotation USING btree (artifact_bundle_id, ordinal)`; valid=True, ready=True.
- `artifact_annotation_pkey`: `CREATE UNIQUE INDEX artifact_annotation_pkey ON artifact_runtime.artifact_annotation USING btree (artifact_annotation_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `artifact_runtime.artifact_asset`

**Kind / use case:** table. Private immutable SVG/LaTeX/manifest/export assets and integrity metadata.

**Migration owner:** [022_artifact_runtime.sql](../../../mathbank-db/sql/022_artifact_runtime.sql#L44); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/artifact_runtime.py](../../../mathbank-rest/src/mathbank_rest/artifact_runtime.py#L820).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `artifact_asset_id` | `uuid` | no | `-` | `- / -` |
| `artifact_bundle_id` | `uuid` | no | `-` | `- / -` |
| `asset_type` | `text` | no | `-` | `- / -` |
| `object_key` | `text` | no | `-` | `- / -` |
| `sha256` | `text` | no | `-` | `- / -` |
| `size_bytes` | `integer` | no | `-` | `- / -` |
| `mime_type` | `text` | no | `-` | `- / -` |
| `render_format` | `text` | no | `-` | `- / -` |
| `width` | `integer` | yes | `-` | `- / -` |
| `height` | `integer` | yes | `-` | `- / -` |
| `element_ids` | `jsonb` | no | `'[]'::jsonb` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `artifact_asset_artifact_asset_id_not_null` / `n` | `NOT NULL artifact_asset_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_artifact_bundle_id_fkey` / `f` | `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_artifact_bundle_id_not_null` / `n` | `NOT NULL artifact_bundle_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_asset_type_check` / `c` | `CHECK (asset_type = ANY (ARRAY['SVG_DIAGRAM'::text, 'LATEX_CARD'::text, 'FRAME_SEQUENCE'::text, 'MANIM_EXPORT_SPEC'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_asset_type_not_null` / `n` | `NOT NULL asset_type` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_element_ids_not_null` / `n` | `NOT NULL element_ids` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_mime_type_not_null` / `n` | `NOT NULL mime_type` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_object_key_check` / `c` | `CHECK (object_key ~ '^[0-9a-f]{32}\.[a-z0-9]{1,10}$'::text)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_object_key_key` / `u` | `UNIQUE (object_key)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_object_key_not_null` / `n` | `NOT NULL object_key` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_pkey` / `p` | `PRIMARY KEY (artifact_asset_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_render_format_not_null` / `n` | `NOT NULL render_format` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_sha256_check` / `c` | `CHECK (sha256 ~ '^[0-9a-f]{64}$'::text)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_sha256_not_null` / `n` | `NOT NULL sha256` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_size_bytes_check` / `c` | `CHECK (size_bytes >= 1 AND size_bytes <= 26214400)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_asset_size_bytes_not_null` / `n` | `NOT NULL size_bytes` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `artifact_runtime.artifact_metadata` / `artifact_metadata_artifact_asset_id_fkey`: `FOREIGN KEY (artifact_asset_id) REFERENCES artifact_runtime.artifact_asset(artifact_asset_id) ON DELETE CASCADE`.
- `artifact_runtime.frame_sequence` / `frame_sequence_manifest_asset_id_fkey`: `FOREIGN KEY (manifest_asset_id) REFERENCES artifact_runtime.artifact_asset(artifact_asset_id)`.
- `artifact_runtime.overlay_state` / `overlay_state_base_asset_id_fkey`: `FOREIGN KEY (base_asset_id) REFERENCES artifact_runtime.artifact_asset(artifact_asset_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `artifact_asset_object_key_key`: `CREATE UNIQUE INDEX artifact_asset_object_key_key ON artifact_runtime.artifact_asset USING btree (object_key)`; valid=True, ready=True.
- `artifact_asset_pkey`: `CREATE UNIQUE INDEX artifact_asset_pkey ON artifact_runtime.artifact_asset USING btree (artifact_asset_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `artifact_runtime.artifact_bundle`

**Kind / use case:** table. Generated bundle version, publication state and searchable summary.

**Migration owner:** [022_artifact_runtime.sql](../../../mathbank-db/sql/022_artifact_runtime.sql#L21); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/artifact_runtime.py](../../../mathbank-rest/src/mathbank_rest/artifact_runtime.py#L809).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `artifact_bundle_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `artifact_request_id` | `uuid` | no | `-` | `- / -` |
| `parent_bundle_id` | `uuid` | yes | `-` | `- / -` |
| `subject` | `text` | no | `-` | `- / -` |
| `topic` | `text` | no | `-` | `- / -` |
| `subtopic` | `text` | yes | `-` | `- / -` |
| `title` | `text` | no | `-` | `- / -` |
| `summary` | `text` | no | `-` | `- / -` |
| `difficulty_band` | `text` | no | `-` | `- / -` |
| `grade_band` | `text` | no | `-` | `- / -` |
| `status` | `text` | no | `'DRAFT'::text` | `- / -` |
| `review_state` | `text` | no | `'VALIDATED'::text` | `- / -` |
| `version` | `integer` | no | `1` | `- / -` |
| `created_by_agent` | `text` | no | `-` | `- / -` |
| `rule_profile_id` | `text` | no | `-` | `- / -` |
| `annotation_profile_id` | `text` | no | `-` | `- / -` |
| `search_text` | `text` | no | `-` | `- / -` |
| `metadata` | `jsonb` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `published_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `artifact_bundle_annotation_profile_id_not_null` / `n` | `NOT NULL annotation_profile_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_artifact_bundle_id_not_null` / `n` | `NOT NULL artifact_bundle_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_artifact_request_id_fkey` / `f` | `FOREIGN KEY (artifact_request_id) REFERENCES artifact_runtime.artifact_request(artifact_request_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_artifact_request_id_not_null` / `n` | `NOT NULL artifact_request_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_artifact_request_id_version_key` / `u` | `UNIQUE (artifact_request_id, version)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_created_by_agent_not_null` / `n` | `NOT NULL created_by_agent` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_difficulty_band_not_null` / `n` | `NOT NULL difficulty_band` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_grade_band_not_null` / `n` | `NOT NULL grade_band` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_metadata_not_null` / `n` | `NOT NULL metadata` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_parent_bundle_id_fkey` / `f` | `FOREIGN KEY (parent_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_pkey` / `p` | `PRIMARY KEY (artifact_bundle_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_review_state_check` / `c` | `CHECK (review_state = ANY (ARRAY['VALIDATED'::text, 'APPROVED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_review_state_not_null` / `n` | `NOT NULL review_state` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_rule_profile_id_not_null` / `n` | `NOT NULL rule_profile_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_search_text_not_null` / `n` | `NOT NULL search_text` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_status_check` / `c` | `CHECK (status = ANY (ARRAY['DRAFT'::text, 'PUBLISHED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_subject_not_null` / `n` | `NOT NULL subject` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_summary_not_null` / `n` | `NOT NULL summary` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_title_not_null` / `n` | `NOT NULL title` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_topic_not_null` / `n` | `NOT NULL topic` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_version_check` / `c` | `CHECK (version > 0)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_bundle_version_not_null` / `n` | `NOT NULL version` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `artifact_runtime.artifact_annotation` / `artifact_annotation_artifact_bundle_id_fkey`: `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE`.
- `artifact_runtime.artifact_asset` / `artifact_asset_artifact_bundle_id_fkey`: `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE`.
- `artifact_runtime.artifact_bundle` / `artifact_bundle_parent_bundle_id_fkey`: `FOREIGN KEY (parent_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id)`.
- `artifact_runtime.artifact_embedding` / `artifact_embedding_artifact_bundle_id_fkey`: `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE`.
- `artifact_runtime.artifact_lineage` / `artifact_lineage_artifact_bundle_id_fkey`: `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE`.
- `artifact_runtime.artifact_lineage` / `artifact_lineage_parent_bundle_id_fkey`: `FOREIGN KEY (parent_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id)`.
- `artifact_runtime.artifact_search_tag` / `artifact_search_tag_artifact_bundle_id_fkey`: `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE`.
- `artifact_runtime.frame_sequence` / `frame_sequence_artifact_bundle_id_fkey`: `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE`.
- `artifact_runtime.overlay_state` / `overlay_state_artifact_bundle_id_fkey`: `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE`.
- `artifact_runtime.validation_result` / `validation_result_artifact_bundle_id_fkey`: `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `artifact_bundle_artifact_request_id_version_key`: `CREATE UNIQUE INDEX artifact_bundle_artifact_request_id_version_key ON artifact_runtime.artifact_bundle USING btree (artifact_request_id, version)`; valid=True, ready=True.
- `artifact_bundle_pkey`: `CREATE UNIQUE INDEX artifact_bundle_pkey ON artifact_runtime.artifact_bundle USING btree (artifact_bundle_id)`; valid=True, ready=True.
- `artifact_bundle_subject_status`: `CREATE INDEX artifact_bundle_subject_status ON artifact_runtime.artifact_bundle USING btree (subject, status)`; valid=True, ready=True.
- `artifact_lexical_search`: `CREATE INDEX artifact_lexical_search ON artifact_runtime.artifact_bundle USING gin (to_tsvector('simple'::regconfig, search_text))`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `artifact_runtime.artifact_embedding`

**Kind / use case:** table. Explicit model/hash/dimension-indexed artifact vector; not core search.embedding.

**Migration owner:** [022_artifact_runtime.sql](../../../mathbank-db/sql/022_artifact_runtime.sql#L119); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/artifact_runtime.py](../../../mathbank-rest/src/mathbank_rest/artifact_runtime.py#L1160).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `artifact_bundle_id` | `uuid` | no | `-` | `- / -` |
| `model` | `text` | no | `-` | `- / -` |
| `dimensions` | `integer` | no | `1536` | `- / -` |
| `search_text_sha256` | `text` | no | `-` | `- / -` |
| `embedding` | `vector` | no | `-` | `- / -` |
| `indexed_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `artifact_embedding_artifact_bundle_id_fkey` / `f` | `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `artifact_embedding_artifact_bundle_id_not_null` / `n` | `NOT NULL artifact_bundle_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_embedding_check` / `c` | `CHECK (vector_dims(embedding) = dimensions)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_embedding_dimensions_check` / `c` | `CHECK (dimensions >= 1 AND dimensions <= 8192)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_embedding_dimensions_not_null` / `n` | `NOT NULL dimensions` | deferrable=False, initially deferred=False, validated=True |
| `artifact_embedding_embedding_not_null` / `n` | `NOT NULL embedding` | deferrable=False, initially deferred=False, validated=True |
| `artifact_embedding_indexed_at_not_null` / `n` | `NOT NULL indexed_at` | deferrable=False, initially deferred=False, validated=True |
| `artifact_embedding_model_not_null` / `n` | `NOT NULL model` | deferrable=False, initially deferred=False, validated=True |
| `artifact_embedding_pkey` / `p` | `PRIMARY KEY (artifact_bundle_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_embedding_search_text_sha256_not_null` / `n` | `NOT NULL search_text_sha256` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `artifact_embedding_pkey`: `CREATE UNIQUE INDEX artifact_embedding_pkey ON artifact_runtime.artifact_embedding USING btree (artifact_bundle_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `artifact_runtime.artifact_lineage`

**Kind / use case:** table. Immutable bundle parent/source/reference derivation provenance.

**Migration owner:** [022_artifact_runtime.sql](../../../mathbank-db/sql/022_artifact_runtime.sql#L106); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/artifact_runtime.py](../../../mathbank-rest/src/mathbank_rest/artifact_runtime.py#L1086).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `artifact_bundle_id` | `uuid` | no | `-` | `- / -` |
| `artifact_request_id` | `uuid` | no | `-` | `- / -` |
| `parent_bundle_id` | `uuid` | yes | `-` | `- / -` |
| `generator_version` | `text` | no | `-` | `- / -` |
| `source_spec_sha256` | `text` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `artifact_lineage_artifact_bundle_id_fkey` / `f` | `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `artifact_lineage_artifact_bundle_id_not_null` / `n` | `NOT NULL artifact_bundle_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_lineage_artifact_request_id_fkey` / `f` | `FOREIGN KEY (artifact_request_id) REFERENCES artifact_runtime.artifact_request(artifact_request_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_lineage_artifact_request_id_not_null` / `n` | `NOT NULL artifact_request_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_lineage_generator_version_not_null` / `n` | `NOT NULL generator_version` | deferrable=False, initially deferred=False, validated=True |
| `artifact_lineage_parent_bundle_id_fkey` / `f` | `FOREIGN KEY (parent_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_lineage_pkey` / `p` | `PRIMARY KEY (artifact_bundle_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_lineage_source_spec_sha256_not_null` / `n` | `NOT NULL source_spec_sha256` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `artifact_lineage_pkey`: `CREATE UNIQUE INDEX artifact_lineage_pkey ON artifact_runtime.artifact_lineage USING btree (artifact_bundle_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `artifact_runtime.artifact_metadata`

**Kind / use case:** table. Structured subject/topic/skill metadata for assets.

**Migration owner:** [022_artifact_runtime.sql](../../../mathbank-db/sql/022_artifact_runtime.sql#L58); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/artifact_runtime.py](../../../mathbank-rest/src/mathbank_rest/artifact_runtime.py#L1057).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `artifact_asset_id` | `uuid` | no | `-` | `- / -` |
| `subject` | `text` | no | `-` | `- / -` |
| `concept_ids` | `text[]` | no | `'{}'::text[]` | `- / -` |
| `skill_ids` | `text[]` | no | `'{}'::text[]` | `- / -` |
| `theorem_ids` | `text[]` | no | `'{}'::text[]` | `- / -` |
| `step_labels` | `text[]` | no | `'{}'::text[]` | `- / -` |
| `rule_profile_id` | `text` | no | `-` | `- / -` |
| `annotation_profile_id` | `text` | no | `-` | `- / -` |
| `search_text` | `text` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `artifact_metadata_annotation_profile_id_not_null` / `n` | `NOT NULL annotation_profile_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_metadata_artifact_asset_id_fkey` / `f` | `FOREIGN KEY (artifact_asset_id) REFERENCES artifact_runtime.artifact_asset(artifact_asset_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `artifact_metadata_artifact_asset_id_not_null` / `n` | `NOT NULL artifact_asset_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_metadata_concept_ids_not_null` / `n` | `NOT NULL concept_ids` | deferrable=False, initially deferred=False, validated=True |
| `artifact_metadata_pkey` / `p` | `PRIMARY KEY (artifact_asset_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_metadata_rule_profile_id_not_null` / `n` | `NOT NULL rule_profile_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_metadata_search_text_not_null` / `n` | `NOT NULL search_text` | deferrable=False, initially deferred=False, validated=True |
| `artifact_metadata_skill_ids_not_null` / `n` | `NOT NULL skill_ids` | deferrable=False, initially deferred=False, validated=True |
| `artifact_metadata_step_labels_not_null` / `n` | `NOT NULL step_labels` | deferrable=False, initially deferred=False, validated=True |
| `artifact_metadata_subject_not_null` / `n` | `NOT NULL subject` | deferrable=False, initially deferred=False, validated=True |
| `artifact_metadata_theorem_ids_not_null` / `n` | `NOT NULL theorem_ids` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `artifact_metadata_pkey`: `CREATE UNIQUE INDEX artifact_metadata_pkey ON artifact_runtime.artifact_metadata USING btree (artifact_asset_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `artifact_runtime.artifact_request`

**Kind / use case:** table. Owned declarative generation request with logical problem/step association.

**Migration owner:** [022_artifact_runtime.sql](../../../mathbank-db/sql/022_artifact_runtime.sql#L6); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/artifact_runtime.py](../../../mathbank-rest/src/mathbank_rest/artifact_runtime.py#L787).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `artifact_request_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `owner_student_id` | `uuid` | yes | `-` | `- / -` |
| `created_by` | `text` | no | `-` | `- / -` |
| `request_source` | `text` | no | `-` | `- / -` |
| `subject` | `text` | no | `-` | `- / -` |
| `topic` | `text` | no | `-` | `- / -` |
| `subtopic` | `text` | yes | `-` | `- / -` |
| `goal_type` | `text` | no | `-` | `- / -` |
| `linked_problem_id` | `uuid` | yes | `-` | `- / -` |
| `linked_solution_step_id` | `text` | yes | `-` | `- / -` |
| `spec` | `jsonb` | no | `-` | `- / -` |
| `status` | `text` | no | `'REQUESTED'::text` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `artifact_request_artifact_request_id_not_null` / `n` | `NOT NULL artifact_request_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_created_by_not_null` / `n` | `NOT NULL created_by` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_goal_type_not_null` / `n` | `NOT NULL goal_type` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_linked_problem_id_fkey` / `f` | `FOREIGN KEY (linked_problem_id) REFERENCES core.problem(problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_owner_student_id_fkey` / `f` | `FOREIGN KEY (owner_student_id) REFERENCES learner.student_profile(student_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_pkey` / `p` | `PRIMARY KEY (artifact_request_id)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_request_source_not_null` / `n` | `NOT NULL request_source` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_spec_check` / `c` | `CHECK (jsonb_typeof(spec) = 'object'::text)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_spec_not_null` / `n` | `NOT NULL spec` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_status_check` / `c` | `CHECK (status = ANY (ARRAY['REQUESTED'::text, 'GENERATED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_subject_check` / `c` | `CHECK (subject = ANY (ARRAY['GEOMETRY'::text, 'ALGEBRA'::text, 'COMBINATORICS'::text, 'NUMBER_THEORY'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_subject_not_null` / `n` | `NOT NULL subject` | deferrable=False, initially deferred=False, validated=True |
| `artifact_request_topic_not_null` / `n` | `NOT NULL topic` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `artifact_runtime.artifact_bundle` / `artifact_bundle_artifact_request_id_fkey`: `FOREIGN KEY (artifact_request_id) REFERENCES artifact_runtime.artifact_request(artifact_request_id)`.
- `artifact_runtime.artifact_lineage` / `artifact_lineage_artifact_request_id_fkey`: `FOREIGN KEY (artifact_request_id) REFERENCES artifact_runtime.artifact_request(artifact_request_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `artifact_request_pkey`: `CREATE UNIQUE INDEX artifact_request_pkey ON artifact_runtime.artifact_request USING btree (artifact_request_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `artifact_runtime.artifact_search_tag`

**Kind / use case:** table. Stored lexical/filter tags for bundle retrieval.

**Migration owner:** [022_artifact_runtime.sql](../../../mathbank-db/sql/022_artifact_runtime.sql#L113); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/artifact_runtime.py](../../../mathbank-rest/src/mathbank_rest/artifact_runtime.py#L1093).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `artifact_bundle_id` | `uuid` | no | `-` | `- / -` |
| `tag_type` | `text` | no | `-` | `- / -` |
| `tag` | `text` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `artifact_search_tag_artifact_bundle_id_fkey` / `f` | `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `artifact_search_tag_artifact_bundle_id_not_null` / `n` | `NOT NULL artifact_bundle_id` | deferrable=False, initially deferred=False, validated=True |
| `artifact_search_tag_pkey` / `p` | `PRIMARY KEY (artifact_bundle_id, tag_type, tag)` | deferrable=False, initially deferred=False, validated=True |
| `artifact_search_tag_tag_not_null` / `n` | `NOT NULL tag` | deferrable=False, initially deferred=False, validated=True |
| `artifact_search_tag_tag_type_check` / `c` | `CHECK (tag_type = ANY (ARRAY['concept'::text, 'skill'::text, 'theorem'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `artifact_search_tag_tag_type_not_null` / `n` | `NOT NULL tag_type` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `artifact_search_tag_pkey`: `CREATE UNIQUE INDEX artifact_search_tag_pkey ON artifact_runtime.artifact_search_tag USING btree (artifact_bundle_id, tag_type, tag)`; valid=True, ready=True.
- `artifact_search_tags`: `CREATE INDEX artifact_search_tags ON artifact_runtime.artifact_search_tag USING btree (tag_type, tag)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `artifact_runtime.frame_sequence`

**Kind / use case:** table. Frame manifest, stable element IDs, captions and playback metadata.

**Migration owner:** [022_artifact_runtime.sql](../../../mathbank-db/sql/022_artifact_runtime.sql#L79); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/artifact_runtime.py](../../../mathbank-rest/src/mathbank_rest/artifact_runtime.py#L844).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `frame_sequence_id` | `uuid` | no | `-` | `- / -` |
| `artifact_bundle_id` | `uuid` | no | `-` | `- / -` |
| `manifest_asset_id` | `uuid` | no | `-` | `- / -` |
| `ordered_overlay_state_ids` | `uuid[]` | no | `-` | `- / -` |
| `transition_notes` | `text` | no | `''::text` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `frame_sequence_artifact_bundle_id_fkey` / `f` | `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `frame_sequence_artifact_bundle_id_key` / `u` | `UNIQUE (artifact_bundle_id)` | deferrable=False, initially deferred=False, validated=True |
| `frame_sequence_artifact_bundle_id_not_null` / `n` | `NOT NULL artifact_bundle_id` | deferrable=False, initially deferred=False, validated=True |
| `frame_sequence_frame_sequence_id_not_null` / `n` | `NOT NULL frame_sequence_id` | deferrable=False, initially deferred=False, validated=True |
| `frame_sequence_manifest_asset_id_fkey` / `f` | `FOREIGN KEY (manifest_asset_id) REFERENCES artifact_runtime.artifact_asset(artifact_asset_id)` | deferrable=False, initially deferred=False, validated=True |
| `frame_sequence_manifest_asset_id_not_null` / `n` | `NOT NULL manifest_asset_id` | deferrable=False, initially deferred=False, validated=True |
| `frame_sequence_ordered_overlay_state_ids_not_null` / `n` | `NOT NULL ordered_overlay_state_ids` | deferrable=False, initially deferred=False, validated=True |
| `frame_sequence_pkey` / `p` | `PRIMARY KEY (frame_sequence_id)` | deferrable=False, initially deferred=False, validated=True |
| `frame_sequence_transition_notes_not_null` / `n` | `NOT NULL transition_notes` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `frame_sequence_artifact_bundle_id_key`: `CREATE UNIQUE INDEX frame_sequence_artifact_bundle_id_key ON artifact_runtime.frame_sequence USING btree (artifact_bundle_id)`; valid=True, ready=True.
- `frame_sequence_pkey`: `CREATE UNIQUE INDEX frame_sequence_pkey ON artifact_runtime.frame_sequence USING btree (frame_sequence_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `artifact_runtime.overlay_state`

**Kind / use case:** table. Ordered reset-to-base declarative overlays with logical step links.

**Migration owner:** [022_artifact_runtime.sql](../../../mathbank-db/sql/022_artifact_runtime.sql#L69); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/artifact_runtime.py](../../../mathbank-rest/src/mathbank_rest/artifact_runtime.py#L1065).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `overlay_state_id` | `uuid` | no | `-` | `- / -` |
| `artifact_bundle_id` | `uuid` | no | `-` | `- / -` |
| `base_asset_id` | `uuid` | no | `-` | `- / -` |
| `ordinal` | `integer` | no | `-` | `- / -` |
| `actions` | `jsonb` | no | `-` | `- / -` |
| `caption` | `text` | no | `-` | `- / -` |
| `linked_step_id` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `overlay_state_actions_check` / `c` | `CHECK (jsonb_typeof(actions) = 'array'::text)` | deferrable=False, initially deferred=False, validated=True |
| `overlay_state_actions_not_null` / `n` | `NOT NULL actions` | deferrable=False, initially deferred=False, validated=True |
| `overlay_state_artifact_bundle_id_fkey` / `f` | `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `overlay_state_artifact_bundle_id_not_null` / `n` | `NOT NULL artifact_bundle_id` | deferrable=False, initially deferred=False, validated=True |
| `overlay_state_artifact_bundle_id_ordinal_key` / `u` | `UNIQUE (artifact_bundle_id, ordinal)` | deferrable=False, initially deferred=False, validated=True |
| `overlay_state_base_asset_id_fkey` / `f` | `FOREIGN KEY (base_asset_id) REFERENCES artifact_runtime.artifact_asset(artifact_asset_id)` | deferrable=False, initially deferred=False, validated=True |
| `overlay_state_base_asset_id_not_null` / `n` | `NOT NULL base_asset_id` | deferrable=False, initially deferred=False, validated=True |
| `overlay_state_caption_not_null` / `n` | `NOT NULL caption` | deferrable=False, initially deferred=False, validated=True |
| `overlay_state_ordinal_check` / `c` | `CHECK (ordinal >= 0)` | deferrable=False, initially deferred=False, validated=True |
| `overlay_state_ordinal_not_null` / `n` | `NOT NULL ordinal` | deferrable=False, initially deferred=False, validated=True |
| `overlay_state_overlay_state_id_not_null` / `n` | `NOT NULL overlay_state_id` | deferrable=False, initially deferred=False, validated=True |
| `overlay_state_pkey` / `p` | `PRIMARY KEY (overlay_state_id)` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `overlay_state_artifact_bundle_id_ordinal_key`: `CREATE UNIQUE INDEX overlay_state_artifact_bundle_id_ordinal_key ON artifact_runtime.overlay_state USING btree (artifact_bundle_id, ordinal)`; valid=True, ready=True.
- `overlay_state_pkey`: `CREATE UNIQUE INDEX overlay_state_pkey ON artifact_runtime.overlay_state USING btree (overlay_state_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `artifact_runtime.validation_result`

**Kind / use case:** table. Artifact validation evidence/profile/errors, not mathematical proof.

**Migration owner:** [022_artifact_runtime.sql](../../../mathbank-db/sql/022_artifact_runtime.sql#L98); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/artifact_runtime.py](../../../mathbank-rest/src/mathbank_rest/artifact_runtime.py#L1102).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `validation_result_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `artifact_bundle_id` | `uuid` | no | `-` | `- / -` |
| `valid` | `boolean` | no | `-` | `- / -` |
| `validator_version` | `text` | no | `-` | `- / -` |
| `report` | `jsonb` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `validation_result_artifact_bundle_id_fkey` / `f` | `FOREIGN KEY (artifact_bundle_id) REFERENCES artifact_runtime.artifact_bundle(artifact_bundle_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `validation_result_artifact_bundle_id_not_null` / `n` | `NOT NULL artifact_bundle_id` | deferrable=False, initially deferred=False, validated=True |
| `validation_result_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `validation_result_pkey` / `p` | `PRIMARY KEY (validation_result_id)` | deferrable=False, initially deferred=False, validated=True |
| `validation_result_report_not_null` / `n` | `NOT NULL report` | deferrable=False, initially deferred=False, validated=True |
| `validation_result_valid_not_null` / `n` | `NOT NULL valid` | deferrable=False, initially deferred=False, validated=True |
| `validation_result_validation_result_id_not_null` / `n` | `NOT NULL validation_result_id` | deferrable=False, initially deferred=False, validated=True |
| `validation_result_validator_version_not_null` / `n` | `NOT NULL validator_version` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `validation_result_pkey`: `CREATE UNIQUE INDEX validation_result_pkey ON artifact_runtime.validation_result USING btree (validation_result_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

