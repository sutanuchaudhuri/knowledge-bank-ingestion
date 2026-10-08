# PostgreSQL `geometry_scene` schema

**Role:** Private geometry scenes. Immutable accepted geometry versions, receipts and interpretation/review runs.

**Access family:** `/v1/geometry-scenes/*`; learner JWT ownership or explicit staff operations.

**Evidence:** live catalog metadata at 2026-10-08T01:57:54.421824+00:00; source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `geometry_scene.receipts`

**Kind / use case:** table. Immutable owner-scoped accepted interpretation idempotency receipt.

**Migration owner:** [026_geometry_scenes.sql](../../../mathbank-rest/src/mathbank_rest/migrations/026_geometry_scenes.sql#L20); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/geometry_storage.py](../../../mathbank-rest/src/mathbank_rest/geometry_storage.py#L128).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `owner` | `text` | no | `-` | `- / -` |
| `key` | `text` | no | `-` | `- / -` |
| `request_hash` | `text` | no | `-` | `- / -` |
| `scene_id` | `text` | no | `-` | `- / -` |
| `version` | `integer` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `receipts_key_not_null` / `n` | `NOT NULL key` | deferrable=False, initially deferred=False, validated=True |
| `receipts_owner_not_null` / `n` | `NOT NULL owner` | deferrable=False, initially deferred=False, validated=True |
| `receipts_pkey` / `p` | `PRIMARY KEY (owner, key)` | deferrable=False, initially deferred=False, validated=True |
| `receipts_request_hash_not_null` / `n` | `NOT NULL request_hash` | deferrable=False, initially deferred=False, validated=True |
| `receipts_scene_id_not_null` / `n` | `NOT NULL scene_id` | deferrable=False, initially deferred=False, validated=True |
| `receipts_scene_id_version_fkey` / `f` | `FOREIGN KEY (scene_id, version) REFERENCES geometry_scene.versions(scene_id, version)` | deferrable=False, initially deferred=False, validated=True |
| `receipts_version_not_null` / `n` | `NOT NULL version` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `receipts_pkey`: `CREATE UNIQUE INDEX receipts_pkey ON geometry_scene.receipts USING btree (owner, key)`; valid=True, ready=True.

**Triggers:**

- `immutable_geometry_receipts`: `CREATE TRIGGER immutable_geometry_receipts BEFORE DELETE OR UPDATE ON geometry_scene.receipts FOR EACH ROW EXECUTE FUNCTION geometry_scene.reject_accepted_mutation()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `geometry_scene.runs`

**Kind / use case:** table. Private model/validation/review evidence; staff review never publishes a scene.

**Migration owner:** [026_geometry_scenes.sql](../../../mathbank-rest/src/mathbank_rest/migrations/026_geometry_scenes.sql#L29); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/geometry_storage.py](../../../mathbank-rest/src/mathbank_rest/geometry_storage.py#L279).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `owner` | `text` | no | `-` | `- / -` |
| `run_id` | `text` | no | `-` | `- / -` |
| `evidence_asset` | `jsonb` | no | `-` | `- / -` |
| `evidence_hash` | `text` | no | `-` | `- / -` |
| `review` | `jsonb` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `runs_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `runs_evidence_asset_not_null` / `n` | `NOT NULL evidence_asset` | deferrable=False, initially deferred=False, validated=True |
| `runs_evidence_hash_not_null` / `n` | `NOT NULL evidence_hash` | deferrable=False, initially deferred=False, validated=True |
| `runs_owner_not_null` / `n` | `NOT NULL owner` | deferrable=False, initially deferred=False, validated=True |
| `runs_pkey` / `p` | `PRIMARY KEY (owner, run_id)` | deferrable=False, initially deferred=False, validated=True |
| `runs_run_id_not_null` / `n` | `NOT NULL run_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `runs_pkey`: `CREATE UNIQUE INDEX runs_pkey ON geometry_scene.runs USING btree (owner, run_id)`; valid=True, ready=True.

**Triggers:**

- `immutable_geometry_run_evidence`: `CREATE TRIGGER immutable_geometry_run_evidence BEFORE DELETE OR UPDATE ON geometry_scene.runs FOR EACH ROW EXECUTE FUNCTION geometry_scene.protect_run_evidence()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `geometry_scene.scenes`

**Kind / use case:** table. Owned accepted-scene head with optimistic version.

**Migration owner:** [026_geometry_scenes.sql](../../../mathbank-rest/src/mathbank_rest/migrations/026_geometry_scenes.sql#L4); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/geometry_storage.py](../../../mathbank-rest/src/mathbank_rest/geometry_storage.py#L95).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `scene_id` | `text` | no | `-` | `- / -` |
| `owner` | `text` | no | `-` | `- / -` |
| `current_version` | `integer` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `scenes_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `scenes_current_version_check` / `c` | `CHECK (current_version >= 0)` | deferrable=False, initially deferred=False, validated=True |
| `scenes_current_version_not_null` / `n` | `NOT NULL current_version` | deferrable=False, initially deferred=False, validated=True |
| `scenes_owner_not_null` / `n` | `NOT NULL owner` | deferrable=False, initially deferred=False, validated=True |
| `scenes_pkey` / `p` | `PRIMARY KEY (scene_id)` | deferrable=False, initially deferred=False, validated=True |
| `scenes_scene_id_not_null` / `n` | `NOT NULL scene_id` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `geometry_scene.versions` / `versions_scene_id_fkey`: `FOREIGN KEY (scene_id) REFERENCES geometry_scene.scenes(scene_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `geometry_scene_owner_idx`: `CREATE INDEX geometry_scene_owner_idx ON geometry_scene.scenes USING btree (owner)`; valid=True, ready=True.
- `scenes_pkey`: `CREATE UNIQUE INDEX scenes_pkey ON geometry_scene.scenes USING btree (scene_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `geometry_scene.versions`

**Kind / use case:** table. Immutable accepted scene state and private SVG lineage.

**Migration owner:** [026_geometry_scenes.sql](../../../mathbank-rest/src/mathbank_rest/migrations/026_geometry_scenes.sql#L12); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/geometry_storage.py](../../../mathbank-rest/src/mathbank_rest/geometry_storage.py#L94).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `scene_id` | `text` | no | `-` | `- / -` |
| `version` | `integer` | no | `-` | `- / -` |
| `assets` | `jsonb` | no | `-` | `- / -` |
| `lineage` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `versions_assets_not_null` / `n` | `NOT NULL assets` | deferrable=False, initially deferred=False, validated=True |
| `versions_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `versions_lineage_not_null` / `n` | `NOT NULL lineage` | deferrable=False, initially deferred=False, validated=True |
| `versions_pkey` / `p` | `PRIMARY KEY (scene_id, version)` | deferrable=False, initially deferred=False, validated=True |
| `versions_scene_id_fkey` / `f` | `FOREIGN KEY (scene_id) REFERENCES geometry_scene.scenes(scene_id)` | deferrable=False, initially deferred=False, validated=True |
| `versions_scene_id_not_null` / `n` | `NOT NULL scene_id` | deferrable=False, initially deferred=False, validated=True |
| `versions_version_check` / `c` | `CHECK (version >= 0)` | deferrable=False, initially deferred=False, validated=True |
| `versions_version_not_null` / `n` | `NOT NULL version` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `geometry_scene.receipts` / `receipts_scene_id_version_fkey`: `FOREIGN KEY (scene_id, version) REFERENCES geometry_scene.versions(scene_id, version)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `versions_pkey`: `CREATE UNIQUE INDEX versions_pkey ON geometry_scene.versions USING btree (scene_id, version)`; valid=True, ready=True.

**Triggers:**

- `immutable_geometry_versions`: `CREATE TRIGGER immutable_geometry_versions BEFORE DELETE OR UPDATE ON geometry_scene.versions FOR EACH ROW EXECUTE FUNCTION geometry_scene.reject_accepted_mutation()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

## Functions and routines

Extension routines are owned by their installed extension, not project migration code.
Volatility: i=immutable, s=stable, v=volatile. No routine was invoked by this inspection.

| Signature | Returns | Language / volatility | Security definer | Owner / source |
|---|---|---|---|---|
| `protect_run_evidence(-)` | `trigger` | plpgsql / v | False | [026_geometry_scenes.sql](../../../mathbank-rest/src/mathbank_rest/migrations/026_geometry_scenes.sql) |
| `reject_accepted_mutation(-)` | `trigger` | plpgsql / v | False | [026_geometry_scenes.sql](../../../mathbank-rest/src/mathbank_rest/migrations/026_geometry_scenes.sql) |

### Observed definition: `geometry_scene.protect_run_evidence`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION geometry_scene.protect_run_evidence()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_OP = 'DELETE' OR NEW.owner IS DISTINCT FROM OLD.owner
        OR NEW.run_id IS DISTINCT FROM OLD.run_id
        OR NEW.evidence_asset IS DISTINCT FROM OLD.evidence_asset
        OR NEW.evidence_hash IS DISTINCT FROM OLD.evidence_hash
        OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'geometry run evidence is immutable; only review may change';
    END IF;
    RETURN NEW;
END;
$function$
```

### Observed definition: `geometry_scene.reject_accepted_mutation`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION geometry_scene.reject_accepted_mutation()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    RAISE EXCEPTION 'accepted geometry versions and receipts are immutable';
END;
$function$
```
