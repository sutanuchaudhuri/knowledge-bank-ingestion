-- 017 — Step-level technique tags (NYI-3, runtime_extension/06 Step-[:USES_TECHNIQUE], 07 technique_ids).
--
-- The Prasolov packages tag techniques per *problem* (problem_enrichment.technique_ids), not per step.
-- This table stores derived step → technique assertions. Provenance is kept per row:
--   RULE_STEP_TEXT_IN_PROBLEM  step text names one of the problem's own techniques (deterministic)
--   RULE_STEP_TEXT_NAMED       step text names a specific theorem/method (Menelaus, inversion …)
--   RULE_STEP_FORMULA          step formula has the signature of a technique (e.g. R² − OX²)
--   LLM                        model classification over a closed candidate list (opt-in, paid)
--   RUNTIME                    filled while tutoring (non-textbook corpora; planned)
--   HUMAN                      admin decision; never overwritten by a re-derivation
-- Everything is auto-approved for now (approval_method = 'automatic'); readers filter on
-- review_status = 'APPROVED' and may threshold on confidence.
--
-- Non-Prasolov corpora have no pedagogy.solution_step rows, so they have no rows here (NULL by design).
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS pedagogy.solution_step_technique (
    solution_step_id   text NOT NULL REFERENCES pedagogy.solution_step ON DELETE CASCADE,
    technique_node_id  text NOT NULL REFERENCES pedagogy.taxonomy_node,
    confidence         numeric(3, 2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    source_type        text NOT NULL CHECK (source_type IN (
                           'RULE_STEP_TEXT_IN_PROBLEM', 'RULE_STEP_TEXT_NAMED', 'RULE_STEP_FORMULA',
                           'LLM', 'RUNTIME', 'HUMAN')),
    evidence           text,                 -- matched phrase / model rationale (no student data)
    derivation_version text NOT NULL,        -- e.g. rules-v1, llm-v1:<model>
    review_status      text NOT NULL DEFAULT 'APPROVED'
                           CHECK (review_status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED')),
    approval_method    text CHECK (approval_method IS NULL OR approval_method IN ('automatic', 'human')),
    approved_at        timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (solution_step_id, technique_node_id)
);

CREATE INDEX IF NOT EXISTS solution_step_technique_technique_idx
    ON pedagogy.solution_step_technique (technique_node_id) WHERE review_status = 'APPROVED';

-- Steps the derivation looked at, including those it could not tag, so coverage and the LLM
-- backlog are measurable without re-running the rules.
CREATE TABLE IF NOT EXISTS pedagogy.solution_step_technique_run (
    solution_step_id   text NOT NULL REFERENCES pedagogy.solution_step ON DELETE CASCADE,
    derivation_version text NOT NULL,
    outcome            text NOT NULL CHECK (outcome IN ('TAGGED', 'NO_MATCH', 'NO_PROBLEM_TECHNIQUE')),
    candidate_ids      text[] NOT NULL DEFAULT '{}',
    created_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (solution_step_id, derivation_version)
);
