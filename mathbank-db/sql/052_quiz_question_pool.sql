-- requirements/64 (continued): a reusable, ever-growing pool of critic-approved,
-- corpus-inspired mock-exam questions WITH full solutions. mathbank-exam-agent checks
-- this pool first for a near-identical request (same style/question type/difficulty and
-- an overlapping concept or a similar topic phrase) and only drafts fresh questions for
-- the slots the pool can't fill; every freshly approved question is written back here,
-- so the pool keeps expanding with use. Additive only — no existing row/column/constraint
-- semantics change.

CREATE TABLE IF NOT EXISTS quiz.question_pool (
    pool_question_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- sha256 of the whitespace/case-normalized prompt_text: the same question is never
    -- pooled twice, even if two parallel generations happen to draft it.
    content_hash text NOT NULL UNIQUE,
    style text NOT NULL,
    question_type text NOT NULL CHECK (question_type IN ('MCQ', 'FREE_TEXT', 'PROOF')),
    difficulty_band text,
    -- Lower-cased, whitespace-collapsed topic phrase from the request (e.g.
    -- "combinatorics"), matched with pg_trgm similarity for "almost the same" requests.
    topic_key text NOT NULL DEFAULT '',
    concept_slugs text[] NOT NULL DEFAULT '{}',
    technique_slugs text[] NOT NULL DEFAULT '{}',
    -- The full finalize_paper question payload (prompt, options, correct_answer,
    -- solution_text/steps, key_insight, option_explanations, inspiration_sources, ...),
    -- so a pooled question can be copied into a new paper with zero LLM calls.
    question jsonb NOT NULL,
    source_quiz_id uuid REFERENCES quiz.paper(quiz_id) ON DELETE SET NULL,
    generated_by text,
    times_served integer NOT NULL DEFAULT 0,
    last_served_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_question_pool_lookup
    ON quiz.question_pool (style, question_type, difficulty_band);
CREATE INDEX IF NOT EXISTS idx_question_pool_concepts
    ON quiz.question_pool USING gin (concept_slugs);
CREATE INDEX IF NOT EXISTS idx_question_pool_topic_trgm
    ON quiz.question_pool USING gin (topic_key gin_trgm_ops);

-- Which pool entry a paper's question was served from (or written back to) — used to
-- never serve a student the same pooled question twice.
ALTER TABLE quiz.question
    ADD COLUMN IF NOT EXISTS pool_question_id uuid
        REFERENCES quiz.question_pool(pool_question_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_quiz_question_pool_question
    ON quiz.question (pool_question_id) WHERE pool_question_id IS NOT NULL;

-- New progress phase for the pool lookup step.
ALTER TABLE quiz.generation_event DROP CONSTRAINT IF EXISTS generation_event_phase_check;
ALTER TABLE quiz.generation_event ADD CONSTRAINT generation_event_phase_check CHECK (phase IN (
    'INTAKE', 'TOPIC_RESOLVE', 'DIFFICULTY_SIGNAL', 'POOL_LOOKUP', 'DRAFT_QUESTION', 'CRITIC_REVIEW',
    'AGGREGATE_DIVERSITY_CHECK', 'AGGREGATE_FIX', 'PERSIST', 'DONE', 'FAILED'
));
