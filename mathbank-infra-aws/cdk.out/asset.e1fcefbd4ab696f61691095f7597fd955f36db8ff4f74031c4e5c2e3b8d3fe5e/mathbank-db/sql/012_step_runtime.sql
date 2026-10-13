-- 012 — v2 Phase 6: student step runtime (attempt session, step state, append-only events,
-- tutor runtime checkpoint, transactional outbox). Spec: runtime_extension/03 §6–8 & §12, 08, 09, 16.
--
-- Collision decision (GOT-PG-18): the existing learner.attempt (migration 003) is an append-only
-- per-answer log with is_correct NOT NULL that drives concept/technique mastery. The spec's
-- "attempt" is a stateful solving session with a current step. We keep learner.attempt unchanged and
-- add learner.solve_attempt for the session. When a session completes, the runtime writes exactly one
-- learner.attempt outcome row (linked via solve_attempt.outcome_attempt_id), so mastery keeps working.
--
-- Idempotent: safe to re-run.

CREATE SCHEMA IF NOT EXISTS tutor;

CREATE TABLE IF NOT EXISTS learner.solve_attempt (
    solve_attempt_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id               uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    problem_id               uuid NOT NULL REFERENCES core.problem,
    attempt_number           integer NOT NULL CHECK (attempt_number >= 1),
    status                   text NOT NULL DEFAULT 'IN_PROGRESS'
                             CHECK (status IN ('IN_PROGRESS', 'SUBMITTED', 'COMPLETED', 'ABANDONED')),
    started_at               timestamptz NOT NULL DEFAULT now(),
    submitted_at             timestamptz,
    completed_at             timestamptz,
    current_solution_part_id text REFERENCES pedagogy.solution_part,
    current_solution_step_id text REFERENCES pedagogy.solution_step,
    recovery_plan_id         uuid,  -- FK added with pedagogy.recovery_plan (Phase 10)
    outcome_attempt_id       uuid REFERENCES learner.attempt ON DELETE SET NULL,
    metadata                 jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (student_id, problem_id, attempt_number)
);
-- At most one open session per student and problem: "start" resumes it instead of duplicating.
CREATE UNIQUE INDEX IF NOT EXISTS solve_attempt_one_open
    ON learner.solve_attempt (student_id, problem_id) WHERE status = 'IN_PROGRESS';
CREATE INDEX IF NOT EXISTS solve_attempt_student_idx ON learner.solve_attempt (student_id, started_at DESC);

CREATE TABLE IF NOT EXISTS learner.attempt_step_state (
    solve_attempt_id   uuid NOT NULL REFERENCES learner.solve_attempt ON DELETE CASCADE,
    solution_step_id   text NOT NULL REFERENCES pedagogy.solution_step,
    state              text NOT NULL DEFAULT 'NOT_SEEN'
                       CHECK (state IN ('NOT_SEEN', 'PRESENTED', 'ATTEMPTED', 'SUCCESS_INDEPENDENT',
                                        'SUCCESS_WITH_HELP', 'FAILED', 'DETOURED', 'RETRY_PRESENTED', 'SKIPPED')),
    first_seen_at      timestamptz,
    first_attempted_at timestamptz,
    last_updated_at    timestamptz NOT NULL DEFAULT now(),
    independent_success boolean,
    help_level_used    integer NOT NULL DEFAULT 0 CHECK (help_level_used BETWEEN 0 AND 5),
    attempt_count      integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_response_text text,
    last_evaluation    jsonb,
    evidence           jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (solve_attempt_id, solution_step_id),
    -- Level-5 (full reveal) or any help is never independent mastery evidence (runtime_extension/09 §2).
    CONSTRAINT step_state_independent_requires_no_help
        CHECK (independent_success IS NOT TRUE OR help_level_used = 0)
);

