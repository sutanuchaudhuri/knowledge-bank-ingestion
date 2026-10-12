BEGIN;

ALTER TABLE learner.pedagogy_feedback
    ADD COLUMN IF NOT EXISTS feedback_type text NOT NULL DEFAULT 'RETRIEVAL_IRRELEVANT'
        CHECK (feedback_type='RETRIEVAL_IRRELEVANT'),
    ADD COLUMN IF NOT EXISTS audit_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(audit_snapshot)='object'),
    ADD COLUMN IF NOT EXISTS retrieval_verdict text NOT NULL DEFAULT 'UNCLASSIFIED'
        CHECK (retrieval_verdict IN ('UNCLASSIFIED','IRRELEVANT','RELEVANT')),
    ADD COLUMN IF NOT EXISTS error_kind text NOT NULL DEFAULT 'UNCLASSIFIED'
        CHECK (error_kind IN ('UNCLASSIFIED','METADATA','RETRIEVAL','INSUFFICIENT_EVIDENCE'));

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE
        conrelid='learner.pedagogy_feedback'::regclass AND conname='feedback_negative_review_check') THEN
        ALTER TABLE learner.pedagogy_feedback
            ADD CONSTRAINT feedback_negative_review_check
            CHECK (retrieval_verdict='UNCLASSIFIED' OR
                   (status <> 'PENDING' AND review_note IS NOT NULL));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS pedagogy_feedback_reviewed_negative_idx
    ON learner.pedagogy_feedback(topic,problem_id)
    WHERE retrieval_verdict='IRRELEVANT' AND status='RESOLVED';

COMMIT;
