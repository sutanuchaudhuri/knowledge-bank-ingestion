-- 014 — v2 Phase 9: step-level gap diagnosis (runtime_extension/10, 13_ATTEMPT_DIAGNOSIS).
--
-- A diagnosis is run for one (solve attempt, current step) and persists several ranked
-- knowledge-gap hypotheses. Hypotheses are never overwritten or deleted by the runtime: only
-- their status moves UNRESOLVED -> CONFIRMED / REJECTED, CONFIRMED -> RESOLVED, each with a
-- learner.event. Mastery is never set from a diagnosis. Re-running with identical evidence
-- (same fingerprint) returns the existing diagnosis instead of inserting a duplicate.
--
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS pedagogy.gap_diagnosis (
    gap_diagnosis_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id           uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    solve_attempt_id     uuid NOT NULL REFERENCES learner.solve_attempt ON DELETE CASCADE,
    solution_step_id     text NOT NULL REFERENCES pedagogy.solution_step,
    trigger              text NOT NULL CHECK (trigger IN ('AUTO', 'STUDENT_REQUEST', 'TUTOR')),
    recommended_action   text NOT NULL CHECK (recommended_action IN (
        'RETRY_WITH_HINT', 'DIAGNOSTIC_PROBE', 'RECOVERY_DETOUR')),
    evidence_fingerprint text NOT NULL,
    evidence             jsonb NOT NULL DEFAULT '{}'::jsonb,
    probes               jsonb NOT NULL DEFAULT '[]'::jsonb,
    diagnoser_version    text NOT NULL,
    created_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (solve_attempt_id, solution_step_id, evidence_fingerprint)
);
CREATE INDEX IF NOT EXISTS gap_diagnosis_student_idx ON pedagogy.gap_diagnosis (student_id, created_at DESC);

CREATE TABLE IF NOT EXISTS pedagogy.knowledge_gap (
    knowledge_gap_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gap_diagnosis_id      uuid NOT NULL REFERENCES pedagogy.gap_diagnosis ON DELETE CASCADE,
    student_id            uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    solve_attempt_id      uuid NOT NULL REFERENCES learner.solve_attempt ON DELETE CASCADE,
    solution_step_id      text NOT NULL REFERENCES pedagogy.solution_step,
    rank                  integer NOT NULL CHECK (rank >= 1),
    failure_location      text NOT NULL CHECK (failure_location IN (
        'CONCEPT', 'SUBCONCEPT', 'SKILL', 'TECHNIQUE', 'PREREQUISITE', 'REPRESENTATION')),
    failure_mode          text NOT NULL CHECK (failure_mode IN (
        'NOT_RECOGNIZED', 'MISUNDERSTOOD', 'THEOREM_NOT_RECALLED', 'WRONG_THEOREM_SELECTED',
        'CANNOT_EXECUTE', 'PROOF_CONNECTION_MISSING', 'DIAGRAM_MISREAD', 'ALGEBRA_BREAKDOWN',
        'CASE_MISSED', 'OVERCOMPLICATED', 'CARELESS')),
    target_concept_id     text,           -- taxonomy node id, e.g. GEO.C01
    target_subconcept_id  text,           -- e.g. GEO.C01.S01
    target_skill_id       text,           -- solution_step.skill_id (taxonomy skill code)
    target_skill_node_id  uuid,           -- knowledge.skill (logical link, not enforced)
    target_label          text,
    source_step_id        text REFERENCES pedagogy.solution_step,  -- prerequisite step that suggested it
    confidence            numeric(4, 3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    evidence              jsonb NOT NULL DEFAULT '{}'::jsonb,
    status                text NOT NULL DEFAULT 'UNRESOLVED' CHECK (status IN (
        'UNRESOLVED', 'CONFIRMED', 'REJECTED', 'RESOLVED')),
    status_reason         text,
    created_at            timestamptz NOT NULL DEFAULT now(),
    status_changed_at     timestamptz,
    resolved_at           timestamptz,
    UNIQUE (gap_diagnosis_id, rank)
);
CREATE INDEX IF NOT EXISTS knowledge_gap_open_idx
    ON pedagogy.knowledge_gap (student_id, target_skill_id) WHERE status IN ('UNRESOLVED', 'CONFIRMED');
CREATE INDEX IF NOT EXISTS knowledge_gap_attempt_idx ON pedagogy.knowledge_gap (solve_attempt_id);

-- Add GAP_HYPOTHESIS_RESOLVED to the learner.event type list (012 lacked it).
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
    'RETURNED_TO_ORIGINAL_STEP', 'RETURNED_TO_ORIGINAL_PROBLEM',
    'ATTEMPT_SUBMITTED', 'ATTEMPT_COMPLETED'));
