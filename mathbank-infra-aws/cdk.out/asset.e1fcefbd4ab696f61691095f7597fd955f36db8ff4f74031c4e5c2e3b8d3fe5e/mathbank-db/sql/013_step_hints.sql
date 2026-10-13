-- 013 — v2 Phase 8: step evaluation + progressive hints.
--
-- Hints for levels 1–4 are generated once per (step, level, prompt version) from the canonical step
-- and shared by every student, so the paid call happens at most once per hint. Level 5 (full
-- reveal) is the canonical step text itself and is never stored here.
-- Evaluations are not a separate table: evidence lives on learner.attempt_step_state.last_evaluation
-- and in the append-only STEP_EVALUATED event payload (012).
--
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS pedagogy.step_hint (
    solution_step_id text NOT NULL REFERENCES pedagogy.solution_step ON DELETE CASCADE,
    hint_level       integer NOT NULL CHECK (hint_level BETWEEN 1 AND 4),
    prompt_version   text NOT NULL,
    hint_text        text NOT NULL CHECK (length(hint_text) > 0),
    model            text NOT NULL,
    leak_checked     boolean NOT NULL DEFAULT true,
    created_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (solution_step_id, hint_level, prompt_version)
);
