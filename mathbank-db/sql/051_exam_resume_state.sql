-- Durable in-progress exam state (requirements/64): save the current question and
-- unsubmitted drafts separately from quiz.response, which remains the graded answer.
ALTER TABLE quiz.paper
    ADD COLUMN IF NOT EXISTS resume_question_ordinal integer
        CHECK (resume_question_ordinal IS NULL OR resume_question_ordinal > 0);

CREATE TABLE IF NOT EXISTS quiz.response_draft (
    quiz_id uuid NOT NULL REFERENCES quiz.paper(quiz_id) ON DELETE CASCADE,
    question_id uuid NOT NULL REFERENCES quiz.question(question_id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES learner.student_profile(student_id),
    raw_response jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (quiz_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_quiz_response_draft_student
    ON quiz.response_draft(student_id, updated_at DESC);
