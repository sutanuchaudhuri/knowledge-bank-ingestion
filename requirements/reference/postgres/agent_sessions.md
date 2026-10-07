# PostgreSQL `agent_sessions` schema

**Role:** ADK-managed framework storage. Google ADK database sessions, events and user/app state; not project migration tables.

**Access family:** ADK agent service plus `/v1/learner/agent-sessions/*` and `/v1/admin/agent-sessions/*` transcript reads; logical learner.agent_session_link, no cross-schema FK.

**Evidence:** live catalog metadata at 2026-10-07T13:40:57.292324+00:00; source `375f3743357cef814c50e3c8752f7f4ce2d6ebe5`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `agent_sessions.adk_internal_metadata`

**Kind / use case:** table. ADK framework schema/version bookkeeping.

**Owner:** Google ADK framework-managed, configured by [session_config.py](../../../mathbank-agent/session_config.py). Not a numbered project migration.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `key` | `character varying(128)` | no | `-` | `- / -` |
| `value` | `character varying(256)` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `adk_internal_metadata_key_not_null` / `n` | `NOT NULL key` | deferrable=False, initially deferred=False, validated=True |
| `adk_internal_metadata_pkey` / `p` | `PRIMARY KEY (key)` | deferrable=False, initially deferred=False, validated=True |
| `adk_internal_metadata_value_not_null` / `n` | `NOT NULL value` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `adk_internal_metadata_pkey`: `CREATE UNIQUE INDEX adk_internal_metadata_pkey ON agent_sessions.adk_internal_metadata USING btree (key)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `agent_sessions.app_states`

**Kind / use case:** table. ADK application-scoped persistent state.

**Owner:** Google ADK framework-managed, configured by [session_config.py](../../../mathbank-agent/session_config.py). Not a numbered project migration.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `app_name` | `character varying(128)` | no | `-` | `- / -` |
| `state` | `jsonb` | no | `-` | `- / -` |
| `update_time` | `timestamp without time zone` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `app_states_app_name_not_null` / `n` | `NOT NULL app_name` | deferrable=False, initially deferred=False, validated=True |
| `app_states_pkey` / `p` | `PRIMARY KEY (app_name)` | deferrable=False, initially deferred=False, validated=True |
| `app_states_state_not_null` / `n` | `NOT NULL state` | deferrable=False, initially deferred=False, validated=True |
| `app_states_update_time_not_null` / `n` | `NOT NULL update_time` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `app_states_pkey`: `CREATE UNIQUE INDEX app_states_pkey ON agent_sessions.app_states USING btree (app_name)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `agent_sessions.events`

**Kind / use case:** table. ADK invocation messages, tool actions and state deltas.

