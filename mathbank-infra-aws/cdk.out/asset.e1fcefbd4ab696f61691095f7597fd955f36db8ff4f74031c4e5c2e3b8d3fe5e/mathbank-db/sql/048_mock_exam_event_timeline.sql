-- requirements/64 (continued): per-option MCQ explanations and a full response-event
-- timeline for the exam-taking UI (mathbank-exam-web) — additive-only, same convention
-- as migration 047.

-- "Why a certain answer does not work" for every MCQ option, not just the correct one.
ALTER TABLE quiz.question
    ADD COLUMN IF NOT EXISTS option_explanations jsonb NOT NULL DEFAULT '{}'::jsonb;

-- Append-only interaction timeline per question — "option 1 chosen at time T1, skipped
-- at time T2" is literally this table, not a derived summary. Deliberately separate
-- from quiz.response (the final, one-row-per-question answer quiz_runtime.py already
-- grades against) — this is raw telemetry, never used for grading itself.
CREATE TABLE IF NOT EXISTS quiz.response_event (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id uuid NOT NULL REFERENCES quiz.paper(quiz_id) ON DELETE CASCADE,
    question_id uuid NOT NULL REFERENCES quiz.question(question_id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES learner.student_profile(student_id),
    event_type text NOT NULL
        CHECK (event_type IN ('VIEW', 'SELECT_OPTION', 'DESELECT_OPTION', 'TEXT_CHANGE', 'SKIP', 'FINAL_SUBMIT')),
    option_key text,
    client_timestamp_ms bigint,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_response_event_quiz_question
    ON quiz.response_event(quiz_id, question_id, created_at);
