-- 015 — v2 Phase 10: recovery plans (runtime_extension/11, 03, 13, 14 §7–9) and learning-item
-- automatic approval provenance.
--
-- A recovery plan is a persisted detour from one (solve attempt, solution step): a short ordered
-- list of items (theory/worked example, approved learning items, a transfer item, then the
-- return to the exact origin step). The plan is written before execution; the runtime never keeps
-- it only in agent memory. A plan ends COMPLETED (mastery policy met), EXHAUSTED (items ran out
-- without mastery; the student still returns), ABORTED (student/tutor left early) or SUPERSEDED.
-- A prerequisite branch is a child plan (parent_recovery_plan_id); the parent waits SUSPENDED.
--
-- Idempotent: safe to re-run.

-- Learning items: record *how* an item was approved (automatic now, human later).
ALTER TABLE pedagogy.learning_item ADD COLUMN IF NOT EXISTS approval_method text;
ALTER TABLE pedagogy.learning_item ADD COLUMN IF NOT EXISTS approved_at timestamptz;
ALTER TABLE pedagogy.learning_item DROP CONSTRAINT IF EXISTS learning_item_approval_method_check;
ALTER TABLE pedagogy.learning_item ADD CONSTRAINT learning_item_approval_method_check
    CHECK (approval_method IS NULL OR approval_method IN ('automatic', 'human'));
CREATE INDEX IF NOT EXISTS learning_item_skill_visible_idx
    ON pedagogy.learning_item (target_skill_node_id, transformation_type) WHERE student_visible;
CREATE INDEX IF NOT EXISTS learning_item_subconcept_visible_idx
    ON pedagogy.learning_item (target_subconcept_node_id, transformation_type) WHERE student_visible;

-- Optional AI re-ranking of a rules diagnosis (DIAGNOSIS_LLM_RERANK=1). The rules rank in
-- knowledge_gap.rank is never overwritten; the model's order + rationale is stored alongside.
ALTER TABLE pedagogy.gap_diagnosis ADD COLUMN IF NOT EXISTS ai_rerank jsonb;

CREATE TABLE IF NOT EXISTS pedagogy.recovery_plan (
    recovery_plan_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id               uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    solve_attempt_id         uuid NOT NULL REFERENCES learner.solve_attempt ON DELETE CASCADE,
    origin_problem_id        uuid NOT NULL REFERENCES core.problem,
    origin_step_id           text NOT NULL REFERENCES pedagogy.solution_step,
    gap_diagnosis_id         uuid REFERENCES pedagogy.gap_diagnosis ON DELETE SET NULL,
    knowledge_gap_id         uuid REFERENCES pedagogy.knowledge_gap ON DELETE SET NULL,
    parent_recovery_plan_id  uuid REFERENCES pedagogy.recovery_plan ON DELETE CASCADE,
    trigger                  text NOT NULL CHECK (trigger IN ('DIAGNOSIS', 'STUDENT_REQUEST', 'TUTOR', 'BRANCH')),
    target_skill_id          text,           -- taxonomy skill code (solution_step.skill_node_id)
    target_subconcept_id     text,
    target_label             text,
    status                   text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN (
        'ACTIVE', 'SUSPENDED', 'COMPLETED', 'EXHAUSTED', 'ABORTED', 'SUPERSEDED')),
    current_item_ordinal     integer,
    mastery_policy           jsonb NOT NULL DEFAULT
        '{"independent_successes_required": 2, "transfer_success_required": true, "max_help_level_on_final": 1}'::jsonb,
    outcome                  jsonb NOT NULL DEFAULT '{}'::jsonb,
    planner_version          text NOT NULL,
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now(),
    ended_at                 timestamptz
);
-- At most one running (ACTIVE) plan per solve attempt; a suspended parent waits for its branch.
CREATE UNIQUE INDEX IF NOT EXISTS recovery_plan_one_active_idx
    ON pedagogy.recovery_plan (solve_attempt_id) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS recovery_plan_student_idx ON pedagogy.recovery_plan (student_id, created_at DESC);

