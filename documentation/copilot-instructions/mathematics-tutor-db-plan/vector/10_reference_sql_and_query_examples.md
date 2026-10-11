# Vector 10 — Reference SQL and Query Examples

This is a reference blueprint, not the final production migration.

## 1. Extensions

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

## 2. Model registry

```sql
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
    UNIQUE(provider, model_name, model_revision)
);
```

## 3. Preprocessing profiles

```sql
CREATE TABLE IF NOT EXISTS search.preprocessing_profile (
    preprocessing_profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    version int NOT NULL,
    configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
    code_revision text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(name, version)
);
```

## 4. Representations

```sql
CREATE TABLE IF NOT EXISTS search.representation (
    representation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_type text NOT NULL,
    source_entity_id uuid NOT NULL,
    representation_kind text NOT NULL,
    preprocessing_profile_id uuid NOT NULL
        REFERENCES search.preprocessing_profile,
    rendered_text text NOT NULL,
    content_hash text NOT NULL,
    source_updated_at timestamptz,
    generated_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'ACTIVE',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (
      source_entity_type,
      source_entity_id,
      representation_kind,
      preprocessing_profile_id,
      content_hash
    )
);
```

## 5. Chunks and lexical search

```sql
CREATE TABLE IF NOT EXISTS search.chunk (
    chunk_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    representation_id uuid NOT NULL
        REFERENCES search.representation ON DELETE CASCADE,
    chunk_ordinal int NOT NULL,
    chunk_kind text NOT NULL,
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
    textsearch tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(chunk_text, ''))
    ) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(representation_id, chunk_ordinal)
);

CREATE INDEX idx_search_chunk_fts
ON search.chunk USING gin(textsearch);

CREATE INDEX idx_search_chunk_trgm
ON search.chunk USING gin(chunk_text gin_trgm_ops);

CREATE INDEX idx_search_chunk_problem ON search.chunk(problem_id);
CREATE INDEX idx_search_chunk_concept ON search.chunk(concept_id);
CREATE INDEX idx_search_chunk_technique ON search.chunk(technique_id);
```

## 6. Embeddings

```sql
CREATE TABLE IF NOT EXISTS search.embedding (
    embedding_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id uuid NOT NULL
        REFERENCES search.chunk ON DELETE CASCADE,
    embedding_model_id uuid NOT NULL
        REFERENCES search.embedding_model,
    embedding vector NOT NULL,
    embedding_hash text,
    generated_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'ACTIVE',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE(chunk_id, embedding_model_id)
);

CREATE INDEX idx_embedding_model_status
ON search.embedding(embedding_model_id, status);
```

## 7. HNSW model-specific index

For an active 1536-dimensional model:

```sql
CREATE INDEX CONCURRENTLY idx_search_embedding_model_a_hnsw
ON search.embedding
USING hnsw (
    (embedding::vector(1536)) vector_cosine_ops
)
WITH (m = 16, ef_construction = 64)
WHERE embedding_model_id = '00000000-0000-0000-0000-000000000001'
  AND status = 'ACTIVE';
```

Create one approximate vector index per active model/dimension.

## 8. Semantic nearest neighbors

```sql
BEGIN;
SET LOCAL hnsw.ef_search = 100;
SET LOCAL hnsw.iterative_scan = strict_order;

SELECT
    c.chunk_id,
    c.problem_id,
    c.chunk_text,
    1 - (
      e.embedding::vector(1536)
      <=> :query_embedding::vector(1536)
    ) AS cosine_similarity
FROM search.embedding e
JOIN search.chunk c ON c.chunk_id = e.chunk_id
WHERE e.embedding_model_id = :model_id
  AND e.status = 'ACTIVE'
ORDER BY e.embedding::vector(1536)
         <=> :query_embedding::vector(1536)
LIMIT 25;
COMMIT;
```

## 9. Semantic search with canonical filters

