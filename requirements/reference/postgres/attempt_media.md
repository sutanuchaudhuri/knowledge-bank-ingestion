# PostgreSQL `attempt_media` schema

**Role:** Private learner evidence. Uploads, candidate transcription/steps, approval versions and assessed alignments.

**Access family:** `/v1/attempt-media/*`; JWT ownership, staff review; private bytes via authenticated handlers.

**Evidence:** live catalog metadata at 2026-10-07T13:40:57.292324+00:00; source `375f3743357cef814c50e3c8752f7f4ce2d6ebe5`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `attempt_media.approval`

**Kind / use case:** table. Explicit approved transcription version and immutable approval record.

**Migration owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql#L96); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/attempt_media.py#L136); [mathbank-rest/src/mathbank_rest/routers/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L484).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `submission_id` | `uuid` | no | `-` | `- / -` |
| `approved_version` | `integer` | no | `-` | `- / -` |
| `transcription_version` | `integer` | no | `-` | `- / -` |
| `learner_attempt_id` | `uuid` | no | `-` | `- / -` |
| `approved_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `student_edit_summary` | `text` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `approval_approved_at_not_null` / `n` | `NOT NULL approved_at` | deferrable=False, initially deferred=False, validated=True |
| `approval_approved_version_not_null` / `n` | `NOT NULL approved_version` | deferrable=False, initially deferred=False, validated=True |
| `approval_learner_attempt_id_fkey` / `f` | `FOREIGN KEY (learner_attempt_id) REFERENCES learner.attempt(attempt_id)` | deferrable=False, initially deferred=False, validated=True |
| `approval_learner_attempt_id_key` / `u` | `UNIQUE (learner_attempt_id)` | deferrable=False, initially deferred=False, validated=True |
| `approval_learner_attempt_id_not_null` / `n` | `NOT NULL learner_attempt_id` | deferrable=False, initially deferred=False, validated=True |
| `approval_pkey` / `p` | `PRIMARY KEY (submission_id, approved_version)` | deferrable=False, initially deferred=False, validated=True |
| `approval_student_edit_summary_not_null` / `n` | `NOT NULL student_edit_summary` | deferrable=False, initially deferred=False, validated=True |
| `approval_submission_id_fkey` / `f` | `FOREIGN KEY (submission_id) REFERENCES attempt_media.submission(submission_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `approval_submission_id_not_null` / `n` | `NOT NULL submission_id` | deferrable=False, initially deferred=False, validated=True |
| `approval_submission_id_transcription_version_fkey` / `f` | `FOREIGN KEY (submission_id, transcription_version) REFERENCES attempt_media.transcription_candidate(submission_id, version)` | deferrable=False, initially deferred=False, validated=True |
| `approval_submission_id_transcription_version_key` / `u` | `UNIQUE (submission_id, transcription_version)` | deferrable=False, initially deferred=False, validated=True |
| `approval_transcription_version_not_null` / `n` | `NOT NULL transcription_version` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `attempt_media.step_assessment` / `step_assessment_submission_id_approved_version_fkey`: `FOREIGN KEY (submission_id, approved_version) REFERENCES attempt_media.approval(submission_id, approved_version)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `approval_learner_attempt_id_key`: `CREATE UNIQUE INDEX approval_learner_attempt_id_key ON attempt_media.approval USING btree (learner_attempt_id)`; valid=True, ready=True.
- `approval_pkey`: `CREATE UNIQUE INDEX approval_pkey ON attempt_media.approval USING btree (submission_id, approved_version)`; valid=True, ready=True.
- `approval_submission_id_transcription_version_key`: `CREATE UNIQUE INDEX approval_submission_id_transcription_version_key ON attempt_media.approval USING btree (submission_id, transcription_version)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `attempt_media.approved_step`

**Kind / use case:** view. View of steps associated with approved transcription versions.

**Owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql).

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/routers/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L504).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `approved_version` | `integer` | yes | `-` | `- / -` |
| `learner_attempt_id` | `uuid` | yes | `-` | `- / -` |
| `submission_id` | `uuid` | yes | `-` | `- / -` |
| `version` | `integer` | yes | `-` | `- / -` |
| `step_id` | `uuid` | yes | `-` | `- / -` |
| `ordinal` | `integer` | yes | `-` | `- / -` |
| `plain_text` | `text` | yes | `-` | `- / -` |
| `latex_text` | `text` | yes | `-` | `- / -` |
| `step_type` | `text` | yes | `-` | `- / -` |
| `confidence` | `double precision` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

