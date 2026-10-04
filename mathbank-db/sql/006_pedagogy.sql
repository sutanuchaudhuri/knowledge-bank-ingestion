-- P0 curated pedagogy. Apply explicitly after 001_schema.sql; no corpus seeds.
BEGIN;

CREATE TABLE IF NOT EXISTS knowledge.skill (
    skill_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE CHECK (btrim(slug) <> ''),
    name text NOT NULL CHECK (btrim(name) <> ''),
    objective text NOT NULL CHECK (btrim(objective) <> ''),
    level integer CHECK (level BETWEEN 1 AND 5),
    source text NOT NULL CHECK (btrim(source) <> ''),
    confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    review_status text NOT NULL DEFAULT 'PENDING'
        CHECK (review_status IN ('PENDING', 'REVIEWED', 'REJECTED'))
);

CREATE TABLE IF NOT EXISTS knowledge.skill_concept (
    skill_id uuid NOT NULL REFERENCES knowledge.skill ON DELETE CASCADE,
    concept_id uuid NOT NULL REFERENCES knowledge.concept,
    source text NOT NULL CHECK (btrim(source) <> ''),
    confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    review_status text NOT NULL DEFAULT 'PENDING'
        CHECK (review_status IN ('PENDING', 'REVIEWED', 'REJECTED')),
    PRIMARY KEY (skill_id, concept_id)
);

CREATE TABLE IF NOT EXISTS knowledge.skill_relation (
    from_skill_id uuid NOT NULL REFERENCES knowledge.skill ON DELETE CASCADE,
    to_skill_id uuid NOT NULL REFERENCES knowledge.skill ON DELETE CASCADE,
    relation_type text NOT NULL
        CHECK (relation_type IN ('PREREQUISITE_OF', 'PART_OF', 'BUILDS_ON')),
    source text NOT NULL CHECK (btrim(source) <> ''),
    confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    review_status text NOT NULL DEFAULT 'PENDING'
        CHECK (review_status IN ('PENDING', 'REVIEWED', 'REJECTED')),
    CHECK (from_skill_id <> to_skill_id),
    PRIMARY KEY (from_skill_id, to_skill_id, relation_type)
);

CREATE TABLE IF NOT EXISTS knowledge.problem_skill (
    problem_id uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    skill_id uuid NOT NULL REFERENCES knowledge.skill,
    relation_type text NOT NULL CHECK (relation_type IN ('REQUIRES', 'PRACTICES', 'TESTS')),
    role text NOT NULL CHECK (role IN ('primary', 'supporting')),
    required_level integer CHECK (required_level BETWEEN 1 AND 5),
    importance numeric NOT NULL CHECK (importance BETWEEN 0 AND 1),
    source text NOT NULL CHECK (btrim(source) <> ''),
    confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    review_status text NOT NULL DEFAULT 'PENDING'
        CHECK (review_status IN ('PENDING', 'REVIEWED', 'REJECTED')),
    PRIMARY KEY (problem_id, skill_id, relation_type, role)
);

CREATE TABLE IF NOT EXISTS knowledge.problem_pedagogy (
    problem_id uuid PRIMARY KEY REFERENCES core.problem ON DELETE CASCADE,
    conceptual_depth integer CHECK (conceptual_depth BETWEEN 1 AND 5),
    technical_load integer CHECK (technical_load BETWEEN 1 AND 5),
    algebraic_load integer CHECK (algebraic_load BETWEEN 1 AND 5),
    insight_required integer CHECK (insight_required BETWEEN 1 AND 5),
    number_of_steps integer CHECK (number_of_steps >= 0),
    prerequisite_depth integer CHECK (prerequisite_depth >= 0),
    estimated_contest_level text CHECK (btrim(estimated_contest_level) <> ''),
    source text NOT NULL CHECK (btrim(source) <> ''),
    confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    review_status text NOT NULL DEFAULT 'PENDING'
        CHECK (review_status IN ('PENDING', 'REVIEWED', 'REJECTED'))
);

CREATE INDEX IF NOT EXISTS skill_concept_concept_idx ON knowledge.skill_concept (concept_id);
CREATE INDEX IF NOT EXISTS skill_relation_target_idx ON knowledge.skill_relation (to_skill_id);
CREATE INDEX IF NOT EXISTS problem_skill_skill_idx ON knowledge.problem_skill (skill_id);
COMMIT;
