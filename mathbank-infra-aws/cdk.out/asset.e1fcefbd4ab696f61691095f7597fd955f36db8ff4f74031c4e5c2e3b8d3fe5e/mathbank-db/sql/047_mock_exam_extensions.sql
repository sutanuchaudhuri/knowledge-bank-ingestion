-- requirements/64 EXM-2: additive-only extensions to requirements/53's quiz.* schema
-- (migration 042) for the AWS Bedrock mock-exam agent (mathbank-exam-agent). Zero
-- existing row, column, or constraint from migration 042 is altered or dropped — every
-- requirements/53 code path continues to work unchanged against agent_framework =
-- 'OPENAI_DIRECT', exam_mode = false rows exactly as before.

ALTER TABLE quiz.paper
    ADD COLUMN IF NOT EXISTS exam_mode boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS time_limit_seconds integer,
    ADD COLUMN IF NOT EXISTS agent_framework text NOT NULL DEFAULT 'OPENAI_DIRECT'
        CHECK (agent_framework IN ('OPENAI_DIRECT', 'STRANDS_BEDROCK'));

-- Full generator<->critic revision history (every round, not just the final approved
-- version) — requirements/64 §4's "audit, don't just store the final state" decision,
-- mirroring record_audit_event's use elsewhere in this repo. Per-question
-- difficulty_band (migration 042 only has one difficulty_band per *paper*, not per
-- question) is needed for the diagnosis agent's pacing analysis (requirements/64 §7 —
-- "flagging questions that took disproportionately long relative to their difficulty
-- band").
ALTER TABLE quiz.question
    ADD COLUMN IF NOT EXISTS revision_log jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS difficulty_band text;

-- One holistic post-exam report per paper (requirements/64 §7) — deliberately separate
-- from quiz.response.grading_feedback, which is per-question, not a synthesized,
-- paper-level diagnosis.
CREATE TABLE IF NOT EXISTS quiz.exam_diagnosis (
    quiz_id uuid PRIMARY KEY REFERENCES quiz.paper(quiz_id) ON DELETE CASCADE,
    time_management_verdict text NOT NULL,
    pacing_notes jsonb NOT NULL DEFAULT '[]'::jsonb,
    reasoning_guidance jsonb NOT NULL DEFAULT '[]'::jsonb,
    improvement_areas jsonb NOT NULL DEFAULT '[]'::jsonb,
    generated_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
