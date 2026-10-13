-- mathbank-db vector/search subsystem — pgvector + FTS hybrid retrieval.
-- Per mathematics_tutor_db_plan_v2/vector/10_reference_sql_and_query_examples.md
-- (adapted: table/column names kept as-is, one schema file instead of split migrations).
--
-- Requires pgvector >= 0.8 installed for this Postgres install (see
-- `make install-pgvector` — Homebrew's bottled pgvector only targets pg@17/18).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS search.embedding_model (
    embedding_model_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    model_name text NOT NULL,
    model_revision text NOT NULL,
    dimensions int NOT NULL CHECK (dimensions > 0),
    distance_metric text NOT NULL DEFAULT 'COSINE',
    normalization text,
    status text NOT NULL DEFAULT 'REGISTERED',
    activated_at timestamptz,
    retired_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (provider, model_name, model_revision)
);

CREATE TABLE IF NOT EXISTS search.preprocessing_profile (
    preprocessing_profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    version int NOT NULL,
    configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
    code_revision text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS search.representation (
    representation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_type text NOT NULL, -- 'PROBLEM' | 'SOLUTION'
    source_entity_id uuid NOT NULL,
    representation_kind text NOT NULL, -- 'PROBLEM_STATEMENT' | 'SOLUTION_FULL'
    preprocessing_profile_id uuid NOT NULL REFERENCES search.preprocessing_profile,
    rendered_text text NOT NULL,
    content_hash text NOT NULL,
    source_updated_at timestamptz,
    generated_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'ACTIVE', -- ACTIVE | SUPERSEDED
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_entity_type, source_entity_id, representation_kind,
            preprocessing_profile_id, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_representation_source
    ON search.representation(source_entity_type, source_entity_id, status);

CREATE TABLE IF NOT EXISTS search.chunk (
    chunk_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    representation_id uuid NOT NULL REFERENCES search.representation ON DELETE CASCADE,
    chunk_ordinal int NOT NULL,
    chunk_kind text NOT NULL, -- 'FULL' | 'WINDOW'
    chunk_text text NOT NULL,
    chunk_hash text NOT NULL,
    token_count int,
    char_count int NOT NULL,
    parent_chunk_id uuid REFERENCES search.chunk,
    problem_id uuid REFERENCES core.problem,
    solution_id uuid REFERENCES core.solution,
    concept_id uuid REFERENCES knowledge.concept,
    technique_id uuid REFERENCES knowledge.technique,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    textsearch tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(chunk_text, ''))) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (representation_id, chunk_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_search_chunk_fts ON search.chunk USING gin (textsearch);
CREATE INDEX IF NOT EXISTS idx_search_chunk_trgm ON search.chunk USING gin (chunk_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_search_chunk_problem ON search.chunk(problem_id);
CREATE INDEX IF NOT EXISTS idx_search_chunk_solution ON search.chunk(solution_id);

CREATE TABLE IF NOT EXISTS search.embedding (
    embedding_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id uuid NOT NULL REFERENCES search.chunk ON DELETE CASCADE,
    embedding_model_id uuid NOT NULL REFERENCES search.embedding_model,
    embedding vector NOT NULL, -- unconstrained dims; model-specific HNSW index casts explicitly
    embedding_hash text,
    generated_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'ACTIVE',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (chunk_id, embedding_model_id)
);

CREATE INDEX IF NOT EXISTS idx_embedding_model_status ON search.embedding(embedding_model_id, status);

CREATE TABLE IF NOT EXISTS search.embedding_job (
    embedding_job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid REFERENCES pipeline.run,
    representation_id uuid REFERENCES search.representation,
    embedding_model_id uuid REFERENCES search.embedding_model,
    status text NOT NULL DEFAULT 'PENDING',
    attempt_count int NOT NULL DEFAULT 0,
    input_hash text NOT NULL,
    started_at timestamptz,
    heartbeat_at timestamptz,
    completed_at timestamptz,
    worker_id text,
    last_error text,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (representation_id, embedding_model_id, input_hash)
);

CREATE TABLE IF NOT EXISTS search.retrieval_profile (
    retrieval_profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    version int NOT NULL,
    configuration jsonb NOT NULL,
    status text NOT NULL DEFAULT 'ACTIVE',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);
