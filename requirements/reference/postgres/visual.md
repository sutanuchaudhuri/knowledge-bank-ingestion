# PostgreSQL `visual` schema

**Role:** Declarative widget registry/state. Validated WidgetSpecs, session state and asset metadata.

**Access family:** `/v1/widgets/*`, live widget operations; stored-spec mutations are admin-only. No step-widget attachment REST resource.

**Evidence:** live catalog metadata at 2026-10-08T01:57:54.421824+00:00; source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `visual.asset`

**Kind / use case:** table. Widget-supporting asset locator/type/provenance metadata.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L342); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `asset_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `uri` | `text` | no | `-` | `- / -` |
| `mime_type` | `text` | no | `-` | `- / -` |
| `content_hash` | `text` | no | `-` | `- / -` |
| `source_problem_id` | `uuid` | yes | `-` | `- / -` |
| `diagram_id` | `text` | yes | `-` | `- / -` |
| `created_by_agent` | `text` | yes | `-` | `- / -` |
| `persistence_mode` | `text` | no | `'SESSION'::text` | `- / -` |
| `validation_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `expires_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `asset_asset_id_not_null` / `n` | `NOT NULL asset_id` | deferrable=False, initially deferred=False, validated=True |
| `asset_content_hash_not_null` / `n` | `NOT NULL content_hash` | deferrable=False, initially deferred=False, validated=True |
| `asset_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `asset_diagram_id_fkey` / `f` | `FOREIGN KEY (diagram_id) REFERENCES pedagogy.diagram(diagram_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `asset_mime_type_not_null` / `n` | `NOT NULL mime_type` | deferrable=False, initially deferred=False, validated=True |
| `asset_persistence_mode_check` / `c` | `CHECK (persistence_mode = ANY (ARRAY['STATIC'::text, 'SESSION'::text, 'EPHEMERAL'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `asset_persistence_mode_not_null` / `n` | `NOT NULL persistence_mode` | deferrable=False, initially deferred=False, validated=True |
| `asset_pkey` / `p` | `PRIMARY KEY (asset_id)` | deferrable=False, initially deferred=False, validated=True |
| `asset_source_problem_id_fkey` / `f` | `FOREIGN KEY (source_problem_id) REFERENCES core.problem(problem_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `asset_uri_not_null` / `n` | `NOT NULL uri` | deferrable=False, initially deferred=False, validated=True |
| `asset_validation_status_check` / `c` | `CHECK (validation_status = ANY (ARRAY['PENDING'::text, 'VALID'::text, 'REJECTED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `asset_validation_status_not_null` / `n` | `NOT NULL validation_status` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `asset_hash_idx`: `CREATE INDEX asset_hash_idx ON visual.asset USING btree (content_hash)`; valid=True, ready=True.
- `asset_pkey`: `CREATE UNIQUE INDEX asset_pkey ON visual.asset USING btree (asset_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `visual.widget_spec`

**Kind / use case:** table. Validated declarative widget content/lifecycle/persistence/lineage.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L306); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L305); [mathbank-rest/src/mathbank_rest/routers/fluid.py](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L122).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `widget_spec_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `widget_type` | `text` | no | `-` | `- / -` |
| `spec_version` | `text` | no | `'1'::text` | `- / -` |
| `title` | `text` | yes | `-` | `- / -` |
| `spec` | `jsonb` | no | `-` | `- / -` |
| `lifecycle` | `text` | no | `'VALIDATED'::text` | `- / -` |
| `persistence` | `text` | no | `'SESSION'::text` | `- / -` |
| `live_session_id` | `uuid` | yes | `-` | `- / -` |
| `source_type` | `text` | no | `-` | `- / -` |
| `source_lineage` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `validation` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `content_hash` | `text` | no | `-` | `- / -` |
| `created_by` | `text` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `expires_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `reviewed_by` | `text` | yes | `-` | `- / -` |
| `reviewed_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `widget_spec_content_hash_not_null` / `n` | `NOT NULL content_hash` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_created_by_not_null` / `n` | `NOT NULL created_by` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_lifecycle_check` / `c` | `CHECK (lifecycle = ANY (ARRAY['REQUESTED'::text, 'SPEC_GENERATED'::text, 'VALIDATED'::text, 'READY'::text, 'SHOWN'::text, 'EXPIRED'::text, 'REJECTED'::text, 'PROMOTION_CANDIDATE'::text, 'PROMOTED_TO_TEMPLATE'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_lifecycle_not_null` / `n` | `NOT NULL lifecycle` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_live_session_id_fkey` / `f` | `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_persistence_check` / `c` | `CHECK (persistence = ANY (ARRAY['STATIC'::text, 'SESSION'::text, 'EPHEMERAL'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_persistence_not_null` / `n` | `NOT NULL persistence` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_pkey` / `p` | `PRIMARY KEY (widget_spec_id)` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_source_lineage_not_null` / `n` | `NOT NULL source_lineage` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_source_type_check` / `c` | `CHECK (source_type = ANY (ARRAY['PRECOMPILED'::text, 'CORPUS_DERIVED'::text, 'LIVE_AGENT_CREATED'::text, 'INSTRUCTOR_CREATED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_source_type_not_null` / `n` | `NOT NULL source_type` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_spec_not_null` / `n` | `NOT NULL spec` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_spec_version_not_null` / `n` | `NOT NULL spec_version` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_validation_not_null` / `n` | `NOT NULL validation` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_widget_spec_id_not_null` / `n` | `NOT NULL widget_spec_id` | deferrable=False, initially deferred=False, validated=True |
| `widget_spec_widget_type_not_null` / `n` | `NOT NULL widget_type` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `visual.widget_state` / `widget_state_widget_spec_id_fkey`: `FOREIGN KEY (widget_spec_id) REFERENCES visual.widget_spec(widget_spec_id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `widget_spec_lifecycle_idx`: `CREATE INDEX widget_spec_lifecycle_idx ON visual.widget_spec USING btree (lifecycle, created_at DESC)`; valid=True, ready=True.
- `widget_spec_pkey`: `CREATE UNIQUE INDEX widget_spec_pkey ON visual.widget_spec USING btree (widget_spec_id)`; valid=True, ready=True.
- `widget_spec_session_idx`: `CREATE INDEX widget_spec_session_idx ON visual.widget_spec USING btree (live_session_id, created_at DESC)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `visual.widget_state`

**Kind / use case:** table. Session-scoped state associated with a stored widget spec.

**Migration owner:** [020_live_fluid_platform.sql](../../../mathbank-db/sql/020_live_fluid_platform.sql#L330); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L333).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `live_session_id` | `uuid` | no | `-` | `- / -` |
| `widget_instance_id` | `text` | no | `-` | `- / -` |
| `widget_spec_id` | `uuid` | no | `-` | `- / -` |
| `state` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `state_version` | `bigint` | no | `1` | `- / -` |
| `visible` | `boolean` | no | `true` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `widget_state_live_session_id_fkey` / `f` | `FOREIGN KEY (live_session_id) REFERENCES live.session(live_session_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `widget_state_live_session_id_not_null` / `n` | `NOT NULL live_session_id` | deferrable=False, initially deferred=False, validated=True |
| `widget_state_pkey` / `p` | `PRIMARY KEY (live_session_id, widget_instance_id)` | deferrable=False, initially deferred=False, validated=True |
| `widget_state_state_not_null` / `n` | `NOT NULL state` | deferrable=False, initially deferred=False, validated=True |
| `widget_state_state_version_not_null` / `n` | `NOT NULL state_version` | deferrable=False, initially deferred=False, validated=True |
| `widget_state_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |
| `widget_state_visible_not_null` / `n` | `NOT NULL visible` | deferrable=False, initially deferred=False, validated=True |
| `widget_state_widget_instance_id_not_null` / `n` | `NOT NULL widget_instance_id` | deferrable=False, initially deferred=False, validated=True |
| `widget_state_widget_spec_id_fkey` / `f` | `FOREIGN KEY (widget_spec_id) REFERENCES visual.widget_spec(widget_spec_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `widget_state_widget_spec_id_not_null` / `n` | `NOT NULL widget_spec_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `widget_state_pkey`: `CREATE UNIQUE INDEX widget_state_pkey ON visual.widget_state USING btree (live_session_id, widget_instance_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

