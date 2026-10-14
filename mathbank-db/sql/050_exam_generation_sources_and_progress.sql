-- requirements/64 (continued): parallel question generation needs (1) multiple,
-- explicitly-noted inspiration sources per question (not just the single
-- inspired_by_problem_id column migration 042 already has — a drafted question can
-- genuinely draw on 1-3 real corpus problems at once, each contributing a different,
-- separately-cited idea) and (2) a durable, pollable progress log for the generation
-- job itself, so the web UI can show live step-by-step status while mathbank-exam-agent
-- works through drafting + critiquing + an aggregate diversity pass — additive only,
-- same convention as every migration since 042.

-- Replaces nothing: quiz.question.inspired_by_problem_id (migration 042) still gets the
-- single "primary" source for any existing code that reads it; this junction table adds
-- the full, ranked set (rank 1 = primary = the same row inspired_by_problem_id points
-- at) plus a per-source note explaining what was actually borrowed/changed, since
-- "inspired by, never copied" is meaningless to a student without saying *how*.
CREATE TABLE IF NOT EXISTS quiz.question_source (
    question_id uuid NOT NULL REFERENCES quiz.question(question_id) ON DELETE CASCADE,
    problem_id uuid NOT NULL REFERENCES core.problem(problem_id),
    rank smallint NOT NULL CHECK (rank BETWEEN 1 AND 5),
    note text NOT NULL DEFAULT '',
    PRIMARY KEY (question_id, problem_id)
);
CREATE INDEX IF NOT EXISTS idx_question_source_question ON quiz.question_source(question_id, rank);

-- Append-only generation-progress log, one row per meaningful step (not per LLM token —
-- this is "drafting question 3 of 10" granularity, not a token stream). Deliberately a
-- *paper-scoped* table, not reusing quiz.response_event (migration 048), which is
-- exam-TAKING telemetry with a completely different lifecycle (after the paper exists,
-- keyed by question_id/student_id) — this table's rows exist entirely *before* the
-- paper's own questions are inserted, so it cannot be keyed by question_id at all.
CREATE TABLE IF NOT EXISTS quiz.generation_event (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id uuid NOT NULL REFERENCES quiz.paper(quiz_id) ON DELETE CASCADE,
    ordinal integer NOT NULL,
    phase text NOT NULL CHECK (phase IN (
        'INTAKE', 'TOPIC_RESOLVE', 'DIFFICULTY_SIGNAL', 'DRAFT_QUESTION', 'CRITIC_REVIEW',
        'AGGREGATE_DIVERSITY_CHECK', 'AGGREGATE_FIX', 'PERSIST', 'DONE', 'FAILED'
    )),
    status text NOT NULL CHECK (status IN ('STARTED', 'DONE', 'FAILED')),
    question_ordinal integer,
    detail text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (quiz_id, ordinal)
);
CREATE INDEX IF NOT EXISTS idx_generation_event_quiz ON quiz.generation_event(quiz_id, ordinal);

-- Complexity/difficulty measurement for generated questions (same session, folded in
-- here rather than a separate migration) — mirrors the real-corpus precedent already
-- established by pedagogy.problem_enrichment.solution_step_count/technique_ids
-- (migration 010), but computed from a generated question's own structured solution
-- rather than source-material metadata, since a freshly drafted solution has no
-- pre-existing pedagogy.solution_part breakdown to count.
ALTER TABLE quiz.solution
    ADD COLUMN IF NOT EXISTS solution_steps jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS step_count integer;

-- A snapshot of the computed signals the critic was actually given as difficulty
-- evidence (step_count, concept_count, technique_count, solution_length_chars) — kept
-- on quiz.question itself (not just derivable from quiz.solution/question_concept at
-- query time) so the review UI can show "6 steps · 3 techniques · Hard" without a
-- second round of joins/aggregation, and so it's auditable alongside revision_log.
ALTER TABLE quiz.question
    ADD COLUMN IF NOT EXISTS complexity_signals jsonb NOT NULL DEFAULT '{}'::jsonb;

