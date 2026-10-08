# PostgreSQL `authoring` schema

**Role:** Versioned presentation authoring. Plans/topics plus chat-proposed patches; publishing protection.

**Access family:** `/v1/authoring/*`; shared admin API key. This is not a canonical atomic-step editor.

**Evidence:** live catalog metadata at 2026-10-08T01:57:54.421824+00:00; source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `authoring.chat_message`

**Kind / use case:** table. Stored admin planning messages; distinct from ADK learner sessions.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L117); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/authoring.py](../../../mathbank-rest/src/mathbank_rest/authoring.py#L459).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `message_id` | `bigint` | no | `nextval('authoring.chat_message_message_id_seq'::regclass)` | `- / -` |
| `chat_session_id` | `uuid` | no | `-` | `- / -` |
| `role` | `text` | no | `-` | `- / -` |
| `content` | `text` | no | `-` | `- / -` |
| `patch_id` | `uuid` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `chat_message_chat_session_id_fkey` / `f` | `FOREIGN KEY (chat_session_id) REFERENCES authoring.chat_session(chat_session_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `chat_message_chat_session_id_not_null` / `n` | `NOT NULL chat_session_id` | deferrable=False, initially deferred=False, validated=True |
| `chat_message_content_not_null` / `n` | `NOT NULL content` | deferrable=False, initially deferred=False, validated=True |
| `chat_message_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `chat_message_message_id_not_null` / `n` | `NOT NULL message_id` | deferrable=False, initially deferred=False, validated=True |
| `chat_message_patch_id_fkey` / `f` | `FOREIGN KEY (patch_id) REFERENCES authoring.proposed_patch(patch_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `chat_message_pkey` / `p` | `PRIMARY KEY (message_id)` | deferrable=False, initially deferred=False, validated=True |
| `chat_message_role_check` / `c` | `CHECK (role = ANY (ARRAY['ADMIN'::text, 'ASSISTANT'::text, 'SYSTEM'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `chat_message_role_not_null` / `n` | `NOT NULL role` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `chat_message_pkey`: `CREATE UNIQUE INDEX chat_message_pkey ON authoring.chat_message USING btree (message_id)`; valid=True, ready=True.
- `chat_message_session_idx`: `CREATE INDEX chat_message_session_idx ON authoring.chat_message USING btree (chat_session_id, message_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `authoring.chat_message_message_id_seq`

**Kind:** sequence; allocates identity values for associated serial columns.
No sequence current/last value was read. Column defaults and indexes identify its table use.

### `authoring.chat_session`

**Kind / use case:** table. Admin planning conversation associated with a plan.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L92); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/authoring.py](../../../mathbank-rest/src/mathbank_rest/authoring.py#L447).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `chat_session_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `plan_id` | `uuid` | no | `-` | `- / -` |
| `actor` | `text` | no | `'admin'::text` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `chat_session_actor_not_null` / `n` | `NOT NULL actor` | deferrable=False, initially deferred=False, validated=True |
| `chat_session_chat_session_id_not_null` / `n` | `NOT NULL chat_session_id` | deferrable=False, initially deferred=False, validated=True |
| `chat_session_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `chat_session_pkey` / `p` | `PRIMARY KEY (chat_session_id)` | deferrable=False, initially deferred=False, validated=True |
| `chat_session_plan_id_fkey` / `f` | `FOREIGN KEY (plan_id) REFERENCES authoring.presentation_plan(plan_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `chat_session_plan_id_not_null` / `n` | `NOT NULL plan_id` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `authoring.chat_message` / `chat_message_chat_session_id_fkey`: `FOREIGN KEY (chat_session_id) REFERENCES authoring.chat_session(chat_session_id) ON DELETE CASCADE`.
- `authoring.proposed_patch` / `proposed_patch_chat_session_id_fkey`: `FOREIGN KEY (chat_session_id) REFERENCES authoring.chat_session(chat_session_id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `chat_session_pkey`: `CREATE UNIQUE INDEX chat_session_pkey ON authoring.chat_session USING btree (chat_session_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `authoring.plan_topic`

**Kind / use case:** table. Ordered plan topic/goal/timing/widget/activity selections.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L35); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L161); [mathbank-rest/src/mathbank_rest/authoring.py](../../../mathbank-rest/src/mathbank_rest/authoring.py#L316).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `topic_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `plan_id` | `uuid` | no | `-` | `- / -` |
| `ordinal` | `integer` | no | `-` | `- / -` |
| `title` | `text` | no | `-` | `- / -` |
| `concept` | `text` | yes | `-` | `- / -` |
| `problem_ref` | `text` | yes | `-` | `- / -` |
| `planned_seconds` | `integer` | no | `-` | `- / -` |
| `min_seconds` | `integer` | yes | `-` | `- / -` |
| `max_seconds` | `integer` | yes | `-` | `- / -` |
| `required` | `boolean` | no | `true` | `- / -` |
| `scenes` | `jsonb` | no | `'[]'::jsonb` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `plan_topic_max_seconds_check` / `c` | `CHECK (max_seconds IS NULL OR max_seconds > 0)` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_min_seconds_check` / `c` | `CHECK (min_seconds IS NULL OR min_seconds > 0)` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_ordinal_check` / `c` | `CHECK (ordinal >= 0)` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_ordinal_not_null` / `n` | `NOT NULL ordinal` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_pkey` / `p` | `PRIMARY KEY (topic_id)` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_plan_id_fkey` / `f` | `FOREIGN KEY (plan_id) REFERENCES authoring.presentation_plan(plan_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_plan_id_not_null` / `n` | `NOT NULL plan_id` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_plan_id_ordinal_key` / `u` | `UNIQUE (plan_id, ordinal) DEFERRABLE INITIALLY DEFERRED` | deferrable=True, initially deferred=True, validated=True |
| `plan_topic_planned_seconds_check` / `c` | `CHECK (planned_seconds > 0)` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_planned_seconds_not_null` / `n` | `NOT NULL planned_seconds` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_required_not_null` / `n` | `NOT NULL required` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_scenes_check` / `c` | `CHECK (jsonb_typeof(scenes) = 'array'::text)` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_scenes_not_null` / `n` | `NOT NULL scenes` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_title_not_null` / `n` | `NOT NULL title` | deferrable=False, initially deferred=False, validated=True |
| `plan_topic_topic_id_not_null` / `n` | `NOT NULL topic_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `plan_topic_pkey`: `CREATE UNIQUE INDEX plan_topic_pkey ON authoring.plan_topic USING btree (topic_id)`; valid=True, ready=True.
- `plan_topic_plan_id_ordinal_key`: `CREATE UNIQUE INDEX plan_topic_plan_id_ordinal_key ON authoring.plan_topic USING btree (plan_id, ordinal)`; valid=True, ready=True.

**Triggers:**

- `plan_topic_guard`: `CREATE TRIGGER plan_topic_guard BEFORE INSERT OR DELETE OR UPDATE ON authoring.plan_topic FOR EACH ROW EXECUTE FUNCTION authoring.guard_published_topic()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `authoring.presentation_plan`

**Kind / use case:** table. Versioned instructor presentation timing/publication plan.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L15); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L154); [mathbank-rest/src/mathbank_rest/authoring.py](../../../mathbank-rest/src/mathbank_rest/authoring.py#L309).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `plan_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `plan_key` | `text` | no | `-` | `- / -` |
| `version` | `integer` | no | `1` | `- / -` |
| `parent_plan_id` | `uuid` | yes | `-` | `- / -` |
| `title` | `text` | no | `-` | `- / -` |
| `description` | `text` | yes | `-` | `- / -` |
| `status` | `text` | no | `'DRAFT'::text` | `- / -` |
| `course_limit_seconds` | `integer` | no | `-` | `- / -` |
| `interaction_buffer_seconds` | `integer` | no | `0` | `- / -` |
| `hard_limit` | `boolean` | no | `false` | `- / -` |
| `created_by` | `text` | no | `'admin'::text` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `approved_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `published_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `presentation_plan_course_limit_seconds_check` / `c` | `CHECK (course_limit_seconds > 0)` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_course_limit_seconds_not_null` / `n` | `NOT NULL course_limit_seconds` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_created_by_not_null` / `n` | `NOT NULL created_by` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_hard_limit_not_null` / `n` | `NOT NULL hard_limit` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_interaction_buffer_seconds_check` / `c` | `CHECK (interaction_buffer_seconds >= 0)` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_interaction_buffer_seconds_not_null` / `n` | `NOT NULL interaction_buffer_seconds` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_parent_plan_id_fkey` / `f` | `FOREIGN KEY (parent_plan_id) REFERENCES authoring.presentation_plan(plan_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_pkey` / `p` | `PRIMARY KEY (plan_id)` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_plan_id_not_null` / `n` | `NOT NULL plan_id` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_plan_key_not_null` / `n` | `NOT NULL plan_key` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_plan_key_version_key` / `u` | `UNIQUE (plan_key, version)` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_status_check` / `c` | `CHECK (status = ANY (ARRAY['DRAFT'::text, 'APPROVED'::text, 'PUBLISHED'::text, 'SUPERSEDED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_title_not_null` / `n` | `NOT NULL title` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_version_check` / `c` | `CHECK (version >= 1)` | deferrable=False, initially deferred=False, validated=True |
| `presentation_plan_version_not_null` / `n` | `NOT NULL version` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `authoring.chat_session` / `chat_session_plan_id_fkey`: `FOREIGN KEY (plan_id) REFERENCES authoring.presentation_plan(plan_id) ON DELETE CASCADE`.
- `authoring.plan_topic` / `plan_topic_plan_id_fkey`: `FOREIGN KEY (plan_id) REFERENCES authoring.presentation_plan(plan_id) ON DELETE CASCADE`.
- `authoring.presentation_plan` / `presentation_plan_parent_plan_id_fkey`: `FOREIGN KEY (parent_plan_id) REFERENCES authoring.presentation_plan(plan_id) ON DELETE SET NULL`.
- `authoring.proposed_patch` / `proposed_patch_plan_id_fkey`: `FOREIGN KEY (plan_id) REFERENCES authoring.presentation_plan(plan_id) ON DELETE CASCADE`.
- `authoring.proposed_patch` / `proposed_patch_result_plan_id_fkey`: `FOREIGN KEY (result_plan_id) REFERENCES authoring.presentation_plan(plan_id) ON DELETE SET NULL`.
- `live.session` / `session_plan_id_fkey`: `FOREIGN KEY (plan_id) REFERENCES authoring.presentation_plan(plan_id) ON DELETE SET NULL`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `presentation_plan_pkey`: `CREATE UNIQUE INDEX presentation_plan_pkey ON authoring.presentation_plan USING btree (plan_id)`; valid=True, ready=True.
- `presentation_plan_plan_key_version_key`: `CREATE UNIQUE INDEX presentation_plan_plan_key_version_key ON authoring.presentation_plan USING btree (plan_key, version)`; valid=True, ready=True.

**Triggers:**

- `presentation_plan_guard`: `CREATE TRIGGER presentation_plan_guard BEFORE DELETE OR UPDATE ON authoring.presentation_plan FOR EACH ROW EXECUTE FUNCTION authoring.guard_published_plan()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `authoring.proposed_patch`

**Kind / use case:** table. Proposed plan change with explicit apply/reject lifecycle.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L99); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/authoring.py](../../../mathbank-rest/src/mathbank_rest/authoring.py#L468).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `patch_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `chat_session_id` | `uuid` | no | `-` | `- / -` |
| `plan_id` | `uuid` | no | `-` | `- / -` |
| `summary` | `text` | no | `-` | `- / -` |
| `operations` | `jsonb` | no | `-` | `- / -` |
| `impact` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `validation` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `proposer` | `text` | no | `'DETERMINISTIC_PARSER'::text` | `- / -` |
| `status` | `text` | no | `'PROPOSED'::text` | `- / -` |
| `result_plan_id` | `uuid` | yes | `-` | `- / -` |
| `decided_by` | `text` | yes | `-` | `- / -` |
| `decided_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `proposed_patch_chat_session_id_fkey` / `f` | `FOREIGN KEY (chat_session_id) REFERENCES authoring.chat_session(chat_session_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_chat_session_id_not_null` / `n` | `NOT NULL chat_session_id` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_impact_not_null` / `n` | `NOT NULL impact` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_operations_check` / `c` | `CHECK (jsonb_typeof(operations) = 'array'::text)` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_operations_not_null` / `n` | `NOT NULL operations` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_patch_id_not_null` / `n` | `NOT NULL patch_id` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_pkey` / `p` | `PRIMARY KEY (patch_id)` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_plan_id_fkey` / `f` | `FOREIGN KEY (plan_id) REFERENCES authoring.presentation_plan(plan_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_plan_id_not_null` / `n` | `NOT NULL plan_id` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_proposer_not_null` / `n` | `NOT NULL proposer` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_result_plan_id_fkey` / `f` | `FOREIGN KEY (result_plan_id) REFERENCES authoring.presentation_plan(plan_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_status_check` / `c` | `CHECK (status = ANY (ARRAY['PROPOSED'::text, 'APPLIED'::text, 'REJECTED'::text, 'SUPERSEDED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_summary_not_null` / `n` | `NOT NULL summary` | deferrable=False, initially deferred=False, validated=True |
| `proposed_patch_validation_not_null` / `n` | `NOT NULL validation` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `authoring.chat_message` / `chat_message_patch_id_fkey`: `FOREIGN KEY (patch_id) REFERENCES authoring.proposed_patch(patch_id) ON DELETE SET NULL`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `proposed_patch_chat_idx`: `CREATE INDEX proposed_patch_chat_idx ON authoring.proposed_patch USING btree (chat_session_id, created_at)`; valid=True, ready=True.
- `proposed_patch_pkey`: `CREATE UNIQUE INDEX proposed_patch_pkey ON authoring.proposed_patch USING btree (patch_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

## Functions and routines

Extension routines are owned by their installed extension, not project migration code.
Volatility: i=immutable, s=stable, v=volatile. No routine was invoked by this inspection.

| Signature | Returns | Language / volatility | Security definer | Owner / source |
|---|---|---|---|---|
| `guard_published_plan(-)` | `trigger` | plpgsql / v | False | [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql) |
| `guard_published_topic(-)` | `trigger` | plpgsql / v | False | [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql) |

### Observed definition: `authoring.guard_published_plan`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION authoring.guard_published_plan()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    -- Transaction-local escape hatch for the live test suite's own fixtures only.
    IF current_setting('authoring.allow_purge', true) = 'on' THEN RETURN COALESCE(NEW, OLD); END IF;
    IF TG_OP = 'DELETE' THEN
        IF OLD.status = 'PUBLISHED' THEN RAISE EXCEPTION 'published presentation plans are immutable'; END IF;
        RETURN OLD;
    END IF;
    IF OLD.status IN ('PUBLISHED', 'SUPERSEDED') THEN
        IF NEW.status = 'SUPERSEDED' AND OLD.status = 'PUBLISHED'
           AND (NEW.title, NEW.course_limit_seconds, NEW.interaction_buffer_seconds, NEW.hard_limit)
               IS NOT DISTINCT FROM (OLD.title, OLD.course_limit_seconds, OLD.interaction_buffer_seconds, OLD.hard_limit)
        THEN RETURN NEW; END IF;
        RAISE EXCEPTION 'published presentation plans are immutable; create a new draft version';
    END IF;
    RETURN NEW;
END $function$
```

### Observed definition: `authoring.guard_published_topic`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION authoring.guard_published_topic()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE plan_status text;
BEGIN
    IF current_setting('authoring.allow_purge', true) = 'on' THEN RETURN COALESCE(NEW, OLD); END IF;
    SELECT status INTO plan_status FROM authoring.presentation_plan
     WHERE plan_id = COALESCE(NEW.plan_id, OLD.plan_id);
    IF plan_status IN ('PUBLISHED', 'SUPERSEDED') THEN
        RAISE EXCEPTION 'topics of a published presentation plan are immutable';
    END IF;
    RETURN COALESCE(NEW, OLD);
END $function$
```
