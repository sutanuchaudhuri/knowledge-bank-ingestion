-- 046_theorem_catalog.sql
-- A reusable Theorem/Axiom/Lemma/Proposition/Corollary/Identity/Definition catalog
-- (requirements/61), separate from the existing per-route `pedagogy.route_asset`
-- (asset_kind='THEORY') / Neo4j `TheoryItem`, which stays untouched (doc 61 §1-§2).
-- This migration only adds tables/columns; it inserts no rows.
BEGIN;

-- §4.1 — the canonical catalog entry. `kind` is the one true IS-A in this design
-- (doc 61 §3.1): every row IS-A theorem-shaped entity, `kind` says which flavor.
CREATE TABLE IF NOT EXISTS knowledge.theorem (
    theorem_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            text NOT NULL UNIQUE,
    name            text NOT NULL,
    kind            text NOT NULL
                        CHECK (kind IN ('AXIOM','THEOREM','LEMMA','PROPOSITION',
                                        'COROLLARY','IDENTITY','DEFINITION')),
    field           text NOT NULL
                        CHECK (field IN ('ALGEBRA','GEOMETRY','NUMBER_THEORY',
                                         'COMBINATORICS','PROBABILITY','ANALYSIS',
                                         'LOGIC_AND_SET_THEORY','OTHER')),
    -- Authoritative formal statement; may contain inline LaTeX ($...$/$$...$$),
    -- rendered through the same KaTeX pipeline as core.problem.statement_text and
    -- validated at write time with mathbank_rest.math_format.check_latex() (doc 61 §4.1).
    statement_text  text NOT NULL,
    statement_latex text,
    description     text,
    proof_sketch    text,
    source          text NOT NULL DEFAULT 'HUMAN'
                        CHECK (source IN ('HUMAN','LLM_DRAFT','LLM_REVIEWED')),
    review_status   text NOT NULL DEFAULT 'PENDING_REVIEW'
                        CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    approval_method text CHECK (approval_method IS NULL OR approval_method IN ('automatic','human')),
    approved_at     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (kind <> 'AXIOM' OR statement_text IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS theorem_kind_field_idx ON knowledge.theorem(kind, field);
CREATE INDEX IF NOT EXISTS theorem_review_status_idx ON knowledge.theorem(review_status);

-- §4.2 — the prerequisite / lineage DAG. Acyclicity is enforced at the application
-- layer (doc 61 §7), not here — validating "is to_theorem_id an AXIOM" or "would this
-- edge create a cycle" needs a graph walk, which a plain CHECK cannot do.
CREATE TABLE IF NOT EXISTS knowledge.theorem_relation (
    relation_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_theorem_id  uuid NOT NULL REFERENCES knowledge.theorem ON DELETE CASCADE,
    to_theorem_id    uuid NOT NULL REFERENCES knowledge.theorem ON DELETE CASCADE,
    relation_type    text NOT NULL
                         CHECK (relation_type IN ('DEPENDS_ON','GENERALIZES',
                                                   'SPECIAL_CASE_OF','EQUIVALENT_TO',
                                                   'COROLLARY_OF')),
    assertion_source text NOT NULL,
    confidence       numeric(5,4) CHECK (confidence BETWEEN 0 AND 1),
    review_status    text NOT NULL DEFAULT 'PENDING'
                         CHECK (review_status IN ('PENDING','REVIEWED','REJECTED')),
    created_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (from_theorem_id <> to_theorem_id),
    UNIQUE (from_theorem_id, to_theorem_id, relation_type)
);
CREATE INDEX IF NOT EXISTS theorem_relation_to_idx ON knowledge.theorem_relation(to_theorem_id);
CREATE INDEX IF NOT EXISTS theorem_relation_from_idx ON knowledge.theorem_relation(from_theorem_id);

-- §4.3 — which techniques rely on which theorems (HAS-A, doc 61 §3.5).
CREATE TABLE IF NOT EXISTS knowledge.technique_theorem (
    technique_id     uuid NOT NULL REFERENCES knowledge.technique ON DELETE CASCADE,
    theorem_id       uuid NOT NULL REFERENCES knowledge.theorem ON DELETE CASCADE,
    role             text NOT NULL DEFAULT 'JUSTIFIES' CHECK (role IN ('JUSTIFIES','APPLIES')),
    confidence       numeric(5,4) CHECK (confidence BETWEEN 0 AND 1),
    assertion_source text NOT NULL,
    review_status    text NOT NULL DEFAULT 'PENDING'
                         CHECK (review_status IN ('PENDING','REVIEWED','REJECTED')),
    PRIMARY KEY (technique_id, theorem_id, role)
);
CREATE INDEX IF NOT EXISTS technique_theorem_theorem_idx ON knowledge.technique_theorem(theorem_id);

-- §4.4 — connecting a theorem to a wider area (DOMAIN), a CONCEPT, or a SUBCONCEPT,
-- via the generic pedagogy.taxonomy_node wrapper (doc 61 §3.1: this is a technical
-- addressing convenience, not a semantic IS-A between Theorem and Concept).
ALTER TABLE pedagogy.taxonomy_node DROP CONSTRAINT IF EXISTS taxonomy_node_node_type_check;
ALTER TABLE pedagogy.taxonomy_node ADD CONSTRAINT taxonomy_node_node_type_check
    CHECK (node_type IN ('DOMAIN','CONCEPT','SUBCONCEPT','SKILL','TECHNIQUE','THEOREM'));
ALTER TABLE pedagogy.taxonomy_node ADD COLUMN IF NOT EXISTS theorem_id uuid REFERENCES knowledge.theorem;
ALTER TABLE pedagogy.taxonomy_node DROP CONSTRAINT IF EXISTS taxonomy_node_check;
ALTER TABLE pedagogy.taxonomy_node ADD CONSTRAINT taxonomy_node_check
    CHECK (num_nonnulls(concept_id, skill_id, technique_id, theorem_id) <= 1);

CREATE TABLE IF NOT EXISTS knowledge.theorem_taxonomy_link (
    theorem_id       uuid NOT NULL REFERENCES knowledge.theorem ON DELETE CASCADE,
    taxonomy_node_id text NOT NULL REFERENCES pedagogy.taxonomy_node,
    role             text NOT NULL DEFAULT 'PRIMARY',
    derived_via      text NOT NULL DEFAULT 'admin_curation',
    created_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (theorem_id, taxonomy_node_id)
);
CREATE INDEX IF NOT EXISTS theorem_taxonomy_link_node_idx ON knowledge.theorem_taxonomy_link(taxonomy_node_id);

-- §4.5 — optional diagrams, reusing visual.asset (the same mechanism problems, videos
-- and artifacts already use).
CREATE TABLE IF NOT EXISTS knowledge.theorem_asset (
    theorem_id uuid NOT NULL REFERENCES knowledge.theorem ON DELETE CASCADE,
    asset_id   uuid NOT NULL REFERENCES visual.asset ON DELETE CASCADE,
    ordinal    int NOT NULL DEFAULT 1,
    caption    text,
    PRIMARY KEY (theorem_id, asset_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS theorem_asset_ordinal_idx
    ON knowledge.theorem_asset(theorem_id, ordinal);

-- §4.6 — optional direct step citation, for a step needing a more specific citation
-- than its technique provides.
CREATE TABLE IF NOT EXISTS pedagogy.solution_step_theorem (
    solution_step_id text NOT NULL REFERENCES pedagogy.solution_step ON DELETE CASCADE,
    theorem_id       uuid NOT NULL REFERENCES knowledge.theorem,
    confidence       numeric(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source_type      text NOT NULL CHECK (source_type IN ('LLM','RUNTIME','HUMAN')),
    evidence         text,
    review_status    text NOT NULL DEFAULT 'PENDING_REVIEW'
                         CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    PRIMARY KEY (solution_step_id, theorem_id)
);

-- §4.7 — precomputed "related theorems" similarity, mirroring
-- knowledge.misconception_embedding/misconception_similarity exactly.
CREATE TABLE IF NOT EXISTS knowledge.theorem_embedding (
    theorem_id uuid PRIMARY KEY REFERENCES knowledge.theorem ON DELETE CASCADE,
    model text NOT NULL,
    dimensions integer NOT NULL DEFAULT 1536 CHECK (dimensions BETWEEN 1 AND 8192),
    source_text_sha256 text NOT NULL,
    embedding public.vector NOT NULL CHECK (vector_dims(embedding) = dimensions),
    generated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge.theorem_similarity (
    theorem_id_a uuid NOT NULL REFERENCES knowledge.theorem ON DELETE CASCADE,
    theorem_id_b uuid NOT NULL REFERENCES knowledge.theorem ON DELETE CASCADE,
    similarity double precision NOT NULL CHECK (similarity BETWEEN -1 AND 1),
    rank smallint NOT NULL CHECK (rank > 0),
    computed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (theorem_id_a, theorem_id_b),
    CHECK (theorem_id_a <> theorem_id_b)
);
CREATE INDEX IF NOT EXISTS theorem_similarity_a_idx ON knowledge.theorem_similarity(theorem_id_a);

-- §4.9 — any number of admin/agent-entered source links per theorem (student-visible
-- once APPROVED). Only the URL + a short label are stored, never bulk-copied text
-- (documentation/CREDITS.md policy).
CREATE TABLE IF NOT EXISTS knowledge.theorem_source (
    theorem_source_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    theorem_id      uuid NOT NULL REFERENCES knowledge.theorem ON DELETE CASCADE,
    url             text NOT NULL,
    label           text NOT NULL,
    source_type     text NOT NULL DEFAULT 'REFERENCE'
                        CHECK (source_type IN ('REFERENCE','FORMAL_PROOF','VIDEO','TEXTBOOK','OTHER')),
    ordinal         int NOT NULL DEFAULT 1,
    added_by        text NOT NULL,
    review_status   text NOT NULL DEFAULT 'PENDING_REVIEW'
                        CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (theorem_id, url)
);
CREATE INDEX IF NOT EXISTS theorem_source_theorem_idx ON knowledge.theorem_source(theorem_id);

-- §3.3 — a micro-course can target a theorem (and its corollaries/prerequisites)
-- directly, reusing the existing CONCEPT/TECHNIQUE/SKILL target mechanism's own role
-- vocabulary (PRIMARY/SECONDARY/PREREQUISITE already means exactly "the theorem" /
-- "its corollaries" / "the axioms it rests on").
ALTER TABLE pedagogy.micro_course_target DROP CONSTRAINT IF EXISTS micro_course_target_target_type_check;
ALTER TABLE pedagogy.micro_course_target ADD CONSTRAINT micro_course_target_target_type_check
    CHECK (target_type IN ('CONCEPT','TECHNIQUE','SKILL','THEOREM'));
ALTER TABLE pedagogy.micro_course_target ADD COLUMN IF NOT EXISTS theorem_id uuid REFERENCES knowledge.theorem;
ALTER TABLE pedagogy.micro_course_target DROP CONSTRAINT IF EXISTS micro_course_target_check;
ALTER TABLE pedagogy.micro_course_target ADD CONSTRAINT micro_course_target_check CHECK (
    (target_type = 'CONCEPT'   AND concept_id   IS NOT NULL AND technique_id IS NULL AND skill_id IS NULL AND theorem_id IS NULL) OR
    (target_type = 'TECHNIQUE' AND technique_id IS NOT NULL AND concept_id   IS NULL AND skill_id IS NULL AND theorem_id IS NULL) OR
    (target_type = 'SKILL'     AND skill_id     IS NOT NULL AND concept_id   IS NULL AND technique_id IS NULL AND theorem_id IS NULL) OR
    (target_type = 'THEOREM'   AND theorem_id   IS NOT NULL AND concept_id   IS NULL AND technique_id IS NULL AND skill_id IS NULL)
);
CREATE INDEX IF NOT EXISTS micro_course_target_theorem_idx ON pedagogy.micro_course_target (theorem_id) WHERE theorem_id IS NOT NULL;

COMMIT;