CREATE TABLE IF NOT EXISTS learner.event (
    event_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id       uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    solve_attempt_id uuid REFERENCES learner.solve_attempt ON DELETE CASCADE,
    event_type       text NOT NULL CHECK (event_type IN (
        'ATTEMPT_STARTED', 'PROBLEM_VIEWED',
        'STEP_PRESENTED', 'STEP_RESPONSE_SUBMITTED', 'STEP_EVALUATED',
        'STEP_COMPLETED_INDEPENDENTLY', 'STEP_COMPLETED_WITH_HELP', 'STEP_FAILED', 'STEP_SKIPPED',
        'HINT_REQUESTED', 'HINT_PRESENTED',
        'GAP_HYPOTHESIS_CREATED', 'GAP_HYPOTHESIS_CONFIRMED', 'GAP_HYPOTHESIS_REJECTED',
        'RECOVERY_PLAN_CREATED', 'RECOVERY_ITEM_PRESENTED', 'RECOVERY_ITEM_SUBMITTED',
        'RECOVERY_ITEM_EVALUATED', 'RECOVERY_PLAN_COMPLETED', 'RECOVERY_PLAN_ABORTED',
        'RETURNED_TO_ORIGINAL_STEP', 'RETURNED_TO_ORIGINAL_PROBLEM',
        'ATTEMPT_SUBMITTED', 'ATTEMPT_COMPLETED')),
    event_time       timestamptz NOT NULL DEFAULT clock_timestamp(),
    actor_type       text NOT NULL CHECK (actor_type IN ('STUDENT', 'TUTOR', 'AGENT', 'SYSTEM', 'ADMIN')),
    solution_step_id text REFERENCES pedagogy.solution_step,
    payload          jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- Client Idempotency-Key of the request that produced this event (traceability), scoped per student.
    idempotency_key  text,
    UNIQUE (student_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS event_attempt_idx ON learner.event (solve_attempt_id, event_time);
CREATE INDEX IF NOT EXISTS event_student_idx ON learner.event (student_id, event_time DESC);

-- Events are append-only (runtime_extension/08 §3). Student erasure is a soft delete (MST-08), so
-- blocking UPDATE/DELETE never blocks the normal lifecycle; a hard delete of a student profile
-- must disable this trigger explicitly as an audited admin action.
CREATE OR REPLACE FUNCTION learner.event_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'learner.event is append-only (% rejected)', TG_OP USING ERRCODE = 'restrict_violation';
END $$;
DROP TRIGGER IF EXISTS event_append_only ON learner.event;
CREATE TRIGGER event_append_only BEFORE UPDATE OR DELETE ON learner.event
    FOR EACH ROW EXECUTE FUNCTION learner.event_append_only();

-- Idempotent replay store (runtime_extension/16 §4). The event log is append-only, so the response
-- returned for a mutation is kept here; a retried request with the same key gets the same response,
-- and the same key with a different request body is rejected (request_hash mismatch).
CREATE TABLE IF NOT EXISTS learner.idempotency_record (
    student_id      uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 200),
    operation       text NOT NULL,
    request_hash    text NOT NULL,
    response        jsonb NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS tutor.runtime_state (
    student_id               uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    solve_attempt_id         uuid NOT NULL REFERENCES learner.solve_attempt ON DELETE CASCADE,
    current_mode             text NOT NULL DEFAULT 'SOLVING'
                             CHECK (current_mode IN ('SOLVING', 'DIAGNOSING', 'RECOVERY', 'REVIEW', 'COMPLETED')),
    current_problem_id       uuid NOT NULL REFERENCES core.problem,
    current_step_id          text REFERENCES pedagogy.solution_step,
    current_recovery_plan_id uuid,
    last_agent_turn_id       text,
    state_version            bigint NOT NULL DEFAULT 1 CHECK (state_version >= 1),
    updated_at               timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, solve_attempt_id)
);

-- Transactional outbox (runtime_extension/16): canonical state + outbox row in one transaction;
-- consumers (graph/embedding/analytics) record processing so a replay is safe.
CREATE TABLE IF NOT EXISTS pipeline.outbox_event (
    outbox_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      text NOT NULL,
    aggregate_type  text NOT NULL,
    aggregate_id    text NOT NULL,
    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS outbox_event_created_idx ON pipeline.outbox_event (created_at);

CREATE TABLE IF NOT EXISTS pipeline.outbox_consumption (
    outbox_event_id uuid NOT NULL REFERENCES pipeline.outbox_event ON DELETE CASCADE,
    consumer_name   text NOT NULL,
    processed_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (outbox_event_id, consumer_name)
);
