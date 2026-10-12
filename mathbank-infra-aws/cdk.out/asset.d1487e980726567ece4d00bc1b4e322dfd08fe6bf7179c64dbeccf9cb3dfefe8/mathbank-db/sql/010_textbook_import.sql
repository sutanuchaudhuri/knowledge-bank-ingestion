-- 010_textbook_import.sql — v2 pack Phase 2/3: textbook package import,
-- staging/reconciliation, and the solution part/step/dependency DAG.
--
-- Design (see requirements/18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md):
--   * Canonical problems/solutions stay in core.problem / core.solution; a
--     textbook becomes a core.competition, each chapter a core.paper.
--   * Taxonomy nodes bridge into the existing knowledge.concept / skill /
--     technique tables; the raw package taxonomy is kept in pedagogy.taxonomy_*.
--   * Solution diagrams live in pedagogy.diagram (never core.problem_image)
--     so student surfaces cannot leak hidden solution content.
--   * Transformations become review-gated pedagogy.learning_item rows that are
--     never student-visible while PENDING_REVIEW.
-- Idempotent and additive; safe to re-run.

BEGIN;

CREATE SCHEMA IF NOT EXISTS ingest;
CREATE SCHEMA IF NOT EXISTS pedagogy;

-- Textbooks have no contest year; the edition label carries the edition.
ALTER TABLE core.competition_edition ALTER COLUMN year DROP NOT NULL;

-- ---------------------------------------------------------------- ingest ---
CREATE TABLE IF NOT EXISTS ingest.content_package (
    content_package_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    package_name       text NOT NULL,
    package_version    text NOT NULL,
    manifest_hash      text NOT NULL,
    book_code          text,
    source_root        text,
    status             text NOT NULL DEFAULT 'REGISTERED'
        CHECK (status IN ('REGISTERED','VALIDATING','INVALID','IMPORTING','RECONCILING',
                          'POSTGRES_COMPLETE','EMBEDDING','GRAPH_PROJECTING','COMPLETED','FAILED')),
    status_detail      text,
    last_scope         text,
    report             jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    imported_at        timestamptz,
    UNIQUE (package_name, package_version, manifest_hash)
);

