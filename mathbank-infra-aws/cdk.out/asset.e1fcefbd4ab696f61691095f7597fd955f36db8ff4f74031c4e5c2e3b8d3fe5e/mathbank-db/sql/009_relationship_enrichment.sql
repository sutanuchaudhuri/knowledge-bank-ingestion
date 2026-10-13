BEGIN;
CREATE TABLE IF NOT EXISTS knowledge.relationship_enrichment_job (
    entity_kind text NOT NULL CHECK (entity_kind IN ('skill','concept')),
    anchor_id uuid NOT NULL,
    input_hash text NOT NULL,
    status text NOT NULL CHECK (status IN ('IN_PROGRESS','COMPLETED','FAILED')),
    attempts integer NOT NULL DEFAULT 1,
    last_error text,
    evidence jsonb,
    edges_inserted integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    PRIMARY KEY(entity_kind,anchor_id)
);
CREATE INDEX IF NOT EXISTS relationship_enrichment_outbox_idx
    ON knowledge.relationship_enrichment_job(updated_at)
    WHERE status='COMPLETED' AND published_at IS NULL;
ALTER TABLE knowledge.pedagogy_review_event
    DROP CONSTRAINT IF EXISTS pedagogy_review_event_entity_kind_check;
ALTER TABLE knowledge.pedagogy_review_event ADD CONSTRAINT pedagogy_review_event_entity_kind_check
    CHECK (entity_kind IN ('skill','skill_concept','skill_relation','concept_relation',
                          'problem_skill','problem_pedagogy','problem_concept','problem_technique'));
COMMIT;
