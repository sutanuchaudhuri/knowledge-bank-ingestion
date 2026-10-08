# PostgreSQL `analytics` schema

**Role:** Derived learner aggregates. Transactional-outbox activity rollups, not canonical grading or mastery.

**Access family:** Outbox worker internal access; no dedicated direct-table public REST endpoint.

**Evidence:** live catalog metadata at 2026-10-08T01:57:54.421824+00:00; source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `analytics.learner_daily_activity`

**Kind / use case:** table. Idempotent UTC-day rollup from learner outbox events.

**Migration owner:** [018_outbox_consumers.sql](../../../mathbank-db/sql/018_outbox_consumers.sql#L29); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/outbox_worker.py](../../../mathbank-rest/src/mathbank_rest/outbox_worker.py#L27).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `student_id` | `uuid` | no | `-` | `- / -` |
| `activity_date` | `date` | no | `-` | `- / -` |
| `attempts_started` | `integer` | no | `0` | `- / -` |
| `attempts_completed` | `integer` | no | `0` | `- / -` |
| `attempts_abandoned` | `integer` | no | `0` | `- / -` |
| `steps_evaluated` | `integer` | no | `0` | `- / -` |
| `steps_succeeded` | `integer` | no | `0` | `- / -` |
| `gaps_diagnosed` | `integer` | no | `0` | `- / -` |
| `knowledge_gaps_created` | `integer` | no | `0` | `- / -` |
| `recovery_plans_created` | `integer` | no | `0` | `- / -` |
| `recovery_plans_completed` | `integer` | no | `0` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `learner_daily_activity_activity_date_not_null` / `n` | `NOT NULL activity_date` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_attempts_abandoned_not_null` / `n` | `NOT NULL attempts_abandoned` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_attempts_completed_not_null` / `n` | `NOT NULL attempts_completed` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_attempts_started_not_null` / `n` | `NOT NULL attempts_started` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_gaps_diagnosed_not_null` / `n` | `NOT NULL gaps_diagnosed` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_knowledge_gaps_created_not_null` / `n` | `NOT NULL knowledge_gaps_created` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_pkey` / `p` | `PRIMARY KEY (student_id, activity_date)` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_recovery_plans_completed_not_null` / `n` | `NOT NULL recovery_plans_completed` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_recovery_plans_created_not_null` / `n` | `NOT NULL recovery_plans_created` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_steps_evaluated_not_null` / `n` | `NOT NULL steps_evaluated` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_steps_succeeded_not_null` / `n` | `NOT NULL steps_succeeded` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |
| `learner_daily_activity_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `learner_daily_activity_pkey`: `CREATE UNIQUE INDEX learner_daily_activity_pkey ON analytics.learner_daily_activity USING btree (student_id, activity_date)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

