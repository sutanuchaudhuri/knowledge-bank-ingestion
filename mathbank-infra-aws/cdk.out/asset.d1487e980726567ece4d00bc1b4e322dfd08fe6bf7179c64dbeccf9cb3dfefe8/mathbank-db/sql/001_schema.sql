-- mathbank-db schema — PostgreSQL system of record.
-- Base DDL per mathematics_tutor_db_plan/postgres/03_reference_schema_ddl.md,
-- extended with nullable external_code/external_id natural keys so the ETL
-- (etl/load_corpus.py) can upsert idempotently from the maths_corpus CSV mirror.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS search;
CREATE SCHEMA IF NOT EXISTS pipeline;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS core.competition (
    competition_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_code text UNIQUE, -- source Competition_ID (competition_catalog.csv)
    name text NOT NULL,
    organization text,
    country text,
    level text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, organization)
);

CREATE TABLE IF NOT EXISTS core.competition_edition (
    edition_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    competition_id uuid NOT NULL REFERENCES core.competition,
    year int NOT NULL CHECK (year BETWEEN 1900 AND 2200),
    season text,
    edition_label text,
    UNIQUE (competition_id, year, season, edition_label)
);

CREATE TABLE IF NOT EXISTS core.paper (
    paper_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id uuid NOT NULL REFERENCES core.competition_edition,
    external_code text UNIQUE, -- source Test_ID (test_registry.csv)
    paper_code text NOT NULL,
    paper_type text,
    duration_minutes int,
    question_count int,
    max_score numeric,
    official boolean NOT NULL DEFAULT true,
    UNIQUE (edition_id, paper_code)
);

CREATE TABLE IF NOT EXISTS core.problem (
    problem_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id uuid NOT NULL REFERENCES core.paper,
    problem_number int NOT NULL,
    canonical_code text NOT NULL UNIQUE, -- source Question_ID (question_index.csv) or crawl_pdf PAPER_ID_Qnn
    statement_text text NOT NULL,
    statement_latex text,
    answer_type text,
    official_answer text,
    source_url text, -- AoPS_Question_URL / Direct_Problem_URL (full text not yet ingested)
    difficulty_band text, -- e.g. "AIME D3 / Entry (Q1-5)" (question_index.csv Difficulty_Band)
    classification_status text, -- UNMAPPED / FINE_CONCEPT_MAPPED / BROAD_OR_OTHER_ONLY
    status text NOT NULL DEFAULT 'ACTIVE',
    content_hash text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (paper_id, problem_number)
);

-- Additive columns for databases migrated from an earlier version of this schema.
ALTER TABLE core.problem ADD COLUMN IF NOT EXISTS difficulty_band text;
ALTER TABLE core.problem ADD COLUMN IF NOT EXISTS classification_status text;

CREATE TABLE IF NOT EXISTS core.solution (
    solution_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    problem_id uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    solution_kind text NOT NULL DEFAULT 'CURATED',
    revision int NOT NULL DEFAULT 1,
    body_markdown text,
    body_latex text,
    verification_status text NOT NULL DEFAULT 'UNVERIFIED',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (problem_id, solution_kind, revision)
);

CREATE TABLE IF NOT EXISTS core.solution_step (
    solution_step_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id uuid NOT NULL REFERENCES core.solution ON DELETE CASCADE,
    ordinal int NOT NULL,
    step_type text,
    explanation text,
    formula_latex text,
    UNIQUE (solution_id, ordinal)
);

-- Figures extracted alongside PDF-parsed problem/solution text (e.g. MPG diagrams).
CREATE TABLE IF NOT EXISTS core.problem_image (
    problem_image_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    problem_id uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    ordinal int NOT NULL,
    local_path text NOT NULL, -- absolute path under data/crawl_pdf/.../images/
    source text NOT NULL DEFAULT 'PDF_PARSED',
    UNIQUE (problem_id, ordinal)
);

