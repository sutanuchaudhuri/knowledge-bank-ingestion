# PostgreSQL `activity` schema

**Role:** Live activities and responses. Definitions, running activity instances and learner responses.

**Access family:** Live activity start/respond/close/result routes; `/v1/live/*`, mathbank-live classroom widgets.

**Evidence:** live catalog metadata at 2026-10-08T01:57:54.421824+00:00; source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `activity.definition`

**Kind / use case:** table. Reusable poll/quiz/exercise definition and answer/reveal policy.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L261); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L391).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `activity_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `activity_type` | `text` | no | `-` | `- / -` |
| `prompt` | `text` | no | `-` | `- / -` |
| `options` | `jsonb` | no | `'[]'::jsonb` | `- / -` |
| `correctness_policy` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `target_skill` | `text` | yes | `-` | `- / -` |
| `estimated_seconds` | `integer` | no | `60` | `- / -` |
| `source_type` | `text` | no | `-` | `- / -` |
| `source_lineage` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `persistence_mode` | `text` | no | `'SESSION'::text` | `- / -` |
| `created_by` | `text` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `definition_activity_id_not_null` / `n` | `NOT NULL activity_id` | deferrable=False, initially deferred=False, validated=True |
| `definition_activity_type_check` / `c` | `CHECK (activity_type = ANY (ARRAY['MCQ'::text, 'MULTISELECT'::text, 'NUMERIC'::text, 'SHORT_RESPONSE'::text, 'SUBPROBLEM'::text, 'STEP_ORDERING'::text, 'ERROR_DIAGNOSIS'::text, 'CONFIDENCE_CHECK'::text, 'LIVE_POLL'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `definition_activity_type_not_null` / `n` | `NOT NULL activity_type` | deferrable=False, initially deferred=False, validated=True |
| `definition_correctness_policy_not_null` / `n` | `NOT NULL correctness_policy` | deferrable=False, initially deferred=False, validated=True |
| `definition_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `definition_created_by_not_null` / `n` | `NOT NULL created_by` | deferrable=False, initially deferred=False, validated=True |
| `definition_estimated_seconds_check` / `c` | `CHECK (estimated_seconds > 0)` | deferrable=False, initially deferred=False, validated=True |
| `definition_estimated_seconds_not_null` / `n` | `NOT NULL estimated_seconds` | deferrable=False, initially deferred=False, validated=True |
| `definition_options_check` / `c` | `CHECK (jsonb_typeof(options) = 'array'::text)` | deferrable=False, initially deferred=False, validated=True |
| `definition_options_not_null` / `n` | `NOT NULL options` | deferrable=False, initially deferred=False, validated=True |
| `definition_persistence_mode_check` / `c` | `CHECK (persistence_mode = ANY (ARRAY['STATIC'::text, 'SESSION'::text, 'EPHEMERAL'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `definition_persistence_mode_not_null` / `n` | `NOT NULL persistence_mode` | deferrable=False, initially deferred=False, validated=True |
| `definition_pkey` / `p` | `PRIMARY KEY (activity_id)` | deferrable=False, initially deferred=False, validated=True |
| `definition_prompt_not_null` / `n` | `NOT NULL prompt` | deferrable=False, initially deferred=False, validated=True |
| `definition_source_lineage_not_null` / `n` | `NOT NULL source_lineage` | deferrable=False, initially deferred=False, validated=True |
| `definition_source_type_check` / `c` | `CHECK (source_type = ANY (ARRAY['PRECOMPILED'::text, 'CORPUS_DERIVED'::text, 'LIVE_AGENT_CREATED'::text, 'INSTRUCTOR_CREATED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `definition_source_type_not_null` / `n` | `NOT NULL source_type` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `activity.instance` / `instance_activity_id_fkey`: `FOREIGN KEY (activity_id) REFERENCES activity.definition(activity_id) ON DELETE RESTRICT`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `definition_pkey`: `CREATE UNIQUE INDEX definition_pkey ON activity.definition USING btree (activity_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `activity.instance`

**Kind / use case:** table. Live occurrence of an activity under a topic/session.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L279); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L425).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `activity_instance_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `live_session_id` | `uuid` | no | `-` | `- / -` |
| `activity_id` | `uuid` | no | `-` | `- / -` |
| `status` | `text` | no | `'OPEN'::text` | `- / -` |
| `anonymous` | `boolean` | no | `true` | `- / -` |
| `opened_by` | `text` | no | `-` | `- / -` |
| `opened_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `closes_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `closed_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `instance_activity_id_fkey` / `f` | `FOREIGN KEY (activity_id) REFERENCES activity.definition(activity_id) ON DELETE RESTRICT` | deferrable=False, initially deferred=False, validated=True |
| `instance_activity_id_not_null` / `n` | `NOT NULL activity_id` | deferrable=False, initially deferred=False, validated=True |
| `instance_activity_instance_id_not_null` / `n` | `NOT NULL activity_instance_id` | deferrable=False, initially deferred=False, validated=True |
| `instance_anonymous_not_null` / `n` | `NOT NULL anonymous` | deferrable=False, initially deferred=False, validated=True |
| `instance_live_session_id_fkey` / `f` | `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `instance_live_session_id_not_null` / `n` | `NOT NULL live_session_id` | deferrable=False, initially deferred=False, validated=True |
| `instance_opened_at_not_null` / `n` | `NOT NULL opened_at` | deferrable=False, initially deferred=False, validated=True |
| `instance_opened_by_not_null` / `n` | `NOT NULL opened_by` | deferrable=False, initially deferred=False, validated=True |
| `instance_pkey` / `p` | `PRIMARY KEY (activity_instance_id)` | deferrable=False, initially deferred=False, validated=True |
| `instance_status_check` / `c` | `CHECK (status = ANY (ARRAY['OPEN'::text, 'CLOSED'::text, 'REVEALED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `instance_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `activity.response` / `response_activity_instance_id_fkey`: `FOREIGN KEY (activity_instance_id) REFERENCES activity.instance(activity_instance_id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `activity_instance_session_idx`: `CREATE INDEX activity_instance_session_idx ON activity.instance USING btree (live_session_id, opened_at DESC)`; valid=True, ready=True.
- `instance_pkey`: `CREATE UNIQUE INDEX instance_pkey ON activity.instance USING btree (activity_instance_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `activity.response`

**Kind / use case:** table. Participant submitted activity response and result metadata.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L293); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L431); [mathbank-live/lib/events.mjs](../../../mathbank-live/lib/events.mjs#L33).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `response_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `activity_instance_id` | `uuid` | no | `-` | `- / -` |
| `participant_id` | `text` | no | `-` | `- / -` |
| `response` | `jsonb` | no | `-` | `- / -` |
| `confidence` | `smallint` | yes | `-` | `- / -` |
| `is_correct` | `boolean` | yes | `-` | `- / -` |
| `client_command_id` | `text` | yes | `-` | `- / -` |
| `submitted_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `response_activity_instance_id_fkey` / `f` | `FOREIGN KEY (activity_instance_id) REFERENCES activity.instance(activity_instance_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `response_activity_instance_id_not_null` / `n` | `NOT NULL activity_instance_id` | deferrable=False, initially deferred=False, validated=True |
| `response_activity_instance_id_participant_id_key` / `u` | `UNIQUE (activity_instance_id, participant_id)` | deferrable=False, initially deferred=False, validated=True |
| `response_confidence_check` / `c` | `CHECK (confidence IS NULL OR confidence >= 1 AND confidence <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `response_participant_id_not_null` / `n` | `NOT NULL participant_id` | deferrable=False, initially deferred=False, validated=True |
| `response_pkey` / `p` | `PRIMARY KEY (response_id)` | deferrable=False, initially deferred=False, validated=True |
| `response_response_id_not_null` / `n` | `NOT NULL response_id` | deferrable=False, initially deferred=False, validated=True |
| `response_response_not_null` / `n` | `NOT NULL response` | deferrable=False, initially deferred=False, validated=True |
| `response_submitted_at_not_null` / `n` | `NOT NULL submitted_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `response_activity_instance_id_participant_id_key`: `CREATE UNIQUE INDEX response_activity_instance_id_participant_id_key ON activity.response USING btree (activity_instance_id, participant_id)`; valid=True, ready=True.
- `response_pkey`: `CREATE UNIQUE INDEX response_pkey ON activity.response USING btree (response_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

