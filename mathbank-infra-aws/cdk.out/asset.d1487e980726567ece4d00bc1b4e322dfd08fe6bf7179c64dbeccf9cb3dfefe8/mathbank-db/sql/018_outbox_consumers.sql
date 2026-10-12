-- 018 — Outbox consumers, analytics rollup, projection requests, stale-attempt abandonment.
-- Spec: runtime_extension/08 (student events: lifecycle, retention), 16 (outbox consumers, idempotency).
-- Plan: requirements/26_GEOMETRY_RUNTIME_COMPLETION_PLAN.md (WP4).
--
-- Consumers are idempotent through pipeline.outbox_consumption (PK event + consumer): each event is
-- handled and its consumption row written in the same transaction, so a replay is a no-op.
-- Idempotent: safe to re-run.

-- 1. Event vocabulary: ATTEMPT_ABANDONED (stale-attempt job). The full list repeats 015's CHECK.
ALTER TABLE learner.event DROP CONSTRAINT IF EXISTS event_event_type_check;
ALTER TABLE learner.event ADD CONSTRAINT event_event_type_check CHECK (event_type IN (
    'ATTEMPT_STARTED', 'PROBLEM_VIEWED',
    'STEP_PRESENTED', 'STEP_RESPONSE_SUBMITTED', 'STEP_EVALUATED',
    'STEP_COMPLETED_INDEPENDENTLY', 'STEP_COMPLETED_WITH_HELP', 'STEP_FAILED', 'STEP_SKIPPED',
    'HINT_REQUESTED', 'HINT_PRESENTED',
    'GAP_DIAGNOSED', 'GAP_HYPOTHESIS_CREATED', 'GAP_HYPOTHESIS_CONFIRMED', 'GAP_HYPOTHESIS_REJECTED',
    'GAP_HYPOTHESIS_RESOLVED',
    'RECOVERY_PLAN_CREATED', 'RECOVERY_ITEM_PRESENTED', 'RECOVERY_ITEM_SUBMITTED',
    'RECOVERY_ITEM_EVALUATED', 'RECOVERY_PLAN_COMPLETED', 'RECOVERY_PLAN_ABORTED',
    'RECOVERY_PLAN_BRANCHED', 'RECOVERY_PLAN_EXHAUSTED',
    'RETURNED_TO_ORIGINAL_STEP', 'RETURNED_TO_ORIGINAL_PROBLEM',
    'ATTEMPT_SUBMITTED', 'ATTEMPT_COMPLETED', 'ATTEMPT_ABANDONED'));

CREATE INDEX IF NOT EXISTS outbox_event_type_idx ON pipeline.outbox_event (event_type, created_at);

-- 2. Analytics consumer target: per-student, per-UTC-day counters (a mutable, rebuildable cache —
--    learner.event stays the source of truth).
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE TABLE IF NOT EXISTS analytics.learner_daily_activity (
    student_id               uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    activity_date            date NOT NULL,
    attempts_started         integer NOT NULL DEFAULT 0,
    attempts_completed       integer NOT NULL DEFAULT 0,
    attempts_abandoned       integer NOT NULL DEFAULT 0,
    steps_evaluated          integer NOT NULL DEFAULT 0,
    steps_succeeded          integer NOT NULL DEFAULT 0,
    gaps_diagnosed           integer NOT NULL DEFAULT 0,
    knowledge_gaps_created   integer NOT NULL DEFAULT 0,
    recovery_plans_created   integer NOT NULL DEFAULT 0,
    recovery_plans_completed integer NOT NULL DEFAULT 0,
    updated_at               timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, activity_date)
);

-- 3. Projection consumer target: content changes request graph / embedding refreshes. Operators (or
--    the admin import UI) drain them with the existing projectors; nothing dual-writes PG + graph.
CREATE TABLE IF NOT EXISTS pipeline.projection_request (
    projection_request_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    target                 text NOT NULL CHECK (target IN ('GRAPH_TEXTBOOK_STEPS', 'STEP_EMBEDDINGS',
                                                           'LEARNING_ITEM_EMBEDDINGS', 'GRAPH_LEARNING_ITEMS')),
    scope_type             text NOT NULL CHECK (scope_type IN ('BOOK', 'PACKAGE', 'PROBLEM', 'STEP', 'LEARNING_ITEM')),
    scope_id               text NOT NULL,
    reason                 text NOT NULL,
    source_outbox_event_id uuid REFERENCES pipeline.outbox_event ON DELETE SET NULL,
    status                 text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'DONE', 'CANCELLED')),
    requested_at           timestamptz NOT NULL DEFAULT now(),
    completed_at           timestamptz,
    completed_by           text
);
-- At most one open request per target+scope: repeated changes coalesce.
CREATE UNIQUE INDEX IF NOT EXISTS projection_request_open_uq
    ON pipeline.projection_request (target, scope_type, scope_id) WHERE status = 'PENDING';