CREATE TABLE IF NOT EXISTS knowledge.concept (
    concept_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE, -- source Canonical_Topic_ID / LIVE_* concept id, lowercased
    name text NOT NULL,
    description text,
    level int,
    status text NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS knowledge.technique (
    technique_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE, -- source Technique_ID, lowercased
    name text NOT NULL,
    description text,
    status text NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS knowledge.problem_concept (
    problem_id uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    concept_id uuid NOT NULL REFERENCES knowledge.concept,
    role text NOT NULL DEFAULT 'PRIMARY',
    confidence numeric(5,4),
    assertion_source text NOT NULL,
    review_status text NOT NULL DEFAULT 'PENDING',
    asserted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (problem_id, concept_id, role)
);

CREATE TABLE IF NOT EXISTS knowledge.problem_technique (
    problem_id uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    technique_id uuid NOT NULL REFERENCES knowledge.technique,
    role text NOT NULL DEFAULT 'REQUIRED',
    confidence numeric(5,4),
    assertion_source text NOT NULL,
    review_status text NOT NULL DEFAULT 'PENDING',
    PRIMARY KEY (problem_id, technique_id, role)
);

CREATE TABLE IF NOT EXISTS knowledge.concept_relation (
    relation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_concept_id uuid NOT NULL REFERENCES knowledge.concept,
    to_concept_id uuid NOT NULL REFERENCES knowledge.concept,
    relation_type text NOT NULL,
    strength numeric(5,4),
    assertion_source text NOT NULL,
    review_status text NOT NULL DEFAULT 'PENDING',
    UNIQUE (from_concept_id, to_concept_id, relation_type)
);

CREATE TABLE IF NOT EXISTS pipeline.run (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type text NOT NULL,
    requested_scope jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL,
    started_at timestamptz,
    completed_at timestamptz,
    heartbeat_at timestamptz,
    worker_id text,
    expected_items int,
    completed_items int NOT NULL DEFAULT 0,
    failed_items int NOT NULL DEFAULT 0,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS pipeline.work_item (
    work_item_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES pipeline.run ON DELETE CASCADE,
    item_type text NOT NULL,
    item_key text NOT NULL,
    status text NOT NULL DEFAULT 'PENDING',
    attempt_count int NOT NULL DEFAULT 0,
    lease_owner text,
    lease_expires_at timestamptz,
    started_at timestamptz,
    completed_at timestamptz,
    last_error text,
    input_hash text,
    output_hash text,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (run_id, item_type, item_key)
);

-- pipeline.graph_projection per graph/03_postgres_to_graph_projection.md
CREATE TABLE IF NOT EXISTS pipeline.graph_projection (
    projection_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    graph_name text NOT NULL,
    source_watermark timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    nodes_upserted int NOT NULL DEFAULT 0,
    edges_upserted int NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'IN_PROGRESS',
    error text
);

-- Per-link tracker for the PDF download -> parse -> ingest pipeline
-- (etl/pdf_pipeline.py). One row per paper_registry.csv "PAPER_*" link.
CREATE TABLE IF NOT EXISTS pipeline.pdf_source (
    pdf_source_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_external_code text NOT NULL UNIQUE, -- paper_registry.csv Paper_ID
    competition_external_code text NOT NULL,
    crawl_dir text NOT NULL, -- data/crawl_pdf/<crawl_dir>/<paper_external_code>/
    problem_url text,
    solution_url text,
    link_scope text,
    download_status text NOT NULL DEFAULT 'PENDING', -- PENDING | DOWNLOADED | FAILED
    downloaded_at timestamptz,
    parse_status text NOT NULL DEFAULT 'PENDING', -- PENDING | PARSED | FAILED
    parsed_at timestamptz,
    questions_found int NOT NULL DEFAULT 0,
    ingest_status text NOT NULL DEFAULT 'PENDING', -- PENDING | INGESTED | FAILED
    ingested_at timestamptz,
    questions_ingested int NOT NULL DEFAULT 0,
    solutions_ingested int NOT NULL DEFAULT 0,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_problem_paper ON core.problem(paper_id, problem_number);
CREATE INDEX IF NOT EXISTS idx_problem_statement_fts ON core.problem USING gin (to_tsvector('english', statement_text));
CREATE INDEX IF NOT EXISTS idx_problem_statement_trgm ON core.problem USING gin (statement_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_run_status ON pipeline.run(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_work_claim ON pipeline.work_item(status, lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_pdf_source_status ON pipeline.pdf_source(download_status, parse_status, ingest_status);
