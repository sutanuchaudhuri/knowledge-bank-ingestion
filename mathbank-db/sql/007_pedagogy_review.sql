BEGIN;

CREATE TABLE IF NOT EXISTS knowledge.pedagogy_review_event (
    review_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_kind text NOT NULL CHECK (entity_kind IN
        ('skill', 'skill_concept', 'skill_relation', 'problem_skill', 'problem_pedagogy')),
    entity_key jsonb NOT NULL,
    before_snapshot jsonb NOT NULL,
    after_snapshot jsonb NOT NULL,
    reviewer text NOT NULL,
    review_note text NOT NULL CHECK (length(btrim(review_note)) BETWEEN 10 AND 2000),
    reviewed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pedagogy_review_entity_idx
    ON knowledge.pedagogy_review_event (entity_kind, reviewed_at DESC);

CREATE TABLE IF NOT EXISTS knowledge.pedagogy_publication (
    publication_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_fingerprint text NOT NULL,
    publisher text NOT NULL,
    skills_projected integer NOT NULL,
    edges_projected integer NOT NULL,
    published_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;