CREATE TABLE IF NOT EXISTS ingest.package_status_event (
    event_id           bigserial PRIMARY KEY,
    content_package_id uuid NOT NULL REFERENCES ingest.content_package ON DELETE CASCADE,
    from_status        text,
    to_status          text NOT NULL,
    scope              text,
    detail             text,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingest.package_file (
    content_package_id uuid NOT NULL REFERENCES ingest.content_package ON DELETE CASCADE,
    relative_path      text NOT NULL,
    file_role          text NOT NULL,
    sha256             text NOT NULL,
    byte_size          bigint NOT NULL,
    row_count          integer,
    PRIMARY KEY (content_package_id, relative_path)
);

CREATE TABLE IF NOT EXISTS ingest.staging_row (
    staging_row_id     bigserial PRIMARY KEY,
    content_package_id uuid NOT NULL REFERENCES ingest.content_package ON DELETE CASCADE,
    source_file        text NOT NULL,
    source_row_number  integer NOT NULL,
    entity_type        text NOT NULL,
    external_id        text,
    source_row_json    jsonb NOT NULL,
    validation_status  text NOT NULL DEFAULT 'PENDING'
        CHECK (validation_status IN ('PENDING','VALID','IMPORTED','REJECTED')),
    validation_errors  jsonb NOT NULL DEFAULT '[]'::jsonb,
    validation_warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
    target_key         text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (content_package_id, source_file, source_row_number)
);
CREATE INDEX IF NOT EXISTS staging_row_status_idx
    ON ingest.staging_row (content_package_id, entity_type, validation_status);

CREATE TABLE IF NOT EXISTS ingest.import_conflict (
    conflict_id        bigserial PRIMARY KEY,
    content_package_id uuid NOT NULL REFERENCES ingest.content_package ON DELETE CASCADE,
    entity_type        text NOT NULL,
    external_id        text NOT NULL,
    conflict_type      text NOT NULL,
    severity           text NOT NULL CHECK (severity IN ('INFO','WARNING','ERROR')),
    detail             jsonb NOT NULL DEFAULT '{}'::jsonb,
    resolution_status  text NOT NULL DEFAULT 'OPEN'
        CHECK (resolution_status IN ('OPEN','AUTO_RESOLVED','RESOLVED','IGNORED')),
    resolution         text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (content_package_id, entity_type, external_id, conflict_type)
);

CREATE TABLE IF NOT EXISTS ingest.reconciliation (
    content_package_id uuid NOT NULL REFERENCES ingest.content_package ON DELETE CASCADE,
    scope              text NOT NULL,
    entity_type        text NOT NULL,
    source_count       integer NOT NULL DEFAULT 0,
    valid_count        integer NOT NULL DEFAULT 0,
    imported_count     integer NOT NULL DEFAULT 0,
    created_count      integer NOT NULL DEFAULT 0,
    updated_count      integer NOT NULL DEFAULT 0,
    unchanged_count    integer NOT NULL DEFAULT 0,
    rejected_count     integer NOT NULL DEFAULT 0,
    conflict_count     integer NOT NULL DEFAULT 0,
    present_in_db      integer NOT NULL DEFAULT 0,
    reconciled         boolean NOT NULL DEFAULT false,
    reconciled_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (content_package_id, scope, entity_type)
);

-- -------------------------------------------------------------- pedagogy ---
CREATE TABLE IF NOT EXISTS pedagogy.source_book (
    book_code          text PRIMARY KEY,
    external_book_id   text NOT NULL UNIQUE,
    title              text NOT NULL,
    author             text,
    translator_editor  text,
    source_file        text,
    competition_id     uuid REFERENCES core.competition,
    edition_id         uuid REFERENCES core.competition_edition,
    metadata           jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pedagogy.chapter_section (
    book_code          text NOT NULL REFERENCES pedagogy.source_book,
    chapter_number     integer NOT NULL,
    section_number     text NOT NULL,
    chapter_title      text,
    section_title      text,
    paper_id           uuid REFERENCES core.paper,
    content_package_id uuid NOT NULL REFERENCES ingest.content_package,
    PRIMARY KEY (book_code, chapter_number, section_number)
);

CREATE TABLE IF NOT EXISTS pedagogy.taxonomy_node (
    taxonomy_node_id   text PRIMARY KEY,
    node_type          text NOT NULL CHECK (node_type IN ('DOMAIN','CONCEPT','SUBCONCEPT','SKILL','TECHNIQUE')),
    name               text NOT NULL,
    parent_node_id     text,
    chapter_number     integer,
    section_number     text,
    source_basis       text,
    description        text,
    concept_id         uuid REFERENCES knowledge.concept,
    skill_id           uuid REFERENCES knowledge.skill,
    technique_id       uuid REFERENCES knowledge.technique,
    content_package_id uuid NOT NULL REFERENCES ingest.content_package,
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(concept_id, skill_id, technique_id) <= 1)
);

CREATE TABLE IF NOT EXISTS pedagogy.taxonomy_edge (
    from_node_id       text NOT NULL REFERENCES pedagogy.taxonomy_node,
    to_node_id         text NOT NULL REFERENCES pedagogy.taxonomy_node,
    relationship_type  text NOT NULL,
    source_basis       text,
    confidence         numeric,
    content_package_id uuid NOT NULL REFERENCES ingest.content_package,
    PRIMARY KEY (from_node_id, to_node_id, relationship_type),
    CHECK (from_node_id <> to_node_id)
);

-- External textbook identifiers mapped onto canonical problems.
CREATE TABLE IF NOT EXISTS pedagogy.problem_source_ref (
    book_code               text NOT NULL REFERENCES pedagogy.source_book,
    source_problem_id       text NOT NULL,
    problem_id              uuid NOT NULL UNIQUE REFERENCES core.problem ON DELETE CASCADE,
    chapter_number          integer NOT NULL,
    section_number          text,
    section_title           text,
    source_printed_problem_id text,
    source_editorial_marker text,
    source_numbering_note   text,
    source_pdf              text,
    source_page_start       integer,
    source_page_end         integer,
    problem_requires_diagram boolean,
    solution_requires_diagram boolean,
    difficulty_rank_in_section integer,
    section_problem_count   integer,
    content_package_id      uuid NOT NULL REFERENCES ingest.content_package,
    PRIMARY KEY (book_code, source_problem_id)
);

CREATE TABLE IF NOT EXISTS pedagogy.solution_source_ref (
    book_code          text NOT NULL REFERENCES pedagogy.source_book,
    source_solution_id text NOT NULL,
    solution_id        uuid NOT NULL UNIQUE REFERENCES core.solution ON DELETE CASCADE,
    problem_id         uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    solution_first_step text,
    source_page        integer,
    content_package_id uuid NOT NULL REFERENCES ingest.content_package,
    PRIMARY KEY (book_code, source_solution_id)
);

-- Spec "taxonomy.problem_enrichment", kept beside the pedagogy tables.
CREATE TABLE IF NOT EXISTS pedagogy.problem_enrichment (
    problem_id                  uuid PRIMARY KEY REFERENCES core.problem ON DELETE CASCADE,
    concept_node_id             text REFERENCES pedagogy.taxonomy_node,
    subconcept_node_id          text REFERENCES pedagogy.taxonomy_node,
    primary_skill_node_id       text REFERENCES pedagogy.taxonomy_node,
    solution_step_skill_ids     text[] NOT NULL DEFAULT '{}',
    technique_ids               text[] NOT NULL DEFAULT '{}',
    problem_form                text,
    difficulty_band_source_order integer,
    solution_step_count         integer,
    taxonomy_mapping_basis      text,
    taxonomy_confidence         numeric,
    content_package_id          uuid NOT NULL REFERENCES ingest.content_package,
    updated_at                  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pedagogy.solution_part (
    solution_part_id     text PRIMARY KEY,
    source_part_id       text NOT NULL,
    occurrence           integer NOT NULL DEFAULT 1,
    book_code            text NOT NULL REFERENCES pedagogy.source_book,
    solution_id          uuid NOT NULL REFERENCES core.solution ON DELETE CASCADE,
    problem_id           uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    part_label           text,
    part_ordinal         integer NOT NULL,
    step_count           integer NOT NULL,
    source_step_count    integer,
    source_page          integer,
    part_text_normalized text,
    content_package_id   uuid NOT NULL REFERENCES ingest.content_package,
    updated_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (book_code, source_part_id, occurrence)
);
CREATE INDEX IF NOT EXISTS solution_part_problem_idx ON pedagogy.solution_part (problem_id, part_ordinal);

CREATE TABLE IF NOT EXISTS pedagogy.solution_step (
    solution_step_id    text PRIMARY KEY,
    source_step_id      text NOT NULL,
    occurrence          integer NOT NULL DEFAULT 1,
    book_code           text NOT NULL REFERENCES pedagogy.source_book,
    solution_part_id    text NOT NULL REFERENCES pedagogy.solution_part ON DELETE CASCADE,
    solution_id         uuid NOT NULL REFERENCES core.solution ON DELETE CASCADE,
    problem_id          uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    global_step_index   integer NOT NULL,
    step_index_in_part  integer NOT NULL,
    step_text           text NOT NULL,
    step_type           text NOT NULL,
    tutor_role          text,
    concept_node_id     text REFERENCES pedagogy.taxonomy_node,
    subconcept_node_id  text REFERENCES pedagogy.taxonomy_node,
    skill_node_id       text REFERENCES pedagogy.taxonomy_node,
    skill_name          text,
    hint_level          smallint CHECK (hint_level BETWEEN 1 AND 4),
    is_checkpoint       boolean NOT NULL DEFAULT false,
    source_previous_step_id text,
    source_next_step_id text,
    source_page         integer,
    source_metadata     jsonb NOT NULL DEFAULT '{}'::jsonb,
    publication_status  text NOT NULL DEFAULT 'PUBLISHED',
    content_package_id  uuid NOT NULL REFERENCES ingest.content_package,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (problem_id, global_step_index),
    UNIQUE (book_code, source_step_id, occurrence)
);
CREATE INDEX IF NOT EXISTS solution_step_part_idx ON pedagogy.solution_step (solution_part_id, step_index_in_part);
CREATE INDEX IF NOT EXISTS solution_step_skill_idx ON pedagogy.solution_step (skill_node_id);

CREATE TABLE IF NOT EXISTS pedagogy.solution_step_dependency (
    from_step_id       text NOT NULL REFERENCES pedagogy.solution_step ON DELETE CASCADE,
    to_step_id         text NOT NULL REFERENCES pedagogy.solution_step ON DELETE CASCADE,
    relationship_type  text NOT NULL,
    logical_dependency text,
    confidence         numeric CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    source_type        text NOT NULL,
    review_status      text NOT NULL DEFAULT 'REVIEWED' CHECK (review_status IN ('PENDING','REVIEWED','REJECTED')),
    approval_method    text,
    metadata           jsonb NOT NULL DEFAULT '{}'::jsonb,
    content_package_id uuid REFERENCES ingest.content_package,
    PRIMARY KEY (from_step_id, to_step_id, relationship_type),
    CHECK (from_step_id <> to_step_id)
);
CREATE INDEX IF NOT EXISTS solution_step_dependency_to_idx ON pedagogy.solution_step_dependency (to_step_id);

-- Phase 1 LearningItem model, seeded from package transformations.
CREATE TABLE IF NOT EXISTS pedagogy.learning_item (
    learning_item_id        text PRIMARY KEY,
    source_transformation_id text NOT NULL,
    occurrence              integer NOT NULL DEFAULT 1,
    book_code               text NOT NULL REFERENCES pedagogy.source_book,
    source_problem_id       uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    parent_learning_item_id text,
    transformation_type     text NOT NULL,
    transformed_form        text,
    target_concept_node_id  text REFERENCES pedagogy.taxonomy_node,
    target_subconcept_node_id text REFERENCES pedagogy.taxonomy_node,
    target_skill_node_id    text REFERENCES pedagogy.taxonomy_node,
    difficulty_direction    text,
    question_text           text NOT NULL,
    choices                 jsonb,
    correct_answer          text,
    answer_or_solution_seed text,
    generation_mode         text,
    solution_part_label     text,
    requires_source_problem boolean,
    diagram_strategy        text,
    no_proof                boolean NOT NULL CHECK (no_proof),
    review_status           text NOT NULL DEFAULT 'PENDING_REVIEW'
        CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED','NEEDS_REVISION')),
    student_visible         boolean NOT NULL DEFAULT false,
    content_package_id      uuid NOT NULL REFERENCES ingest.content_package,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (book_code, source_transformation_id, occurrence),
    CONSTRAINT learning_item_visible_requires_approval CHECK (NOT student_visible OR review_status = 'APPROVED')
);
CREATE INDEX IF NOT EXISTS learning_item_problem_idx ON pedagogy.learning_item (source_problem_id);

CREATE TABLE IF NOT EXISTS pedagogy.learning_item_step_anchor (
    learning_item_id   text NOT NULL REFERENCES pedagogy.learning_item ON DELETE CASCADE,
    solution_step_id   text NOT NULL REFERENCES pedagogy.solution_step ON DELETE CASCADE,
    anchor_ordinal     integer NOT NULL,
    PRIMARY KEY (learning_item_id, solution_step_id)
);

CREATE TABLE IF NOT EXISTS pedagogy.diagram (
    diagram_id           text PRIMARY KEY,
    source_diagram_id    text NOT NULL,
    book_code            text NOT NULL REFERENCES pedagogy.source_book,
    problem_id           uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    usage                text NOT NULL,
    visibility           text NOT NULL CHECK (visibility IN ('STUDENT_PROBLEM','SOLUTION_HIDDEN')),
    source_pdf_page      integer,
    source_figure_number text,
    source_caption       text,
    asset_path           text NOT NULL,
    local_path           text NOT NULL,
    sha256               text,
    extraction_method    text,
    validation_status    text,
    problem_image_id     uuid REFERENCES core.problem_image ON DELETE SET NULL,
    content_package_id   uuid NOT NULL REFERENCES ingest.content_package,
    updated_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (book_code, source_diagram_id)
);
CREATE INDEX IF NOT EXISTS diagram_problem_idx ON pedagogy.diagram (problem_id, usage);

COMMENT ON SCHEMA ingest IS 'v2 content-package registry, staging, conflicts and reconciliation';
COMMENT ON SCHEMA pedagogy IS 'v2 solution DAG, textbook taxonomy, learning items and diagrams';
COMMENT ON TABLE pedagogy.diagram IS 'SOLUTION_HIDDEN diagrams must never be returned by student-facing problem endpoints';
COMMENT ON TABLE pedagogy.learning_item IS 'Transformations; never student-visible unless review_status=APPROVED';

COMMIT;
