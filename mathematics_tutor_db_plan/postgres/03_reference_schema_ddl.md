# PostgreSQL 03 — Reference Schema DDL

This is a representative starting schema. Production migrations should split it into versioned Alembic migrations.

```sql
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS search;
CREATE SCHEMA IF NOT EXISTS pipeline;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE core.competition (
    competition_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    organization text,
    country text,
    level text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, organization)
);

CREATE TABLE core.competition_edition (
    edition_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    competition_id uuid NOT NULL REFERENCES core.competition,
    year int NOT NULL CHECK (year BETWEEN 1900 AND 2200),
    season text,
    edition_label text,
    UNIQUE (competition_id, year, season, edition_label)
);

CREATE TABLE core.paper (
    paper_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id uuid NOT NULL REFERENCES core.competition_edition,
    paper_code text NOT NULL,
    paper_type text,
    duration_minutes int,
    question_count int,
    max_score numeric,
    official boolean NOT NULL DEFAULT true,
    UNIQUE (edition_id, paper_code)
);

CREATE TABLE core.problem (
    problem_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id uuid NOT NULL REFERENCES core.paper,
    problem_number int NOT NULL,
    canonical_code text NOT NULL UNIQUE,
    statement_text text NOT NULL,
    statement_latex text,
    answer_type text,
    official_answer text,
    status text NOT NULL DEFAULT 'ACTIVE',
    content_hash text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (paper_id, problem_number)
);

CREATE TABLE core.solution (
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

CREATE TABLE core.solution_step (
    solution_step_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id uuid NOT NULL REFERENCES core.solution ON DELETE CASCADE,
    ordinal int NOT NULL,
    step_type text,
    explanation text,
    formula_latex text,
    UNIQUE (solution_id, ordinal)
);

CREATE TABLE knowledge.concept (
    concept_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE,
    name text NOT NULL,
    description text,
    level int,
    status text NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE knowledge.technique (
    technique_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE,
    name text NOT NULL,
    description text,
    status text NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE knowledge.problem_concept (
    problem_id uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    concept_id uuid NOT NULL REFERENCES knowledge.concept,
    role text NOT NULL DEFAULT 'PRIMARY',
    confidence numeric(5,4),
    assertion_source text NOT NULL,
    review_status text NOT NULL DEFAULT 'PENDING',
    asserted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (problem_id, concept_id, role)
);

CREATE TABLE knowledge.problem_technique (
    problem_id uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    technique_id uuid NOT NULL REFERENCES knowledge.technique,
    role text NOT NULL DEFAULT 'REQUIRED',
    confidence numeric(5,4),
    assertion_source text NOT NULL,
    review_status text NOT NULL DEFAULT 'PENDING',
    PRIMARY KEY (problem_id, technique_id, role)
);

CREATE TABLE knowledge.concept_relation (
    relation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_concept_id uuid NOT NULL REFERENCES knowledge.concept,
    to_concept_id uuid NOT NULL REFERENCES knowledge.concept,
    relation_type text NOT NULL,
    strength numeric(5,4),
    assertion_source text NOT NULL,
    review_status text NOT NULL DEFAULT 'PENDING',
    UNIQUE (from_concept_id, to_concept_id, relation_type)
);

CREATE TABLE pipeline.run (
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

CREATE TABLE pipeline.work_item (
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

CREATE INDEX idx_problem_paper ON core.problem(paper_id, problem_number);
CREATE INDEX idx_problem_statement_fts ON core.problem USING gin (to_tsvector('english', statement_text));
CREATE INDEX idx_problem_statement_trgm ON core.problem USING gin (statement_text gin_trgm_ops);
CREATE INDEX idx_run_status ON pipeline.run(status, started_at DESC);
CREATE INDEX idx_work_claim ON pipeline.work_item(status, lease_expires_at);
```

## Status constraints

In production, use check constraints or reference tables for controlled statuses. Suggested run/work states:

`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `PARTIAL`, `CANCELLED`, `BLOCKED`, `STALE`.

Avoid PostgreSQL ENUM initially if frequent state evolution is expected; a reference table plus foreign key is easier to migrate.
