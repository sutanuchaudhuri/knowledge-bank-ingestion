BEGIN;

CREATE TABLE IF NOT EXISTS learner.pedagogy_feedback (
    feedback_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    problem_id uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    topic text NOT NULL CHECK (length(btrim(topic)) BETWEEN 1 AND 200),
    reason text NOT NULL CHECK (length(btrim(reason)) BETWEEN 10 AND 2000),
    status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'RESOLVED', 'DISMISSED')),
    review_note text CHECK (length(btrim(review_note)) BETWEEN 10 AND 2000),
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    UNIQUE (student_id, problem_id, topic, reason),
    CHECK ((status = 'PENDING' AND reviewed_at IS NULL AND review_note IS NULL)
        OR (status <> 'PENDING' AND reviewed_at IS NOT NULL AND review_note IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS pedagogy_feedback_pending_idx
    ON learner.pedagogy_feedback(status, created_at);

COMMIT;
