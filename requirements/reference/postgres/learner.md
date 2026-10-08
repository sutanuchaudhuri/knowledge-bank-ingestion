# PostgreSQL `learner` schema

**Role:** Authenticated learner data. Student accounts, attempt evidence, per-step states, mastery, feedback and agent-session links.

**Access family:** `/v1/learner/*`, `/v1/students/{student_id}/problems/{problem_ref}/attempts`, `/v1/attempts/*`; JWT ownership checks.

**Evidence:** live catalog metadata at 2026-10-08T01:57:54.421824+00:00; source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `learner.agent_session_link`

**Kind / use case:** table. Logical ownership link from learner to ADK service sessions.

**Migration owner:** [016_agent_session_link.sql](../../../mathbank-db/sql/016_agent_session_link.sql#L14); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/agent_transcripts.py](../../../mathbank-rest/src/mathbank_rest/agent_transcripts.py#L4); [mathbank-web/lib/agentIdentity.mjs](../../../mathbank-web/lib/agentIdentity.mjs#L4).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `agent_session_link_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `agent_app_name` | `text` | no | `-` | `- / -` |
| `agent_user_id` | `text` | no | `-` | `- / -` |
| `agent_session_id` | `text` | no | `-` | `- / -` |
| `student_id` | `uuid` | no | `-` | `- / -` |
| `surface` | `text` | no | `'HOME_CHAT'::text` | `- / -` |
| `context` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `last_seen_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `agent_session_link_agent_app_name_not_null` / `n` | `NOT NULL agent_app_name` | deferrable=False, initially deferred=False, validated=True |
| `agent_session_link_agent_session_id_not_null` / `n` | `NOT NULL agent_session_id` | deferrable=False, initially deferred=False, validated=True |
| `agent_session_link_agent_session_link_id_not_null` / `n` | `NOT NULL agent_session_link_id` | deferrable=False, initially deferred=False, validated=True |
| `agent_session_link_agent_user_id_not_null` / `n` | `NOT NULL agent_user_id` | deferrable=False, initially deferred=False, validated=True |
| `agent_session_link_context_not_null` / `n` | `NOT NULL context` | deferrable=False, initially deferred=False, validated=True |
| `agent_session_link_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `agent_session_link_last_seen_at_not_null` / `n` | `NOT NULL last_seen_at` | deferrable=False, initially deferred=False, validated=True |
| `agent_session_link_pkey` / `p` | `PRIMARY KEY (agent_session_link_id)` | deferrable=False, initially deferred=False, validated=True |
| `agent_session_link_session_uq` / `u` | `UNIQUE (agent_app_name, agent_session_id)` | deferrable=False, initially deferred=False, validated=True |
| `agent_session_link_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `agent_session_link_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |
| `agent_session_link_surface_check` / `c` | `CHECK (surface = ANY (ARRAY['HOME_CHAT'::text, 'SOLVE_WORKSPACE'::text, 'OTHER'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `agent_session_link_surface_not_null` / `n` | `NOT NULL surface` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `agent_session_link_pkey`: `CREATE UNIQUE INDEX agent_session_link_pkey ON learner.agent_session_link USING btree (agent_session_link_id)`; valid=True, ready=True.
- `agent_session_link_session_uq`: `CREATE UNIQUE INDEX agent_session_link_session_uq ON learner.agent_session_link USING btree (agent_app_name, agent_session_id)`; valid=True, ready=True.
- `agent_session_link_student_idx`: `CREATE INDEX agent_session_link_student_idx ON learner.agent_session_link USING btree (student_id, created_at DESC)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `learner.attempt`

**Kind / use case:** table. Recorded whole-problem attempts; nullable correctness for unassessed evidence.

**Migration owner:** [003_learner_schema.sql](../../../mathbank-db/sql/003_learner_schema.sql#L27); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/attempt_media.py#L328); [mathbank-rest/src/mathbank_rest/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/step_runtime.py#L515); [mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py](../../../mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py#L128); [mathbank-rest/src/mathbank_rest/db/learner.py](../../../mathbank-rest/src/mathbank_rest/db/learner.py#L30).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `attempt_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `student_id` | `uuid` | no | `-` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `is_correct` | `boolean` | yes | `-` | `- / -` |
| `submitted_answer` | `text` | yes | `-` | `- / -` |
| `time_spent_seconds` | `integer` | yes | `-` | `- / -` |
| `hint_count` | `integer` | no | `0` | `- / -` |
| `attempted_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `source` | `text` | no | `'web'::text` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `attempt_attempt_id_not_null` / `n` | `NOT NULL attempt_id` | deferrable=False, initially deferred=False, validated=True |
| `attempt_attempted_at_not_null` / `n` | `NOT NULL attempted_at` | deferrable=False, initially deferred=False, validated=True |
| `attempt_hint_count_not_null` / `n` | `NOT NULL hint_count` | deferrable=False, initially deferred=False, validated=True |
| `attempt_pkey` / `p` | `PRIMARY KEY (attempt_id)` | deferrable=False, initially deferred=False, validated=True |
| `attempt_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `attempt_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `attempt_source_not_null` / `n` | `NOT NULL source` | deferrable=False, initially deferred=False, validated=True |
| `attempt_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `attempt_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |
| `attempt_time_spent_seconds_check` / `c` | `CHECK (time_spent_seconds IS NULL OR time_spent_seconds >= 0)` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `attempt_media.approval` / `approval_learner_attempt_id_fkey`: `FOREIGN KEY (learner_attempt_id) REFERENCES learner.attempt(attempt_id)`.
- `learner.solve_attempt` / `solve_attempt_outcome_attempt_id_fkey`: `FOREIGN KEY (outcome_attempt_id) REFERENCES learner.attempt(attempt_id) ON DELETE SET NULL`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `attempt_pkey`: `CREATE UNIQUE INDEX attempt_pkey ON learner.attempt USING btree (attempt_id)`; valid=True, ready=True.
- `idx_attempt_problem`: `CREATE INDEX idx_attempt_problem ON learner.attempt USING btree (problem_id)`; valid=True, ready=True.
- `idx_attempt_student`: `CREATE INDEX idx_attempt_student ON learner.attempt USING btree (student_id, attempted_at DESC)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `learner.attempt_step_state`

**Kind / use case:** table. Per-attempt responses, help use, verdict and independent/assisted progress.

**Migration owner:** [012_step_runtime.sql](../../../mathbank-db/sql/012_step_runtime.sql#L36); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/step_runtime.py#L184); [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L479); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L194); [mathbank-rest/src/mathbank_rest/step_tutor.py](../../../mathbank-rest/src/mathbank_rest/step_tutor.py#L208).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `solve_attempt_id` | `uuid` | no | `-` | `- / -` |
| `solution_step_id` | `text` | no | `-` | `- / -` |
| `state` | `text` | no | `'NOT_SEEN'::text` | `- / -` |
| `first_seen_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `first_attempted_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `last_updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `independent_success` | `boolean` | yes | `-` | `- / -` |
| `help_level_used` | `integer` | no | `0` | `- / -` |
| `attempt_count` | `integer` | no | `0` | `- / -` |
| `last_response_text` | `text` | yes | `-` | `- / -` |
| `last_evaluation` | `jsonb` | yes | `-` | `- / -` |
| `evidence` | `jsonb` | no | `'{}'::jsonb` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `attempt_step_state_attempt_count_check` / `c` | `CHECK (attempt_count >= 0)` | deferrable=False, initially deferred=False, validated=True |
| `attempt_step_state_attempt_count_not_null` / `n` | `NOT NULL attempt_count` | deferrable=False, initially deferred=False, validated=True |
| `attempt_step_state_evidence_not_null` / `n` | `NOT NULL evidence` | deferrable=False, initially deferred=False, validated=True |
| `attempt_step_state_help_level_used_check` / `c` | `CHECK (help_level_used >= 0 AND help_level_used <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `attempt_step_state_help_level_used_not_null` / `n` | `NOT NULL help_level_used` | deferrable=False, initially deferred=False, validated=True |
| `attempt_step_state_last_updated_at_not_null` / `n` | `NOT NULL last_updated_at` | deferrable=False, initially deferred=False, validated=True |
| `attempt_step_state_pkey` / `p` | `PRIMARY KEY (solve_attempt_id, solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `attempt_step_state_solution_step_id_fkey` / `f` | `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `attempt_step_state_solution_step_id_not_null` / `n` | `NOT NULL solution_step_id` | deferrable=False, initially deferred=False, validated=True |
| `attempt_step_state_solve_attempt_id_fkey` / `f` | `FOREIGN KEY (solve_attempt_id) REFERENCES learner.solve_attempt(solve_attempt_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `attempt_step_state_solve_attempt_id_not_null` / `n` | `NOT NULL solve_attempt_id` | deferrable=False, initially deferred=False, validated=True |
| `attempt_step_state_state_check` / `c` | `CHECK (state = ANY (ARRAY['NOT_SEEN'::text, 'PRESENTED'::text, 'ATTEMPTED'::text, 'SUCCESS_INDEPENDENT'::text, 'SUCCESS_WITH_HELP'::text, 'FAILED'::text, 'DETOURED'::text, 'RETRY_PRESENTED'::text, 'SKIPPED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `attempt_step_state_state_not_null` / `n` | `NOT NULL state` | deferrable=False, initially deferred=False, validated=True |
| `step_state_independent_requires_no_help` / `c` | `CHECK (independent_success IS NOT TRUE OR help_level_used = 0)` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `attempt_step_state_pkey`: `CREATE UNIQUE INDEX attempt_step_state_pkey ON learner.attempt_step_state USING btree (solve_attempt_id, solution_step_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `learner.concept_mastery`

**Kind / use case:** table. Derived per-learner concept mastery and weakness evidence.

**Migration owner:** [003_learner_schema.sql](../../../mathbank-db/sql/003_learner_schema.sql#L46); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/learner.py](../../../mathbank-rest/src/mathbank_rest/db/learner.py#L234).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `student_id` | `uuid` | no | `-` | `- / -` |
| `concept_id` | `uuid` | no | `-` | `- / -` |
| `mastery_score` | `numeric` | no | `-` | `- / -` |
| `attempts_count` | `integer` | no | `0` | `- / -` |
| `correct_count` | `integer` | no | `0` | `- / -` |
| `last_attempt_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `concept_mastery_attempts_count_not_null` / `n` | `NOT NULL attempts_count` | deferrable=False, initially deferred=False, validated=True |
| `concept_mastery_concept_id_fkey` / `f` | `FOREIGN KEY (concept_id) REFERENCES knowledge.concept(concept_id)` | deferrable=False, initially deferred=False, validated=True |
| `concept_mastery_concept_id_not_null` / `n` | `NOT NULL concept_id` | deferrable=False, initially deferred=False, validated=True |
| `concept_mastery_correct_count_not_null` / `n` | `NOT NULL correct_count` | deferrable=False, initially deferred=False, validated=True |
| `concept_mastery_mastery_score_check` / `c` | `CHECK (mastery_score >= 0::numeric AND mastery_score <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `concept_mastery_mastery_score_not_null` / `n` | `NOT NULL mastery_score` | deferrable=False, initially deferred=False, validated=True |
| `concept_mastery_pkey` / `p` | `PRIMARY KEY (student_id, concept_id)` | deferrable=False, initially deferred=False, validated=True |
| `concept_mastery_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `concept_mastery_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |
| `concept_mastery_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `concept_mastery_pkey`: `CREATE UNIQUE INDEX concept_mastery_pkey ON learner.concept_mastery USING btree (student_id, concept_id)`; valid=True, ready=True.
- `idx_concept_mastery_student`: `CREATE INDEX idx_concept_mastery_student ON learner.concept_mastery USING btree (student_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `learner.event`

**Kind / use case:** table. Append-only learner runtime evidence/event log.

**Migration owner:** [012_step_runtime.sql](../../../mathbank-db/sql/012_step_runtime.sql#L57); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/step_runtime.py#L154); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L10).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `event_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `student_id` | `uuid` | no | `-` | `- / -` |
| `solve_attempt_id` | `uuid` | yes | `-` | `- / -` |
| `event_type` | `text` | no | `-` | `- / -` |
| `event_time` | `timestamp with time zone` | no | `clock_timestamp()` | `- / -` |
| `actor_type` | `text` | no | `-` | `- / -` |
| `solution_step_id` | `text` | yes | `-` | `- / -` |
| `payload` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `idempotency_key` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `event_actor_type_check` / `c` | `CHECK (actor_type = ANY (ARRAY['STUDENT'::text, 'TUTOR'::text, 'AGENT'::text, 'SYSTEM'::text, 'ADMIN'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `event_actor_type_not_null` / `n` | `NOT NULL actor_type` | deferrable=False, initially deferred=False, validated=True |
| `event_event_id_not_null` / `n` | `NOT NULL event_id` | deferrable=False, initially deferred=False, validated=True |
| `event_event_time_not_null` / `n` | `NOT NULL event_time` | deferrable=False, initially deferred=False, validated=True |
| `event_event_type_check` / `c` | `CHECK (event_type = ANY (ARRAY['ATTEMPT_STARTED'::text, 'PROBLEM_VIEWED'::text, 'STEP_PRESENTED'::text, 'STEP_RESPONSE_SUBMITTED'::text, 'STEP_EVALUATED'::text, 'STEP_COMPLETED_INDEPENDENTLY'::text, 'STEP_COMPLETED_WITH_HELP'::text, 'STEP_FAILED'::text, 'STEP_SKIPPED'::text, 'HINT_REQUESTED'::text, 'HINT_PRESENTED'::text, 'GAP_DIAGNOSED'::text, 'GAP_HYPOTHESIS_CREATED'::text, 'GAP_HYPOTHESIS_CONFIRMED'::text, 'GAP_HYPOTHESIS_REJECTED'::text, 'GAP_HYPOTHESIS_RESOLVED'::text, 'RECOVERY_PLAN_CREATED'::text, 'RECOVERY_ITEM_PRESENTED'::text, 'RECOVERY_ITEM_SUBMITTED'::text, 'RECOVERY_ITEM_EVALUATED'::text, 'RECOVERY_PLAN_COMPLETED'::text, 'RECOVERY_PLAN_ABORTED'::text, 'RECOVERY_PLAN_BRANCHED'::text, 'RECOVERY_PLAN_EXHAUSTED'::text, 'RETURNED_TO_ORIGINAL_STEP'::text, 'RETURNED_TO_ORIGINAL_PROBLEM'::text, 'ATTEMPT_SUBMITTED'::text, 'ATTEMPT_COMPLETED'::text, 'ATTEMPT_ABANDONED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `event_event_type_not_null` / `n` | `NOT NULL event_type` | deferrable=False, initially deferred=False, validated=True |
| `event_payload_not_null` / `n` | `NOT NULL payload` | deferrable=False, initially deferred=False, validated=True |
| `event_pkey` / `p` | `PRIMARY KEY (event_id)` | deferrable=False, initially deferred=False, validated=True |
| `event_solution_step_id_fkey` / `f` | `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `event_solve_attempt_id_fkey` / `f` | `FOREIGN KEY (solve_attempt_id) REFERENCES learner.solve_attempt(solve_attempt_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `event_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `event_student_id_idempotency_key_key` / `u` | `UNIQUE (student_id, idempotency_key)` | deferrable=False, initially deferred=False, validated=True |
| `event_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `event_attempt_idx`: `CREATE INDEX event_attempt_idx ON learner.event USING btree (solve_attempt_id, event_time)`; valid=True, ready=True.
- `event_pkey`: `CREATE UNIQUE INDEX event_pkey ON learner.event USING btree (event_id)`; valid=True, ready=True.
- `event_student_id_idempotency_key_key`: `CREATE UNIQUE INDEX event_student_id_idempotency_key_key ON learner.event USING btree (student_id, idempotency_key)`; valid=True, ready=True.
- `event_student_idx`: `CREATE INDEX event_student_idx ON learner.event USING btree (student_id, event_time DESC)`; valid=True, ready=True.

**Triggers:**

- `event_append_only`: `CREATE TRIGGER event_append_only BEFORE DELETE OR UPDATE ON learner.event FOR EACH ROW EXECUTE FUNCTION learner.event_append_only()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `learner.idempotency_record`

**Kind / use case:** table. Scoped request hashes and replay responses for learner mutations.

**Migration owner:** [012_step_runtime.sql](../../../mathbank-db/sql/012_step_runtime.sql#L96); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/step_runtime.py#L131).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `student_id` | `uuid` | no | `-` | `- / -` |
| `idempotency_key` | `text` | no | `-` | `- / -` |
| `operation` | `text` | no | `-` | `- / -` |
| `request_hash` | `text` | no | `-` | `- / -` |
| `response` | `jsonb` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `idempotency_record_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `idempotency_record_idempotency_key_check` / `c` | `CHECK (length(idempotency_key) >= 1 AND length(idempotency_key) <= 200)` | deferrable=False, initially deferred=False, validated=True |
| `idempotency_record_idempotency_key_not_null` / `n` | `NOT NULL idempotency_key` | deferrable=False, initially deferred=False, validated=True |
| `idempotency_record_operation_not_null` / `n` | `NOT NULL operation` | deferrable=False, initially deferred=False, validated=True |
| `idempotency_record_pkey` / `p` | `PRIMARY KEY (student_id, idempotency_key)` | deferrable=False, initially deferred=False, validated=True |
| `idempotency_record_request_hash_not_null` / `n` | `NOT NULL request_hash` | deferrable=False, initially deferred=False, validated=True |
| `idempotency_record_response_not_null` / `n` | `NOT NULL response` | deferrable=False, initially deferred=False, validated=True |
| `idempotency_record_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `idempotency_record_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `idempotency_record_pkey`: `CREATE UNIQUE INDEX idempotency_record_pkey ON learner.idempotency_record USING btree (student_id, idempotency_key)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `learner.pedagogy_feedback`

**Kind / use case:** table. Learner relevance reports with source audit snapshot and reviewed retriever labels.

**Migration owner:** [023_pedagogy_feedback.sql](../../../mathbank-db/sql/023_pedagogy_feedback.sql#L3); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py](../../../mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py#L113).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `feedback_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `student_id` | `uuid` | no | `-` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `topic` | `text` | no | `-` | `- / -` |
| `reason` | `text` | no | `-` | `- / -` |
| `status` | `text` | no | `'PENDING'::text` | `- / -` |
| `review_note` | `text` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `reviewed_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `feedback_type` | `text` | no | `'RETRIEVAL_IRRELEVANT'::text` | `- / -` |
| `audit_snapshot` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `retrieval_verdict` | `text` | no | `'UNCLASSIFIED'::text` | `- / -` |
| `error_kind` | `text` | no | `'UNCLASSIFIED'::text` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `feedback_negative_review_check` / `c` | `CHECK (retrieval_verdict = 'UNCLASSIFIED'::text OR status <> 'PENDING'::text AND review_note IS NOT NULL)` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_audit_snapshot_check` / `c` | `CHECK (jsonb_typeof(audit_snapshot) = 'object'::text)` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_audit_snapshot_not_null` / `n` | `NOT NULL audit_snapshot` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_check` / `c` | `CHECK (status = 'PENDING'::text AND reviewed_at IS NULL AND review_note IS NULL OR status <> 'PENDING'::text AND reviewed_at IS NOT NULL AND review_note IS NOT NULL)` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_error_kind_check` / `c` | `CHECK (error_kind = ANY (ARRAY['UNCLASSIFIED'::text, 'METADATA'::text, 'RETRIEVAL'::text, 'INSUFFICIENT_EVIDENCE'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_error_kind_not_null` / `n` | `NOT NULL error_kind` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_feedback_id_not_null` / `n` | `NOT NULL feedback_id` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_feedback_type_check` / `c` | `CHECK (feedback_type = 'RETRIEVAL_IRRELEVANT'::text)` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_feedback_type_not_null` / `n` | `NOT NULL feedback_type` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_pkey` / `p` | `PRIMARY KEY (feedback_id)` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_reason_check` / `c` | `CHECK (length(btrim(reason)) >= 10 AND length(btrim(reason)) <= 2000)` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_reason_not_null` / `n` | `NOT NULL reason` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_retrieval_verdict_check` / `c` | `CHECK (retrieval_verdict = ANY (ARRAY['UNCLASSIFIED'::text, 'IRRELEVANT'::text, 'RELEVANT'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_retrieval_verdict_not_null` / `n` | `NOT NULL retrieval_verdict` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_review_note_check` / `c` | `CHECK (length(btrim(review_note)) >= 10 AND length(btrim(review_note)) <= 2000)` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_status_check` / `c` | `CHECK (status = ANY (ARRAY['PENDING'::text, 'RESOLVED'::text, 'DISMISSED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_student_id_problem_id_topic_reason_key` / `u` | `UNIQUE (student_id, problem_id, topic, reason)` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_topic_check` / `c` | `CHECK (length(btrim(topic)) >= 1 AND length(btrim(topic)) <= 200)` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_feedback_topic_not_null` / `n` | `NOT NULL topic` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `pedagogy_feedback_pending_idx`: `CREATE INDEX pedagogy_feedback_pending_idx ON learner.pedagogy_feedback USING btree (status, created_at)`; valid=True, ready=True.
- `pedagogy_feedback_pkey`: `CREATE UNIQUE INDEX pedagogy_feedback_pkey ON learner.pedagogy_feedback USING btree (feedback_id)`; valid=True, ready=True.
- `pedagogy_feedback_reviewed_negative_idx`: `CREATE INDEX pedagogy_feedback_reviewed_negative_idx ON learner.pedagogy_feedback USING btree (topic, problem_id) WHERE ((retrieval_verdict = 'IRRELEVANT'::text) AND (status = 'RESOLVED'::text))`; valid=True, ready=True.
- `pedagogy_feedback_student_id_problem_id_topic_reason_key`: `CREATE UNIQUE INDEX pedagogy_feedback_student_id_problem_id_topic_reason_key ON learner.pedagogy_feedback USING btree (student_id, problem_id, topic, reason)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `learner.route_attempt`

**Kind / use case:** table. JWT-owned route release pin, optimistic current checkpoint and tutor-explained positions; never a mastery record.

**Migration owner:** [026_tutoring_routes.sql](../../../mathbank-db/sql/026_tutoring_routes.sql#L118); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/route_runtime.py](../../../mathbank-rest/src/mathbank_rest/route_runtime.py#L336).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `route_attempt_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `student_id` | `uuid` | no | `-` | `- / -` |
| `route_release_id` | `uuid` | no | `-` | `- / -` |
| `current_step` | `integer` | no | `1` | `- / -` |
| `version` | `integer` | no | `1` | `- / -` |
| `tutor_explained_steps` | `integer[]` | no | `'{}'::integer[]` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `route_attempt_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `route_attempt_current_step_check` / `c` | `CHECK (current_step > 0)` | deferrable=False, initially deferred=False, validated=True |
| `route_attempt_current_step_not_null` / `n` | `NOT NULL current_step` | deferrable=False, initially deferred=False, validated=True |
| `route_attempt_pkey` / `p` | `PRIMARY KEY (route_attempt_id)` | deferrable=False, initially deferred=False, validated=True |
| `route_attempt_route_attempt_id_not_null` / `n` | `NOT NULL route_attempt_id` | deferrable=False, initially deferred=False, validated=True |
| `route_attempt_route_release_id_fkey` / `f` | `FOREIGN KEY (route_release_id) REFERENCES pedagogy.solution_route_release(route_release_id)` | deferrable=False, initially deferred=False, validated=True |
| `route_attempt_route_release_id_not_null` / `n` | `NOT NULL route_release_id` | deferrable=False, initially deferred=False, validated=True |
| `route_attempt_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id)` | deferrable=False, initially deferred=False, validated=True |
| `route_attempt_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |
| `route_attempt_tutor_explained_steps_not_null` / `n` | `NOT NULL tutor_explained_steps` | deferrable=False, initially deferred=False, validated=True |
| `route_attempt_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |
| `route_attempt_version_check` / `c` | `CHECK (version > 0)` | deferrable=False, initially deferred=False, validated=True |
| `route_attempt_version_not_null` / `n` | `NOT NULL version` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `route_attempt_pkey`: `CREATE UNIQUE INDEX route_attempt_pkey ON learner.route_attempt USING btree (route_attempt_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `learner.solve_attempt`

**Kind / use case:** table. Durable step-solving session and selected current reference step.

**Migration owner:** [012_step_runtime.sql](../../../mathbank-db/sql/012_step_runtime.sql#L14); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/step_runtime.py#L190); [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L246); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L195); [mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py](../../../mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py#L126).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `solve_attempt_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `student_id` | `uuid` | no | `-` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `attempt_number` | `integer` | no | `-` | `- / -` |
| `status` | `text` | no | `'IN_PROGRESS'::text` | `- / -` |
| `started_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `submitted_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `completed_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `current_solution_part_id` | `text` | yes | `-` | `- / -` |
| `current_solution_step_id` | `text` | yes | `-` | `- / -` |
| `recovery_plan_id` | `uuid` | yes | `-` | `- / -` |
| `outcome_attempt_id` | `uuid` | yes | `-` | `- / -` |
| `metadata` | `jsonb` | no | `'{}'::jsonb` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solve_attempt_attempt_number_check` / `c` | `CHECK (attempt_number >= 1)` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_attempt_number_not_null` / `n` | `NOT NULL attempt_number` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_current_solution_part_id_fkey` / `f` | `FOREIGN KEY (current_solution_part_id) REFERENCES pedagogy.solution_part(solution_part_id)` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_current_solution_step_id_fkey` / `f` | `FOREIGN KEY (current_solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_metadata_not_null` / `n` | `NOT NULL metadata` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_outcome_attempt_id_fkey` / `f` | `FOREIGN KEY (outcome_attempt_id) REFERENCES learner.attempt(attempt_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_pkey` / `p` | `PRIMARY KEY (solve_attempt_id)` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_recovery_plan_fk` / `f` | `FOREIGN KEY (recovery_plan_id) REFERENCES pedagogy.recovery_plan(recovery_plan_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_solve_attempt_id_not_null` / `n` | `NOT NULL solve_attempt_id` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_started_at_not_null` / `n` | `NOT NULL started_at` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_status_check` / `c` | `CHECK (status = ANY (ARRAY['IN_PROGRESS'::text, 'SUBMITTED'::text, 'COMPLETED'::text, 'ABANDONED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |
| `solve_attempt_student_id_problem_id_attempt_number_key` / `u` | `UNIQUE (student_id, problem_id, attempt_number)` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `learner.attempt_step_state` / `attempt_step_state_solve_attempt_id_fkey`: `FOREIGN KEY (solve_attempt_id) REFERENCES learner.solve_attempt(solve_attempt_id) ON DELETE CASCADE`.
- `learner.event` / `event_solve_attempt_id_fkey`: `FOREIGN KEY (solve_attempt_id) REFERENCES learner.solve_attempt(solve_attempt_id) ON DELETE CASCADE`.
- `pedagogy.gap_diagnosis` / `gap_diagnosis_solve_attempt_id_fkey`: `FOREIGN KEY (solve_attempt_id) REFERENCES learner.solve_attempt(solve_attempt_id) ON DELETE CASCADE`.
- `pedagogy.knowledge_gap` / `knowledge_gap_solve_attempt_id_fkey`: `FOREIGN KEY (solve_attempt_id) REFERENCES learner.solve_attempt(solve_attempt_id) ON DELETE CASCADE`.
- `pedagogy.recovery_plan` / `recovery_plan_solve_attempt_id_fkey`: `FOREIGN KEY (solve_attempt_id) REFERENCES learner.solve_attempt(solve_attempt_id) ON DELETE CASCADE`.
- `tutor.runtime_state` / `runtime_state_solve_attempt_id_fkey`: `FOREIGN KEY (solve_attempt_id) REFERENCES learner.solve_attempt(solve_attempt_id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `solve_attempt_one_open`: `CREATE UNIQUE INDEX solve_attempt_one_open ON learner.solve_attempt USING btree (student_id, problem_id) WHERE (status = 'IN_PROGRESS'::text)`; valid=True, ready=True.
- `solve_attempt_pkey`: `CREATE UNIQUE INDEX solve_attempt_pkey ON learner.solve_attempt USING btree (solve_attempt_id)`; valid=True, ready=True.
- `solve_attempt_student_id_problem_id_attempt_number_key`: `CREATE UNIQUE INDEX solve_attempt_student_id_problem_id_attempt_number_key ON learner.solve_attempt USING btree (student_id, problem_id, attempt_number)`; valid=True, ready=True.
- `solve_attempt_student_idx`: `CREATE INDEX solve_attempt_student_idx ON learner.solve_attempt USING btree (student_id, started_at DESC)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `learner.student_profile`

**Kind / use case:** table. MathBank learner identity and bcrypt/JWT account metadata.

**Migration owner:** [003_learner_schema.sql](../../../mathbank-db/sql/003_learner_schema.sql#L15); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/live_runtime.py](../../../mathbank-rest/src/mathbank_rest/live_runtime.py#L211); [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L819); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L579); [mathbank-rest/src/mathbank_rest/outbox_worker.py](../../../mathbank-rest/src/mathbank_rest/outbox_worker.py#L70); [mathbank-rest/src/mathbank_rest/agent_transcripts.py](../../../mathbank-rest/src/mathbank_rest/agent_transcripts.py#L147); [mathbank-rest/src/mathbank_rest/db/learner.py](../../../mathbank-rest/src/mathbank_rest/db/learner.py#L57).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `student_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `email` | `text` | no | `-` | `- / -` |
| `password_hash` | `text` | no | `-` | `- / -` |
| `display_name` | `text` | yes | `-` | `- / -` |
| `status` | `text` | no | `'ACTIVE'::text` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `last_login_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `first_name` | `text` | yes | `-` | `- / -` |
| `last_name` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `student_profile_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `student_profile_email_key` / `u` | `UNIQUE (email)` | deferrable=False, initially deferred=False, validated=True |
| `student_profile_email_not_null` / `n` | `NOT NULL email` | deferrable=False, initially deferred=False, validated=True |
| `student_profile_password_hash_not_null` / `n` | `NOT NULL password_hash` | deferrable=False, initially deferred=False, validated=True |
| `student_profile_pkey` / `p` | `PRIMARY KEY (student_id)` | deferrable=False, initially deferred=False, validated=True |
| `student_profile_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `student_profile_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `analytics.learner_daily_activity` / `learner_daily_activity_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `artifact_runtime.artifact_request` / `artifact_request_owner_student_id_fkey`: `FOREIGN KEY (owner_student_id) REFERENCES learner.student_profile(student_id)`.
- `attempt_media.submission` / `submission_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `learner.agent_session_link` / `agent_session_link_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `learner.attempt` / `attempt_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `learner.concept_mastery` / `concept_mastery_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `learner.event` / `event_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `learner.idempotency_record` / `idempotency_record_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `learner.pedagogy_feedback` / `pedagogy_feedback_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `learner.route_attempt` / `route_attempt_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id)`.
- `learner.solve_attempt` / `solve_attempt_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `learner.technique_mastery` / `technique_mastery_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `live.participant` / `participant_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE SET NULL`.
- `pedagogy.gap_diagnosis` / `gap_diagnosis_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `pedagogy.knowledge_gap` / `knowledge_gap_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `pedagogy.recovery_plan` / `recovery_plan_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.
- `tutor.runtime_state` / `runtime_state_student_id_fkey`: `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `student_profile_email_key`: `CREATE UNIQUE INDEX student_profile_email_key ON learner.student_profile USING btree (email)`; valid=True, ready=True.
- `student_profile_pkey`: `CREATE UNIQUE INDEX student_profile_pkey ON learner.student_profile USING btree (student_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `learner.technique_mastery`

**Kind / use case:** table. Derived per-learner technique mastery and weakness evidence.

**Migration owner:** [003_learner_schema.sql](../../../mathbank-db/sql/003_learner_schema.sql#L57); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/learner.py](../../../mathbank-rest/src/mathbank_rest/db/learner.py#L262).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `student_id` | `uuid` | no | `-` | `- / -` |
| `technique_id` | `uuid` | no | `-` | `- / -` |
| `mastery_score` | `numeric` | no | `-` | `- / -` |
| `attempts_count` | `integer` | no | `0` | `- / -` |
| `correct_count` | `integer` | no | `0` | `- / -` |
| `last_attempt_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `technique_mastery_attempts_count_not_null` / `n` | `NOT NULL attempts_count` | deferrable=False, initially deferred=False, validated=True |
| `technique_mastery_correct_count_not_null` / `n` | `NOT NULL correct_count` | deferrable=False, initially deferred=False, validated=True |
| `technique_mastery_mastery_score_check` / `c` | `CHECK (mastery_score >= 0::numeric AND mastery_score <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `technique_mastery_mastery_score_not_null` / `n` | `NOT NULL mastery_score` | deferrable=False, initially deferred=False, validated=True |
| `technique_mastery_pkey` / `p` | `PRIMARY KEY (student_id, technique_id)` | deferrable=False, initially deferred=False, validated=True |
| `technique_mastery_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `technique_mastery_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |
| `technique_mastery_technique_id_fkey` / `f` | `FOREIGN KEY (technique_id) REFERENCES knowledge.technique(technique_id)` | deferrable=False, initially deferred=False, validated=True |
| `technique_mastery_technique_id_not_null` / `n` | `NOT NULL technique_id` | deferrable=False, initially deferred=False, validated=True |
| `technique_mastery_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `idx_technique_mastery_student`: `CREATE INDEX idx_technique_mastery_student ON learner.technique_mastery USING btree (student_id)`; valid=True, ready=True.
- `technique_mastery_pkey`: `CREATE UNIQUE INDEX technique_mastery_pkey ON learner.technique_mastery USING btree (student_id, technique_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

## Functions and routines

Extension routines are owned by their installed extension, not project migration code.
Volatility: i=immutable, s=stable, v=volatile. No routine was invoked by this inspection.

| Signature | Returns | Language / volatility | Security definer | Owner / source |
|---|---|---|---|---|
| `event_append_only(-)` | `trigger` | plpgsql / v | False | [012_step_runtime.sql](../../../mathbank-db/sql/012_step_runtime.sql) |

### Observed definition: `learner.event_append_only`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION learner.event_append_only()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    RAISE EXCEPTION 'learner.event is append-only (% rejected)', TG_OP USING ERRCODE = 'restrict_violation';
END $function$
```
