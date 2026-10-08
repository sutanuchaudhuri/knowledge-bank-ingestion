# PostgreSQL `tutor` schema

**Role:** Durable step-runtime state. Mode and optimistic state-version of each step-solving attempt.

**Access family:** `/v1/attempts/*`; step/recovery runtime functions, scoped by JWT-owned attempt.

**Evidence:** live catalog metadata at 2026-10-08T01:57:54.421824+00:00; source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `tutor.runtime_state`

**Kind / use case:** table. Attempt mode, recovery pointer and optimistic state version.

**Migration owner:** [012_step_runtime.sql](../../../mathbank-db/sql/012_step_runtime.sql#L106); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/step_runtime.py#L191); [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L443); [mathbank-agent/agents/mathbank_tutor/tools/step_runtime_tools.py](../../../mathbank-agent/agents/mathbank_tutor/tools/step_runtime_tools.py#L28).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `student_id` | `uuid` | no | `-` | `- / -` |
| `solve_attempt_id` | `uuid` | no | `-` | `- / -` |
| `current_mode` | `text` | no | `'SOLVING'::text` | `- / -` |
| `current_problem_id` | `uuid` | no | `-` | `- / -` |
| `current_step_id` | `text` | yes | `-` | `- / -` |
| `current_recovery_plan_id` | `uuid` | yes | `-` | `- / -` |
| `last_agent_turn_id` | `text` | yes | `-` | `- / -` |
| `state_version` | `bigint` | no | `1` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `runtime_state_current_mode_check` / `c` | `CHECK (current_mode = ANY (ARRAY['SOLVING'::text, 'DIAGNOSING'::text, 'RECOVERY'::text, 'REVIEW'::text, 'COMPLETED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_current_mode_not_null` / `n` | `NOT NULL current_mode` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_current_problem_id_fkey` / `f` | `FOREIGN KEY (current_problem_id) REFERENCES core.problem(problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_current_problem_id_not_null` / `n` | `NOT NULL current_problem_id` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_current_step_id_fkey` / `f` | `FOREIGN KEY (current_step_id) REFERENCES pedagogy.solution_step(solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_pkey` / `p` | `PRIMARY KEY (student_id, solve_attempt_id)` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_recovery_plan_fk` / `f` | `FOREIGN KEY (current_recovery_plan_id) REFERENCES pedagogy.recovery_plan(recovery_plan_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_solve_attempt_id_fkey` / `f` | `FOREIGN KEY (solve_attempt_id) REFERENCES learner.solve_attempt(solve_attempt_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_solve_attempt_id_not_null` / `n` | `NOT NULL solve_attempt_id` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_state_version_check` / `c` | `CHECK (state_version >= 1)` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_state_version_not_null` / `n` | `NOT NULL state_version` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |
| `runtime_state_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `runtime_state_pkey`: `CREATE UNIQUE INDEX runtime_state_pkey ON tutor.runtime_state USING btree (student_id, solve_attempt_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