CREATE TABLE IF NOT EXISTS pedagogy.recovery_plan_item (
    recovery_plan_item_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recovery_plan_id      uuid NOT NULL REFERENCES pedagogy.recovery_plan ON DELETE CASCADE,
    ordinal               integer NOT NULL CHECK (ordinal >= 1),
    stage                 text NOT NULL CHECK (stage IN (
        'FOUNDATION', 'RECOGNITION', 'ISOLATED_EXECUTION', 'GUIDED_APPLICATION', 'TRANSFER',
        'RETURN_TO_STEP')),
    item_kind             text NOT NULL CHECK (item_kind IN ('LEARNING_ITEM', 'THEORY', 'RETURN')),
    learning_item_id      text REFERENCES pedagogy.learning_item,
    worked_step_id        text REFERENCES pedagogy.solution_step,  -- THEORY worked example (other problem)
    is_transfer           boolean NOT NULL DEFAULT false,
    required              boolean NOT NULL DEFAULT true,
    status                text NOT NULL DEFAULT 'PENDING' CHECK (status IN (
        'PENDING', 'PRESENTED', 'PASSED', 'FAILED', 'SKIPPED')),
    tries                 integer NOT NULL DEFAULT 0,
    independent_success   boolean,
    last_response         jsonb,
    last_result           jsonb,
    added_reason          text NOT NULL DEFAULT 'PLANNED',
    presented_at          timestamptz,
    completed_at          timestamptz,
    UNIQUE (recovery_plan_id, ordinal),
    CHECK ((item_kind = 'LEARNING_ITEM') = (learning_item_id IS NOT NULL))
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'solve_attempt_recovery_plan_fk') THEN
        ALTER TABLE learner.solve_attempt ADD CONSTRAINT solve_attempt_recovery_plan_fk
            FOREIGN KEY (recovery_plan_id) REFERENCES pedagogy.recovery_plan ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'runtime_state_recovery_plan_fk') THEN
        ALTER TABLE tutor.runtime_state ADD CONSTRAINT runtime_state_recovery_plan_fk
            FOREIGN KEY (current_recovery_plan_id) REFERENCES pedagogy.recovery_plan ON DELETE SET NULL;
    END IF;
END $$;

-- Events: add the branch/exhausted transitions to the 014 list.
ALTER TABLE learner.event DROP CONSTRAINT IF EXISTS event_event_type_check;
ALTER TABLE learner.event ADD CONSTRAINT event_event_type_check CHECK (event_type IN (
    'ATTEMPT_STARTED', 'PROBLEM_VIEWED',
    'STEP_PRESENTED', 'STEP_RESPONSE_SUBMITTED', 'STEP_EVALUATED',
    'STEP_COMPLETED_INDEPENDENTLY', 'STEP_COMPLETED_WITH_HELP', 'STEP_FAILED', 'STEP_SKIPPED',
    'HINT_REQUESTED', 'HINT_PRESENTED',
    'GAP_DIAGNOSED',
    'GAP_HYPOTHESIS_CREATED', 'GAP_HYPOTHESIS_CONFIRMED', 'GAP_HYPOTHESIS_REJECTED',
    'GAP_HYPOTHESIS_RESOLVED',
    'RECOVERY_PLAN_CREATED', 'RECOVERY_ITEM_PRESENTED', 'RECOVERY_ITEM_SUBMITTED',
    'RECOVERY_ITEM_EVALUATED', 'RECOVERY_PLAN_COMPLETED', 'RECOVERY_PLAN_ABORTED',
    'RECOVERY_PLAN_BRANCHED', 'RECOVERY_PLAN_EXHAUSTED',
    'RETURNED_TO_ORIGINAL_STEP', 'RETURNED_TO_ORIGINAL_PROBLEM',
    'ATTEMPT_SUBMITTED', 'ATTEMPT_COMPLETED'));