No table constraints observed (views rely on underlying relations).

**Indexes** (including constraint-backed indexes and partial predicates):

No indexes observed.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

**Observed view definition:**

```sql
 SELECT a.approved_version,
    a.learner_attempt_id,
    s.submission_id,
    s.version,
    s.step_id,
    s.ordinal,
    s.plain_text,
    s.latex_text,
    s.step_type,
    s.confidence
   FROM attempt_media.approval a
     JOIN attempt_media.step_candidate s ON s.submission_id = a.submission_id AND s.version = a.transcription_version;
```

### `attempt_media.approved_step_evidence`

**Kind / use case:** view. View of approved steps and evidence-region links.

**Owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql).

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `approved_version` | `integer` | yes | `-` | `- / -` |
| `learner_attempt_id` | `uuid` | yes | `-` | `- / -` |
| `submission_id` | `uuid` | yes | `-` | `- / -` |
| `version` | `integer` | yes | `-` | `- / -` |
| `step_id` | `uuid` | yes | `-` | `- / -` |
| `region_id` | `uuid` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

No table constraints observed (views rely on underlying relations).

**Indexes** (including constraint-backed indexes and partial predicates):

No indexes observed.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

**Observed view definition:**

```sql
 SELECT a.approved_version,
    a.learner_attempt_id,
    e.submission_id,
    e.version,
    e.step_id,
    e.region_id
   FROM attempt_media.approval a
     JOIN attempt_media.step_candidate_evidence e ON e.submission_id = a.submission_id AND e.version = a.transcription_version;
```

### `attempt_media.event`

**Kind / use case:** table. Submission processing/edit/approval/assessment history.