```sql
SELECT
    p.problem_id,
    p.canonical_code,
    p.statement_text,
    pa.paper_code,
    ce.year,
    1 - (
      e.embedding::vector(1536)
      <=> :query_embedding::vector(1536)
    ) AS semantic_score
FROM search.embedding e
JOIN search.chunk c ON c.chunk_id = e.chunk_id
JOIN core.problem p ON p.problem_id = c.problem_id
JOIN core.paper pa ON pa.paper_id = p.paper_id
JOIN core.competition_edition ce ON ce.edition_id = pa.edition_id
WHERE e.embedding_model_id = :model_id
  AND e.status = 'ACTIVE'
  AND ce.year BETWEEN :start_year AND :end_year
  AND pa.paper_type = :paper_type
ORDER BY e.embedding::vector(1536)
         <=> :query_embedding::vector(1536)
LIMIT 25;
```

## 10. Lexical candidates

```sql
SELECT
    c.chunk_id,
    ts_rank_cd(
      c.textsearch,
      websearch_to_tsquery('english', :query_text)
    ) AS lexical_score
FROM search.chunk c
WHERE c.textsearch @@ websearch_to_tsquery('english', :query_text)
ORDER BY lexical_score DESC
LIMIT 100;
```

## 11. Hybrid RRF skeleton

```sql
WITH semantic AS (
    SELECT
        e.chunk_id,
        row_number() OVER (
            ORDER BY e.embedding::vector(1536)
                     <=> :query_embedding::vector(1536)
        ) AS semantic_rank
    FROM search.embedding e
    WHERE e.embedding_model_id = :model_id
      AND e.status = 'ACTIVE'
    ORDER BY e.embedding::vector(1536)
             <=> :query_embedding::vector(1536)
    LIMIT 100
),
lexical AS (
    SELECT
        c.chunk_id,
        row_number() OVER (
            ORDER BY ts_rank_cd(
              c.textsearch,
              websearch_to_tsquery('english', :query_text)
            ) DESC
        ) AS lexical_rank
    FROM search.chunk c
    WHERE c.textsearch @@ websearch_to_tsquery('english', :query_text)
    LIMIT 100
),
combined AS (
    SELECT
        COALESCE(s.chunk_id, l.chunk_id) AS chunk_id,
        COALESCE(1.0 / (60 + s.semantic_rank), 0)
        + COALESCE(1.0 / (60 + l.lexical_rank), 0) AS rrf_score
    FROM semantic s
    FULL OUTER JOIN lexical l ON l.chunk_id = s.chunk_id
)
SELECT
    c.chunk_id,
    c.problem_id,
    c.chunk_text,
    combined.rrf_score
FROM combined
JOIN search.chunk c ON c.chunk_id = combined.chunk_id
ORDER BY combined.rrf_score DESC
LIMIT 20;
```

Production SQL should push hard filters into each candidate branch where practical.

## 12. Exact-search evaluation

```sql
BEGIN;
SET LOCAL enable_indexscan = off;

SELECT e.chunk_id
FROM search.embedding e
WHERE e.embedding_model_id = :model_id
ORDER BY e.embedding::vector(1536)
         <=> :query_embedding::vector(1536)
LIMIT 20;
COMMIT;
```

Use this as the gold candidate set when measuring ANN recall@20.

## 13. Missing-embedding reconciliation

```sql
SELECT c.chunk_id
FROM search.chunk c
JOIN search.representation r
  ON r.representation_id = c.representation_id
LEFT JOIN search.embedding e
  ON e.chunk_id = c.chunk_id
 AND e.embedding_model_id = :model_id
 AND e.status = 'ACTIVE'
WHERE r.status = 'ACTIVE'
  AND e.embedding_id IS NULL;
```

Schedule this as an integrity check.

## 14. Design rule

Vectors answer:

> Which items are semantically close?

SQL answers:

> Which of those items are canonical, allowed, reviewed, appropriately difficult, and eligible for this learner/query?

The tutor needs both.
