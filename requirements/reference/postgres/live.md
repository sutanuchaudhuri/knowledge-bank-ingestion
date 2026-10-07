# PostgreSQL `live` schema

**Role:** Live teaching orchestration. Room sessions, participants, event/replay state, topic timing, recommendations and takeover.

**Access family:** `/v1/live/*` through the mathbank-live socket gateway; staff commands and session-scoped access.

**Evidence:** live catalog metadata at 2026-10-07T13:40:57.292324+00:00; source `375f3743357cef814c50e3c8752f7f4ce2d6ebe5`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `live.command_receipt`

**Kind / use case:** table. Idempotent room command receipt/result.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L205); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L874).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `live_session_id` | `uuid` | no | `-` | `- / -` |
| `client_command_id` | `text` | no | `-` | `- / -` |
| `command_type` | `text` | no | `-` | `- / -` |
| `actor_type` | `text` | no | `-` | `- / -` |
| `actor_id` | `text` | yes | `-` | `- / -` |
| `status` | `text` | no | `-` | `- / -` |
| `result` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `command_receipt_actor_type_not_null` / `n` | `NOT NULL actor_type` | deferrable=False, initially deferred=False, validated=True |
| `command_receipt_client_command_id_not_null` / `n` | `NOT NULL client_command_id` | deferrable=False, initially deferred=False, validated=True |
| `command_receipt_command_type_not_null` / `n` | `NOT NULL command_type` | deferrable=False, initially deferred=False, validated=True |
| `command_receipt_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `command_receipt_live_session_id_fkey` / `f` | `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `command_receipt_live_session_id_not_null` / `n` | `NOT NULL live_session_id` | deferrable=False, initially deferred=False, validated=True |
| `command_receipt_pkey` / `p` | `PRIMARY KEY (live_session_id, client_command_id)` | deferrable=False, initially deferred=False, validated=True |
| `command_receipt_result_not_null` / `n` | `NOT NULL result` | deferrable=False, initially deferred=False, validated=True |
| `command_receipt_status_check` / `c` | `CHECK (status = ANY (ARRAY['ACCEPTED'::text, 'REJECTED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `command_receipt_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `command_receipt_pkey`: `CREATE UNIQUE INDEX command_receipt_pkey ON live.command_receipt USING btree (live_session_id, client_command_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `live.participant`

**Kind / use case:** table. Session member identity/role/status.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L162); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L189).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `live_session_id` | `uuid` | no | `-` | `- / -` |
| `participant_id` | `text` | no | `-` | `- / -` |
| `role` | `text` | no | `-` | `- / -` |
| `student_id` | `uuid` | yes | `-` | `- / -` |
| `display_name` | `text` | no | `-` | `- / -` |
| `group_id` | `text` | yes | `-` | `- / -` |
| `control_mode` | `text` | no | `'AI_ACTIVE'::text` | `- / -` |
| `confused` | `boolean` | no | `false` | `- / -` |
| `joined_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `last_seen_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `participant_confused_not_null` / `n` | `NOT NULL confused` | deferrable=False, initially deferred=False, validated=True |
| `participant_control_mode_check` / `c` | `CHECK (control_mode = ANY (ARRAY['AI_ACTIVE'::text, 'INSTRUCTOR_ACTIVE'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `participant_control_mode_not_null` / `n` | `NOT NULL control_mode` | deferrable=False, initially deferred=False, validated=True |
| `participant_display_name_not_null` / `n` | `NOT NULL display_name` | deferrable=False, initially deferred=False, validated=True |
| `participant_joined_at_not_null` / `n` | `NOT NULL joined_at` | deferrable=False, initially deferred=False, validated=True |
| `participant_last_seen_at_not_null` / `n` | `NOT NULL last_seen_at` | deferrable=False, initially deferred=False, validated=True |
| `participant_live_session_id_fkey` / `f` | `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `participant_live_session_id_not_null` / `n` | `NOT NULL live_session_id` | deferrable=False, initially deferred=False, validated=True |
| `participant_participant_id_not_null` / `n` | `NOT NULL participant_id` | deferrable=False, initially deferred=False, validated=True |
| `participant_pkey` / `p` | `PRIMARY KEY (live_session_id, participant_id)` | deferrable=False, initially deferred=False, validated=True |
| `participant_role_check` / `c` | `CHECK (role = ANY (ARRAY['STUDENT'::text, 'INSTRUCTOR'::text, 'OBSERVER'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `participant_role_not_null` / `n` | `NOT NULL role` | deferrable=False, initially deferred=False, validated=True |
| `participant_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `participant_pkey`: `CREATE UNIQUE INDEX participant_pkey ON live.participant USING btree (live_session_id, participant_id)`; valid=True, ready=True.
- `participant_student_idx`: `CREATE INDEX participant_student_idx ON live.participant USING btree (student_id) WHERE (student_id IS NOT NULL)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `live.recommendation`

**Kind / use case:** table. Proposed teaching action with explicit apply/reject.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L232); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L6).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `recommendation_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `live_session_id` | `uuid` | no | `-` | `- / -` |
| `source` | `text` | no | `-` | `- / -` |
| `action` | `jsonb` | no | `-` | `- / -` |
| `rationale` | `text` | yes | `-` | `- / -` |
| `based_on_version` | `bigint` | no | `-` | `- / -` |
| `status` | `text` | no | `'PROPOSED'::text` | `- / -` |
| `decided_by` | `text` | yes | `-` | `- / -` |
| `decided_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `recommendation_action_not_null` / `n` | `NOT NULL action` | deferrable=False, initially deferred=False, validated=True |
| `recommendation_based_on_version_not_null` / `n` | `NOT NULL based_on_version` | deferrable=False, initially deferred=False, validated=True |
| `recommendation_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `recommendation_live_session_id_fkey` / `f` | `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `recommendation_live_session_id_not_null` / `n` | `NOT NULL live_session_id` | deferrable=False, initially deferred=False, validated=True |
| `recommendation_pkey` / `p` | `PRIMARY KEY (recommendation_id)` | deferrable=False, initially deferred=False, validated=True |
| `recommendation_recommendation_id_not_null` / `n` | `NOT NULL recommendation_id` | deferrable=False, initially deferred=False, validated=True |
| `recommendation_source_check` / `c` | `CHECK (source = ANY (ARRAY['AI_TUTOR'::text, 'INSTRUCTOR_NL'::text, 'TIME_ORCHESTRATOR'::text, 'POLL_BRANCH'::text, 'VISUAL_AGENT'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `recommendation_source_not_null` / `n` | `NOT NULL source` | deferrable=False, initially deferred=False, validated=True |
| `recommendation_status_check` / `c` | `CHECK (status = ANY (ARRAY['PROPOSED'::text, 'ACCEPTED'::text, 'REJECTED'::text, 'STALE'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `recommendation_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `recommendation_pkey`: `CREATE UNIQUE INDEX recommendation_pkey ON live.recommendation USING btree (recommendation_id)`; valid=True, ready=True.
- `recommendation_session_idx`: `CREATE INDEX recommendation_session_idx ON live.recommendation USING btree (live_session_id, created_at DESC)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `live.session`

**Kind / use case:** table. Live room lifecycle and selected published presentation plan.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L128); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L64).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `live_session_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `plan_id` | `uuid` | yes | `-` | `- / -` |
| `title` | `text` | no | `-` | `- / -` |
| `join_code` | `text` | no | `-` | `- / -` |
| `status` | `text` | no | `'SCHEDULED'::text` | `- / -` |
| `control_mode` | `text` | no | `'AI_ACTIVE'::text` | `- / -` |
| `controller` | `text` | yes | `-` | `- / -` |
| `agent_locked` | `boolean` | no | `false` | `- / -` |
| `state_version` | `bigint` | no | `1` | `- / -` |
| `last_sequence` | `bigint` | no | `0` | `- / -` |
| `current_topic_index` | `integer` | no | `0` | `- / -` |
| `current_scene_index` | `integer` | no | `0` | `- / -` |
| `course_limit_seconds` | `integer` | no | `-` | `- / -` |
| `interaction_buffer_seconds` | `integer` | no | `0` | `- / -` |
| `hard_limit` | `boolean` | no | `false` | `- / -` |
| `extension_seconds` | `integer` | no | `0` | `- / -` |
| `started_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `paused_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `paused_total_seconds` | `integer` | no | `0` | `- / -` |
| `topic_started_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `completed_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `stage` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `created_by` | `text` | no | `'admin'::text` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `topics` | `jsonb` | no | `'[]'::jsonb` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `session_agent_locked_not_null` / `n` | `NOT NULL agent_locked` | deferrable=False, initially deferred=False, validated=True |
| `session_control_mode_check` / `c` | `CHECK (control_mode = ANY (ARRAY['AI_ACTIVE'::text, 'INSTRUCTOR_ACTIVE'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `session_control_mode_not_null` / `n` | `NOT NULL control_mode` | deferrable=False, initially deferred=False, validated=True |
| `session_course_limit_seconds_check` / `c` | `CHECK (course_limit_seconds > 0)` | deferrable=False, initially deferred=False, validated=True |
| `session_course_limit_seconds_not_null` / `n` | `NOT NULL course_limit_seconds` | deferrable=False, initially deferred=False, validated=True |
| `session_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `session_created_by_not_null` / `n` | `NOT NULL created_by` | deferrable=False, initially deferred=False, validated=True |
| `session_current_scene_index_not_null` / `n` | `NOT NULL current_scene_index` | deferrable=False, initially deferred=False, validated=True |
| `session_current_topic_index_not_null` / `n` | `NOT NULL current_topic_index` | deferrable=False, initially deferred=False, validated=True |
| `session_extension_seconds_not_null` / `n` | `NOT NULL extension_seconds` | deferrable=False, initially deferred=False, validated=True |
| `session_hard_limit_not_null` / `n` | `NOT NULL hard_limit` | deferrable=False, initially deferred=False, validated=True |
| `session_interaction_buffer_seconds_not_null` / `n` | `NOT NULL interaction_buffer_seconds` | deferrable=False, initially deferred=False, validated=True |
| `session_join_code_key` / `u` | `UNIQUE (join_code)` | deferrable=False, initially deferred=False, validated=True |
| `session_join_code_not_null` / `n` | `NOT NULL join_code` | deferrable=False, initially deferred=False, validated=True |
| `session_last_sequence_check` / `c` | `CHECK (last_sequence >= 0)` | deferrable=False, initially deferred=False, validated=True |
| `session_last_sequence_not_null` / `n` | `NOT NULL last_sequence` | deferrable=False, initially deferred=False, validated=True |
| `session_live_session_id_not_null` / `n` | `NOT NULL live_session_id` | deferrable=False, initially deferred=False, validated=True |
| `session_paused_total_seconds_not_null` / `n` | `NOT NULL paused_total_seconds` | deferrable=False, initially deferred=False, validated=True |
| `session_pkey` / `p` | `PRIMARY KEY (live_session_id)` | deferrable=False, initially deferred=False, validated=True |
| `session_plan_id_fkey` / `f` | `FOREIGN KEY (plan_id) REFERENCES authoring.presentation_plan(plan_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `session_stage_not_null` / `n` | `NOT NULL stage` | deferrable=False, initially deferred=False, validated=True |
| `session_state_version_check` / `c` | `CHECK (state_version >= 1)` | deferrable=False, initially deferred=False, validated=True |
| `session_state_version_not_null` / `n` | `NOT NULL state_version` | deferrable=False, initially deferred=False, validated=True |
| `session_status_check` / `c` | `CHECK (status = ANY (ARRAY['SCHEDULED'::text, 'ACTIVE'::text, 'PAUSED'::text, 'COMPLETED'::text, 'CANCELLED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `session_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `session_title_not_null` / `n` | `NOT NULL title` | deferrable=False, initially deferred=False, validated=True |
| `session_topics_not_null` / `n` | `NOT NULL topics` | deferrable=False, initially deferred=False, validated=True |
| `session_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `activity.instance` / `instance_live_session_id_fkey`: `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE`.
- `live.command_receipt` / `command_receipt_live_session_id_fkey`: `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE`.
- `live.participant` / `participant_live_session_id_fkey`: `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE`.
- `live.recommendation` / `recommendation_live_session_id_fkey`: `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE`.
- `live.session_event` / `session_event_live_session_id_fkey`: `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE`.
- `live.takeover` / `takeover_live_session_id_fkey`: `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE`.
- `live.topic_run` / `topic_run_live_session_id_fkey`: `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE`.
- `visual.widget_spec` / `widget_spec_live_session_id_fkey`: `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE`.
- `visual.widget_state` / `widget_state_live_session_id_fkey`: `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `session_join_code_key`: `CREATE UNIQUE INDEX session_join_code_key ON live.session USING btree (join_code)`; valid=True, ready=True.
- `session_pkey`: `CREATE UNIQUE INDEX session_pkey ON live.session USING btree (live_session_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `live.session_event`

**Kind / use case:** table. Append-only sequenced live commands/events used for replay.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L178); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L4); [mathbank-live/lib/gateway.mjs](../../../mathbank-live/lib/gateway.mjs#L5).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `live_session_id` | `uuid` | no | `-` | `- / -` |
| `sequence` | `bigint` | no | `-` | `- / -` |
| `event_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `event_type` | `text` | no | `-` | `- / -` |
| `session_version` | `bigint` | no | `-` | `- / -` |
| `correlation_id` | `text` | yes | `-` | `- / -` |
| `causation_id` | `text` | yes | `-` | `- / -` |
| `actor_type` | `text` | no | `-` | `- / -` |
| `actor_id` | `text` | yes | `-` | `- / -` |
| `audience` | `text` | no | `'SESSION'::text` | `- / -` |
| `audience_id` | `text` | yes | `-` | `- / -` |
| `payload` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `clock_timestamp()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `session_event_actor_type_check` / `c` | `CHECK (actor_type = ANY (ARRAY['STUDENT'::text, 'INSTRUCTOR'::text, 'ADMIN'::text, 'AI_TUTOR'::text, 'SYSTEM'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `session_event_actor_type_not_null` / `n` | `NOT NULL actor_type` | deferrable=False, initially deferred=False, validated=True |
| `session_event_audience_check` / `c` | `CHECK (audience = ANY (ARRAY['SESSION'::text, 'STUDENT'::text, 'INSTRUCTOR'::text, 'GROUP'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `session_event_audience_not_null` / `n` | `NOT NULL audience` | deferrable=False, initially deferred=False, validated=True |
| `session_event_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `session_event_event_id_key` / `u` | `UNIQUE (event_id)` | deferrable=False, initially deferred=False, validated=True |
| `session_event_event_id_not_null` / `n` | `NOT NULL event_id` | deferrable=False, initially deferred=False, validated=True |
| `session_event_event_type_not_null` / `n` | `NOT NULL event_type` | deferrable=False, initially deferred=False, validated=True |
| `session_event_live_session_id_fkey` / `f` | `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `session_event_live_session_id_not_null` / `n` | `NOT NULL live_session_id` | deferrable=False, initially deferred=False, validated=True |
| `session_event_payload_not_null` / `n` | `NOT NULL payload` | deferrable=False, initially deferred=False, validated=True |
| `session_event_pkey` / `p` | `PRIMARY KEY (live_session_id, sequence)` | deferrable=False, initially deferred=False, validated=True |
| `session_event_sequence_check` / `c` | `CHECK (sequence >= 1)` | deferrable=False, initially deferred=False, validated=True |
| `session_event_sequence_not_null` / `n` | `NOT NULL sequence` | deferrable=False, initially deferred=False, validated=True |
| `session_event_session_version_not_null` / `n` | `NOT NULL session_version` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `session_event_event_id_key`: `CREATE UNIQUE INDEX session_event_event_id_key ON live.session_event USING btree (event_id)`; valid=True, ready=True.
- `session_event_pkey`: `CREATE UNIQUE INDEX session_event_pkey ON live.session_event USING btree (live_session_id, sequence)`; valid=True, ready=True.

**Triggers:**

- `session_event_append_only`: `CREATE TRIGGER session_event_append_only BEFORE UPDATE ON live.session_event FOR EACH ROW EXECUTE FUNCTION live.session_event_append_only()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `live.takeover`

**Kind / use case:** table. Instructor takeover control lifecycle/evidence.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L247); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L661).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `takeover_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `live_session_id` | `uuid` | no | `-` | `- / -` |
| `scope` | `text` | no | `-` | `- / -` |
| `scope_id` | `text` | no | `'*'::text` | `- / -` |
| `instructor` | `text` | no | `-` | `- / -` |
| `handoff_packet` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `started_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `ended_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `takeover_handoff_packet_not_null` / `n` | `NOT NULL handoff_packet` | deferrable=False, initially deferred=False, validated=True |
| `takeover_instructor_not_null` / `n` | `NOT NULL instructor` | deferrable=False, initially deferred=False, validated=True |
| `takeover_live_session_id_fkey` / `f` | `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `takeover_live_session_id_not_null` / `n` | `NOT NULL live_session_id` | deferrable=False, initially deferred=False, validated=True |
| `takeover_pkey` / `p` | `PRIMARY KEY (takeover_id)` | deferrable=False, initially deferred=False, validated=True |
| `takeover_scope_check` / `c` | `CHECK (scope = ANY (ARRAY['SESSION'::text, 'STUDENT'::text, 'GROUP'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `takeover_scope_id_not_null` / `n` | `NOT NULL scope_id` | deferrable=False, initially deferred=False, validated=True |
| `takeover_scope_not_null` / `n` | `NOT NULL scope` | deferrable=False, initially deferred=False, validated=True |
| `takeover_started_at_not_null` / `n` | `NOT NULL started_at` | deferrable=False, initially deferred=False, validated=True |
| `takeover_takeover_id_not_null` / `n` | `NOT NULL takeover_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `takeover_active_uidx`: `CREATE UNIQUE INDEX takeover_active_uidx ON live.takeover USING btree (live_session_id, scope, scope_id) WHERE (ended_at IS NULL)`; valid=True, ready=True.
- `takeover_pkey`: `CREATE UNIQUE INDEX takeover_pkey ON live.takeover USING btree (takeover_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `live.topic_run`

**Kind / use case:** table. Current topic/stage time and orchestration state.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L218); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L185).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `live_session_id` | `uuid` | no | `-` | `- / -` |
| `topic_index` | `integer` | no | `-` | `- / -` |
| `title` | `text` | no | `-` | `- / -` |
| `planned_seconds` | `integer` | no | `-` | `- / -` |
| `started_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `ended_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `actual_seconds` | `integer` | yes | `-` | `- / -` |
| `status` | `text` | no | `'PENDING'::text` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `topic_run_live_session_id_fkey` / `f` | `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `topic_run_live_session_id_not_null` / `n` | `NOT NULL live_session_id` | deferrable=False, initially deferred=False, validated=True |
| `topic_run_pkey` / `p` | `PRIMARY KEY (live_session_id, topic_index)` | deferrable=False, initially deferred=False, validated=True |
| `topic_run_planned_seconds_not_null` / `n` | `NOT NULL planned_seconds` | deferrable=False, initially deferred=False, validated=True |
| `topic_run_status_check` / `c` | `CHECK (status = ANY (ARRAY['PENDING'::text, 'ACTIVE'::text, 'DONE'::text, 'SKIPPED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `topic_run_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `topic_run_title_not_null` / `n` | `NOT NULL title` | deferrable=False, initially deferred=False, validated=True |
| `topic_run_topic_index_not_null` / `n` | `NOT NULL topic_index` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `topic_run_pkey`: `CREATE UNIQUE INDEX topic_run_pkey ON live.topic_run USING btree (live_session_id, topic_index)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

## Functions and routines

Extension routines are owned by their installed extension, not project migration code.
Volatility: i=immutable, s=stable, v=volatile. No routine was invoked by this inspection.

| Signature | Returns | Language / volatility | Security definer | Owner / source |
|---|---|---|---|---|
| `session_event_append_only(-)` | `trigger` | plpgsql / v | False | [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql) |

### Observed definition: `live.session_event_append_only`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION live.session_event_append_only()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    RAISE EXCEPTION 'live.session_event is append-only';
END $function$
```