**Migration owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql#L152); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/attempt_media.py#L56).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `submission_id` | `uuid` | no | `-` | `- / -` |
| `sequence` | `bigint` | no | `-` | `- / -` |
| `event_type` | `text` | no | `-` | `- / -` |
| `transcription_version` | `integer` | no | `-` | `- / -` |
| `approved_attempt_version` | `integer` | no | `-` | `- / -` |
| `payload` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `event_approved_attempt_version_not_null` / `n` | `NOT NULL approved_attempt_version` | deferrable=False, initially deferred=False, validated=True |
| `event_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `event_event_type_not_null` / `n` | `NOT NULL event_type` | deferrable=False, initially deferred=False, validated=True |
| `event_payload_not_null` / `n` | `NOT NULL payload` | deferrable=False, initially deferred=False, validated=True |
| `event_pkey` / `p` | `PRIMARY KEY (submission_id, sequence)` | deferrable=False, initially deferred=False, validated=True |
| `event_sequence_not_null` / `n` | `NOT NULL sequence` | deferrable=False, initially deferred=False, validated=True |
| `event_submission_id_fkey` / `f` | `FOREIGN KEY (submission_id) REFERENCES attempt_media.submission(submission_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `event_submission_id_not_null` / `n` | `NOT NULL submission_id` | deferrable=False, initially deferred=False, validated=True |
| `event_transcription_version_not_null` / `n` | `NOT NULL transcription_version` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `event_pkey`: `CREATE UNIQUE INDEX event_pkey ON attempt_media.event USING btree (submission_id, sequence)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `attempt_media.evidence_region`

**Kind / use case:** table. Normalized page/image evidence rectangles and reading order.

**Migration owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql#L41); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/attempt_media.py#L115).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `region_id` | `uuid` | no | `-` | `- / -` |
| `submission_id` | `uuid` | no | `-` | `- / -` |
| `media_asset_id` | `uuid` | no | `-` | `- / -` |
| `page_number` | `integer` | yes | `-` | `- / -` |
| `x_norm` | `double precision` | yes | `-` | `- / -` |
| `y_norm` | `double precision` | yes | `-` | `- / -` |
| `width_norm` | `double precision` | yes | `-` | `- / -` |
| `height_norm` | `double precision` | yes | `-` | `- / -` |
| `start_ms` | `integer` | yes | `-` | `- / -` |
| `end_ms` | `integer` | yes | `-` | `- / -` |
| `region_type` | `text` | no | `-` | `- / -` |
| `reading_order` | `integer` | no | `-` | `- / -` |
| `confidence` | `double precision` | no | `-` | `- / -` |
| `transcription_version` | `integer` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `evidence_region_check` / `c` | `CHECK (page_number IS NOT NULL AND x_norm IS NOT NULL AND y_norm IS NOT NULL AND width_norm IS NOT NULL AND height_norm IS NOT NULL AND (x_norm + width_norm) <= 1.000001::double precision AND (y_norm + height_norm) <= 1.000001::double precision AND start_ms IS NULL AND end_ms IS NULL OR start_ms IS NOT NULL AND end_ms > start_ms AND page_number IS NULL AND x_norm IS NULL AND y_norm IS NULL AND width_norm IS NULL AND height_norm IS NULL)` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_confidence_check` / `c` | `CHECK (confidence >= 0::double precision AND confidence <= 1::double precision)` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_confidence_not_null` / `n` | `NOT NULL confidence` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_height_norm_check` / `c` | `CHECK (height_norm > 0::double precision AND height_norm <= 1::double precision)` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_media_asset_id_fkey` / `f` | `FOREIGN KEY (media_asset_id) REFERENCES attempt_media.media_asset(media_asset_id)` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_media_asset_id_not_null` / `n` | `NOT NULL media_asset_id` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_page_number_check` / `c` | `CHECK (page_number >= 1 AND page_number <= 10)` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_pkey` / `p` | `PRIMARY KEY (region_id)` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_reading_order_check` / `c` | `CHECK (reading_order >= 0)` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_reading_order_not_null` / `n` | `NOT NULL reading_order` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_region_id_not_null` / `n` | `NOT NULL region_id` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_region_type_not_null` / `n` | `NOT NULL region_type` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_start_ms_check` / `c` | `CHECK (start_ms >= 0)` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_submission_id_fkey` / `f` | `FOREIGN KEY (submission_id) REFERENCES attempt_media.submission(submission_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_submission_id_not_null` / `n` | `NOT NULL submission_id` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_transcription_version_not_null` / `n` | `NOT NULL transcription_version` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_width_norm_check` / `c` | `CHECK (width_norm > 0::double precision AND width_norm <= 1::double precision)` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_x_norm_check` / `c` | `CHECK (x_norm >= 0::double precision AND x_norm <= 1::double precision)` | deferrable=False, initially deferred=False, validated=True |
| `evidence_region_y_norm_check` / `c` | `CHECK (y_norm >= 0::double precision AND y_norm <= 1::double precision)` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `attempt_media.step_candidate_evidence` / `step_candidate_evidence_region_id_fkey`: `FOREIGN KEY (region_id) REFERENCES attempt_media.evidence_region(region_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `evidence_region_pkey`: `CREATE UNIQUE INDEX evidence_region_pkey ON attempt_media.evidence_region USING btree (region_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `attempt_media.media_asset`

**Kind / use case:** table. Private image/PDF/audio/video metadata, object locator and integrity.

**Migration owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql#L22); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/attempt_media.py#L101); [mathbank-rest/src/mathbank_rest/routers/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L107).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `media_asset_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `submission_id` | `uuid` | no | `-` | `- / -` |
| `role` | `text` | no | `'ORIGINAL'::text` | `- / -` |
| `parent_asset_id` | `uuid` | yes | `-` | `- / -` |
| `asset_type` | `text` | no | `-` | `- / -` |
| `object_key` | `text` | no | `-` | `- / -` |
| `mime_type` | `text` | no | `-` | `- / -` |
| `sha256` | `text` | no | `-` | `- / -` |
| `size_bytes` | `bigint` | no | `-` | `- / -` |
| `page_count` | `integer` | yes | `-` | `- / -` |
| `duration_ms` | `integer` | yes | `-` | `- / -` |
| `timestamp_ms` | `integer` | yes | `-` | `- / -` |
| `retention_class` | `text` | no | `'RAW_MEDIA'::text` | `- / -` |
| `purged_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `media_asset_asset_type_check` / `c` | `CHECK (asset_type = ANY (ARRAY['IMAGE'::text, 'PDF'::text, 'AUDIO'::text, 'VIDEO'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_asset_type_not_null` / `n` | `NOT NULL asset_type` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_duration_ms_check` / `c` | `CHECK (duration_ms >= 1 AND duration_ms <= 120000)` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_media_asset_id_not_null` / `n` | `NOT NULL media_asset_id` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_mime_type_not_null` / `n` | `NOT NULL mime_type` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_object_key_not_null` / `n` | `NOT NULL object_key` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_page_count_check` / `c` | `CHECK (page_count >= 1 AND page_count <= 10)` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_parent_asset_id_fkey` / `f` | `FOREIGN KEY (parent_asset_id) REFERENCES attempt_media.media_asset(media_asset_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_pkey` / `p` | `PRIMARY KEY (media_asset_id)` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_retention_class_not_null` / `n` | `NOT NULL retention_class` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_role_check` / `c` | `CHECK (role = ANY (ARRAY['ORIGINAL'::text, 'PAGE'::text, 'KEYFRAME'::text, 'AUDIO'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_role_not_null` / `n` | `NOT NULL role` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_sha256_not_null` / `n` | `NOT NULL sha256` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_size_bytes_check` / `c` | `CHECK (size_bytes > 0)` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_size_bytes_not_null` / `n` | `NOT NULL size_bytes` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_submission_id_fkey` / `f` | `FOREIGN KEY (submission_id) REFERENCES attempt_media.submission(submission_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_submission_id_not_null` / `n` | `NOT NULL submission_id` | deferrable=False, initially deferred=False, validated=True |
| `media_asset_timestamp_ms_check` / `c` | `CHECK (timestamp_ms >= 0)` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `attempt_media.evidence_region` / `evidence_region_media_asset_id_fkey`: `FOREIGN KEY (media_asset_id) REFERENCES attempt_media.media_asset(media_asset_id)`.
- `attempt_media.media_asset` / `media_asset_parent_asset_id_fkey`: `FOREIGN KEY (parent_asset_id) REFERENCES attempt_media.media_asset(media_asset_id) ON DELETE SET NULL`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `asset_submission_idx`: `CREATE INDEX asset_submission_idx ON attempt_media.media_asset USING btree (submission_id)`; valid=True, ready=True.
- `media_asset_pkey`: `CREATE UNIQUE INDEX media_asset_pkey ON attempt_media.media_asset USING btree (media_asset_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `attempt_media.step_alignment`

**Kind / use case:** view. Compatibility view of step-assessment alignment records.

**Owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql).

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `assessment_id` | `uuid` | yes | `-` | `- / -` |
| `submission_id` | `uuid` | yes | `-` | `- / -` |
| `step_id` | `uuid` | yes | `-` | `- / -` |
| `transcription_version` | `integer` | yes | `-` | `- / -` |
| `approved_version` | `integer` | yes | `-` | `- / -` |
| `alignment_type` | `text` | yes | `-` | `- / -` |
| `canonical_solution_step_id` | `text` | yes | `-` | `- / -` |
| `confidence` | `double precision` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

No table constraints observed (views rely on underlying relations).

**Indexes** (including constraint-backed indexes and partial predicates):

No indexes observed.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

**Observed view definition:**

```sql
 SELECT assessment_id,
    submission_id,
    step_id,
    transcription_version,
    approved_version,
    alignment_type,
    canonical_solution_step_id,
    confidence
   FROM attempt_media.step_assessment;
```

### `attempt_media.step_assessment`

**Kind / use case:** table. Reference-step alignment/verdict/evidence for approved learner work.

**Migration owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql#L119); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/attempt_media.py#L145); [mathbank-rest/src/mathbank_rest/routers/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L522).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `assessment_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `submission_id` | `uuid` | no | `-` | `- / -` |
| `transcription_version` | `integer` | no | `-` | `- / -` |
| `step_id` | `uuid` | no | `-` | `- / -` |
| `approved_version` | `integer` | no | `-` | `- / -` |
| `assessment_version` | `integer` | no | `-` | `- / -` |
| `source` | `text` | no | `-` | `- / -` |
| `actor_id` | `text` | no | `-` | `- / -` |
| `correctness` | `text` | no | `-` | `- / -` |
| `alignment_type` | `text` | no | `-` | `- / -` |
| `canonical_solution_step_id` | `text` | yes | `-` | `- / -` |
| `confidence` | `double precision` | no | `-` | `- / -` |
| `why` | `text` | no | `-` | `- / -` |
| `failure_mode` | `text` | no | `-` | `- / -` |
| `next_action` | `text` | no | `-` | `- / -` |
| `evidence_ids` | `jsonb` | no | `-` | `- / -` |
| `model_profile` | `text` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `step_assessment_actor_id_not_null` / `n` | `NOT NULL actor_id` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_alignment_type_not_null` / `n` | `NOT NULL alignment_type` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_approved_version_not_null` / `n` | `NOT NULL approved_version` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_assessment_id_not_null` / `n` | `NOT NULL assessment_id` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_assessment_version_check` / `c` | `CHECK (assessment_version > 0)` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_assessment_version_not_null` / `n` | `NOT NULL assessment_version` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_canonical_solution_step_id_fkey` / `f` | `FOREIGN KEY (canonical_solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_confidence_check` / `c` | `CHECK (confidence >= 0::double precision AND confidence <= 1::double precision)` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_confidence_not_null` / `n` | `NOT NULL confidence` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_correctness_check` / `c` | `CHECK (correctness = ANY (ARRAY['CORRECT'::text, 'PARTIALLY_CORRECT'::text, 'INCORRECT'::text, 'UNJUSTIFIED'::text, 'UNCERTAIN'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_correctness_not_null` / `n` | `NOT NULL correctness` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_evidence_ids_check` / `c` | `CHECK (jsonb_typeof(evidence_ids) = 'array'::text)` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_evidence_ids_not_null` / `n` | `NOT NULL evidence_ids` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_failure_mode_not_null` / `n` | `NOT NULL failure_mode` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_model_profile_not_null` / `n` | `NOT NULL model_profile` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_next_action_not_null` / `n` | `NOT NULL next_action` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_pkey` / `p` | `PRIMARY KEY (assessment_id)` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_source_check` / `c` | `CHECK (source = ANY (ARRAY['AI'::text, 'INSTRUCTOR'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_source_not_null` / `n` | `NOT NULL source` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_step_id_not_null` / `n` | `NOT NULL step_id` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_submission_id_approved_version_fkey` / `f` | `FOREIGN KEY (submission_id, approved_version) REFERENCES attempt_media.approval(submission_id, approved_version)` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_submission_id_not_null` / `n` | `NOT NULL submission_id` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_submission_id_transcription_version_step_i_fkey` / `f` | `FOREIGN KEY (submission_id, transcription_version, step_id) REFERENCES attempt_media.step_candidate(submission_id, version, step_id)` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_submission_id_transcription_version_step_id_key` / `u` | `UNIQUE (submission_id, transcription_version, step_id, assessment_version)` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_transcription_version_not_null` / `n` | `NOT NULL transcription_version` | deferrable=False, initially deferred=False, validated=True |
| `step_assessment_why_not_null` / `n` | `NOT NULL why` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `step_assessment_pkey`: `CREATE UNIQUE INDEX step_assessment_pkey ON attempt_media.step_assessment USING btree (assessment_id)`; valid=True, ready=True.
- `step_assessment_submission_id_transcription_version_step_id_key`: `CREATE UNIQUE INDEX step_assessment_submission_id_transcription_version_step_id_key ON attempt_media.step_assessment USING btree (submission_id, transcription_version, step_id, assessment_version)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `attempt_media.step_candidate`

**Kind / use case:** table. Candidate learner-written mathematical moves, not reference steps.

**Migration owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql#L75); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/attempt_media.py#L127).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `submission_id` | `uuid` | no | `-` | `- / -` |
| `version` | `integer` | no | `-` | `- / -` |
| `step_id` | `uuid` | no | `-` | `- / -` |
| `ordinal` | `integer` | no | `-` | `- / -` |
| `plain_text` | `text` | no | `-` | `- / -` |
| `latex_text` | `text` | no | `-` | `- / -` |
| `step_type` | `text` | no | `-` | `- / -` |
| `confidence` | `double precision` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `step_candidate_confidence_check` / `c` | `CHECK (confidence >= 0::double precision AND confidence <= 1::double precision)` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_confidence_not_null` / `n` | `NOT NULL confidence` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_latex_text_not_null` / `n` | `NOT NULL latex_text` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_ordinal_check` / `c` | `CHECK (ordinal > 0)` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_ordinal_not_null` / `n` | `NOT NULL ordinal` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_pkey` / `p` | `PRIMARY KEY (submission_id, version, step_id)` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_plain_text_not_null` / `n` | `NOT NULL plain_text` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_step_id_not_null` / `n` | `NOT NULL step_id` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_step_type_not_null` / `n` | `NOT NULL step_type` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_submission_id_not_null` / `n` | `NOT NULL submission_id` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_submission_id_version_fkey` / `f` | `FOREIGN KEY (submission_id, version) REFERENCES attempt_media.transcription_candidate(submission_id, version) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_submission_id_version_ordinal_key` / `u` | `UNIQUE (submission_id, version, ordinal)` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_version_not_null` / `n` | `NOT NULL version` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `attempt_media.step_assessment` / `step_assessment_submission_id_transcription_version_step_i_fkey`: `FOREIGN KEY (submission_id, transcription_version, step_id) REFERENCES attempt_media.step_candidate(submission_id, version, step_id)`.
- `attempt_media.step_candidate_evidence` / `step_candidate_evidence_submission_id_version_step_id_fkey`: `FOREIGN KEY (submission_id, version, step_id) REFERENCES attempt_media.step_candidate(submission_id, version, step_id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `step_candidate_pkey`: `CREATE UNIQUE INDEX step_candidate_pkey ON attempt_media.step_candidate USING btree (submission_id, version, step_id)`; valid=True, ready=True.
- `step_candidate_submission_id_version_ordinal_key`: `CREATE UNIQUE INDEX step_candidate_submission_id_version_ordinal_key ON attempt_media.step_candidate USING btree (submission_id, version, ordinal)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `attempt_media.step_candidate_evidence`

**Kind / use case:** table. Candidate-step-to-observed-region evidence links.

**Migration owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql#L88); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/attempt_media.py#L125).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `submission_id` | `uuid` | no | `-` | `- / -` |
| `version` | `integer` | no | `-` | `- / -` |
| `step_id` | `uuid` | no | `-` | `- / -` |
| `region_id` | `uuid` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `step_candidate_evidence_pkey` / `p` | `PRIMARY KEY (submission_id, version, step_id, region_id)` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_evidence_region_id_fkey` / `f` | `FOREIGN KEY (region_id) REFERENCES attempt_media.evidence_region(region_id)` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_evidence_region_id_not_null` / `n` | `NOT NULL region_id` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_evidence_step_id_not_null` / `n` | `NOT NULL step_id` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_evidence_submission_id_not_null` / `n` | `NOT NULL submission_id` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_evidence_submission_id_version_step_id_fkey` / `f` | `FOREIGN KEY (submission_id, version, step_id) REFERENCES attempt_media.step_candidate(submission_id, version, step_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `step_candidate_evidence_version_not_null` / `n` | `NOT NULL version` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `step_candidate_evidence_pkey`: `CREATE UNIQUE INDEX step_candidate_evidence_pkey ON attempt_media.step_candidate_evidence USING btree (submission_id, version, step_id, region_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `attempt_media.submission`

**Kind / use case:** table. Owned uploaded/pasted learner-work session and transcription/approval versions.

**Migration owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql#L6); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/attempt_media.py#L22); [mathbank-rest/src/mathbank_rest/routers/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L56).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `submission_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `student_id` | `uuid` | no | `-` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `status` | `text` | no | `'RECEIVED'::text` | `- / -` |
| `transcription_version` | `integer` | no | `1` | `- / -` |
| `approved_version` | `integer` | no | `0` | `- / -` |
| `last_sequence` | `bigint` | no | `0` | `- / -` |
| `error_code` | `text` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `submission_approved_version_check` / `c` | `CHECK (approved_version >= 0)` | deferrable=False, initially deferred=False, validated=True |
| `submission_approved_version_not_null` / `n` | `NOT NULL approved_version` | deferrable=False, initially deferred=False, validated=True |
| `submission_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `submission_last_sequence_not_null` / `n` | `NOT NULL last_sequence` | deferrable=False, initially deferred=False, validated=True |
| `submission_pkey` / `p` | `PRIMARY KEY (submission_id)` | deferrable=False, initially deferred=False, validated=True |
| `submission_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `submission_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `submission_status_check` / `c` | `CHECK (status = ANY (ARRAY['RECEIVED'::text, 'MEDIA_NORMALIZED'::text, 'TRANSCRIBING'::text, 'TRANSCRIPTION_READY'::text, 'STUDENT_REVIEWING'::text, 'APPROVED'::text, 'ALIGNING'::text, 'CRITIQUING'::text, 'VISUAL_GROUNDING'::text, 'READY'::text, 'FAILED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `submission_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `submission_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `submission_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |
| `submission_submission_id_not_null` / `n` | `NOT NULL submission_id` | deferrable=False, initially deferred=False, validated=True |
| `submission_transcription_version_check` / `c` | `CHECK (transcription_version > 0)` | deferrable=False, initially deferred=False, validated=True |
| `submission_transcription_version_not_null` / `n` | `NOT NULL transcription_version` | deferrable=False, initially deferred=False, validated=True |
| `submission_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `attempt_media.approval` / `approval_submission_id_fkey`: `FOREIGN KEY (submission_id) REFERENCES attempt_media.submission(submission_id) ON DELETE CASCADE`.
- `attempt_media.event` / `event_submission_id_fkey`: `FOREIGN KEY (submission_id) REFERENCES attempt_media.submission(submission_id) ON DELETE CASCADE`.
- `attempt_media.evidence_region` / `evidence_region_submission_id_fkey`: `FOREIGN KEY (submission_id) REFERENCES attempt_media.submission(submission_id) ON DELETE CASCADE`.
- `attempt_media.media_asset` / `media_asset_submission_id_fkey`: `FOREIGN KEY (submission_id) REFERENCES attempt_media.submission(submission_id) ON DELETE CASCADE`.
- `attempt_media.transcription_candidate` / `transcription_candidate_submission_id_fkey`: `FOREIGN KEY (submission_id) REFERENCES attempt_media.submission(submission_id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `submission_owner_idx`: `CREATE INDEX submission_owner_idx ON attempt_media.submission USING btree (student_id, created_at DESC)`; valid=True, ready=True.
- `submission_pkey`: `CREATE UNIQUE INDEX submission_pkey ON attempt_media.submission USING btree (submission_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `attempt_media.transcription_candidate`

**Kind / use case:** table. Candidate transcription output for staff/learner review.

**Migration owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql#L66); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/attempt_media.py#L238).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `submission_id` | `uuid` | no | `-` | `- / -` |
| `version` | `integer` | no | `-` | `- / -` |
| `source` | `text` | no | `-` | `- / -` |
| `machine_output` | `jsonb` | yes | `-` | `- / -` |
| `model_profile` | `text` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `transcription_candidate_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `transcription_candidate_pkey` / `p` | `PRIMARY KEY (submission_id, version)` | deferrable=False, initially deferred=False, validated=True |
| `transcription_candidate_source_check` / `c` | `CHECK (source = ANY (ARRAY['MACHINE'::text, 'STUDENT'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `transcription_candidate_source_not_null` / `n` | `NOT NULL source` | deferrable=False, initially deferred=False, validated=True |
| `transcription_candidate_submission_id_fkey` / `f` | `FOREIGN KEY (submission_id) REFERENCES attempt_media.submission(submission_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `transcription_candidate_submission_id_not_null` / `n` | `NOT NULL submission_id` | deferrable=False, initially deferred=False, validated=True |
| `transcription_candidate_version_not_null` / `n` | `NOT NULL version` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `attempt_media.approval` / `approval_submission_id_transcription_version_fkey`: `FOREIGN KEY (submission_id, transcription_version) REFERENCES attempt_media.transcription_candidate(submission_id, version)`.
- `attempt_media.step_candidate` / `step_candidate_submission_id_version_fkey`: `FOREIGN KEY (submission_id, version) REFERENCES attempt_media.transcription_candidate(submission_id, version) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `transcription_candidate_pkey`: `CREATE UNIQUE INDEX transcription_candidate_pkey ON attempt_media.transcription_candidate USING btree (submission_id, version)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `attempt_media.visual_explanation`

**Kind / use case:** view. Compatibility view of visual explanation evidence.

**Owner:** [021_attempt_media.sql](../../../mathbank-db/sql/021_attempt_media.sql).

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `assessment_id` | `uuid` | yes | `-` | `- / -` |
| `submission_id` | `uuid` | yes | `-` | `- / -` |
| `step_id` | `uuid` | yes | `-` | `- / -` |
| `transcription_version` | `integer` | yes | `-` | `- / -` |
| `approved_version` | `integer` | yes | `-` | `- / -` |
| `evidence_ids` | `jsonb` | yes | `-` | `- / -` |
| `why` | `text` | yes | `-` | `- / -` |
| `next_action` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

No table constraints observed (views rely on underlying relations).

**Indexes** (including constraint-backed indexes and partial predicates):

No indexes observed.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

**Observed view definition:**

```sql
 SELECT assessment_id,
    submission_id,
    step_id,
    transcription_version,
    approved_version,
    evidence_ids,
    why,
    next_action
   FROM attempt_media.step_assessment;
```