**Owner:** Google ADK framework-managed, configured by [session_config.py](../../../mathbank-agent/session_config.py). Not a numbered project migration.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/agent_transcripts.py](../../../mathbank-rest/src/mathbank_rest/agent_transcripts.py#L5).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `id` | `character varying(128)` | no | `-` | `- / -` |
| `app_name` | `character varying(128)` | no | `-` | `- / -` |
| `user_id` | `character varying(128)` | no | `-` | `- / -` |
| `session_id` | `character varying(128)` | no | `-` | `- / -` |
| `invocation_id` | `character varying(256)` | no | `-` | `- / -` |
| `timestamp` | `timestamp without time zone` | no | `-` | `- / -` |
| `event_data` | `jsonb` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `events_app_name_not_null` / `n` | `NOT NULL app_name` | deferrable=False, initially deferred=False, validated=True |
| `events_app_name_user_id_session_id_fkey` / `f` | `FOREIGN KEY (app_name, user_id, session_id) REFERENCES agent_sessions.sessions(app_name, user_id, id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `events_id_not_null` / `n` | `NOT NULL id` | deferrable=False, initially deferred=False, validated=True |
| `events_invocation_id_not_null` / `n` | `NOT NULL invocation_id` | deferrable=False, initially deferred=False, validated=True |
| `events_pkey` / `p` | `PRIMARY KEY (id, app_name, user_id, session_id)` | deferrable=False, initially deferred=False, validated=True |
| `events_session_id_not_null` / `n` | `NOT NULL session_id` | deferrable=False, initially deferred=False, validated=True |
| `events_timestamp_not_null` / `n` | `NOT NULL "timestamp"` | deferrable=False, initially deferred=False, validated=True |
| `events_user_id_not_null` / `n` | `NOT NULL user_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `events_pkey`: `CREATE UNIQUE INDEX events_pkey ON agent_sessions.events USING btree (id, app_name, user_id, session_id)`; valid=True, ready=True.
- `idx_events_app_user_session_ts_id`: `CREATE INDEX idx_events_app_user_session_ts_id ON agent_sessions.events USING btree (app_name, user_id, session_id, "timestamp" DESC, id DESC)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `agent_sessions.sessions`

**Kind / use case:** table. ADK app/user/session identities and session-state JSON.

**Owner:** Google ADK framework-managed, configured by [session_config.py](../../../mathbank-agent/session_config.py). Not a numbered project migration.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `app_name` | `character varying(128)` | no | `-` | `- / -` |
| `user_id` | `character varying(128)` | no | `-` | `- / -` |
| `id` | `character varying(128)` | no | `-` | `- / -` |
| `state` | `jsonb` | no | `-` | `- / -` |
| `create_time` | `timestamp without time zone` | no | `-` | `- / -` |
| `update_time` | `timestamp without time zone` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `sessions_app_name_not_null` / `n` | `NOT NULL app_name` | deferrable=False, initially deferred=False, validated=True |
| `sessions_create_time_not_null` / `n` | `NOT NULL create_time` | deferrable=False, initially deferred=False, validated=True |
| `sessions_id_not_null` / `n` | `NOT NULL id` | deferrable=False, initially deferred=False, validated=True |
| `sessions_pkey` / `p` | `PRIMARY KEY (app_name, user_id, id)` | deferrable=False, initially deferred=False, validated=True |
| `sessions_state_not_null` / `n` | `NOT NULL state` | deferrable=False, initially deferred=False, validated=True |
| `sessions_update_time_not_null` / `n` | `NOT NULL update_time` | deferrable=False, initially deferred=False, validated=True |
| `sessions_user_id_not_null` / `n` | `NOT NULL user_id` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `agent_sessions.events` / `events_app_name_user_id_session_id_fkey`: `FOREIGN KEY (app_name, user_id, session_id) REFERENCES agent_sessions.sessions(app_name, user_id, id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `sessions_pkey`: `CREATE UNIQUE INDEX sessions_pkey ON agent_sessions.sessions USING btree (app_name, user_id, id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `agent_sessions.user_states`

**Kind / use case:** table. ADK user-scoped persistent state.

**Owner:** Google ADK framework-managed, configured by [session_config.py](../../../mathbank-agent/session_config.py). Not a numbered project migration.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `app_name` | `character varying(128)` | no | `-` | `- / -` |
| `user_id` | `character varying(128)` | no | `-` | `- / -` |
| `state` | `jsonb` | no | `-` | `- / -` |
| `update_time` | `timestamp without time zone` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `user_states_app_name_not_null` / `n` | `NOT NULL app_name` | deferrable=False, initially deferred=False, validated=True |
| `user_states_pkey` / `p` | `PRIMARY KEY (app_name, user_id)` | deferrable=False, initially deferred=False, validated=True |
| `user_states_state_not_null` / `n` | `NOT NULL state` | deferrable=False, initially deferred=False, validated=True |
| `user_states_update_time_not_null` / `n` | `NOT NULL update_time` | deferrable=False, initially deferred=False, validated=True |
| `user_states_user_id_not_null` / `n` | `NOT NULL user_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `user_states_pkey`: `CREATE UNIQUE INDEX user_states_pkey ON agent_sessions.user_states USING btree (app_name, user_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

