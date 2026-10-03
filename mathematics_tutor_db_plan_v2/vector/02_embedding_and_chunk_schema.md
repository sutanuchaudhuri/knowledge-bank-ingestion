# Vector 02 — Embedding, Representation, and Chunk Data Model

## 1. Data model

Use four layers:

```text
SOURCE ENTITY → REPRESENTATION → CHUNK → EMBEDDING
```

A source entity is canonical content already stored elsewhere.

A representation specifies how that content is rendered for a retrieval purpose.

A chunk is the stable retrievable unit.

An embedding is the model-specific numeric vector for that chunk.

## 2. Embedding-model registry

```sql
CREATE TABLE search.embedding_model (
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

Do not use the marketing model name as the only identifier. A provider may change model behavior, and local fine-tuned models need explicit revision identity.

Suggested statuses:

```text
REGISTERED
BACKFILLING
EVALUATING
ACTIVE
DEPRECATED
RETIRED
FAILED
```

## 3. Preprocessing profile

```sql
CREATE TABLE search.preprocessing_profile (
    preprocessing_profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    version int NOT NULL,
    configuration jsonb NOT NULL,
    code_revision text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(name, version)
);
```

Example configuration:

```json
{
  "normalize_unicode": true,
  "preserve_latex": true,
  "latex_plaintext_projection": true,
  "prepend_entity_type": true,
  "prepend_taxonomy": false,
  "solution_step_window": 2,
  "max_tokens": 1200
}
```

## 4. Search representation

```sql
CREATE TABLE search.representation (
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

## 5. Semantic chunks

```sql
CREATE TABLE search.chunk (
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
    created_at timestamptz NOT NULL DEFAULT now(),

    UNIQUE(representation_id, chunk_ordinal)
);
```

The denormalized canonical foreign keys are deliberate: they make common filtered retrieval fast while provenance still flows through the representation back to the true source.

## 6. Embedding rows

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE search.embedding (
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
```

Use `vector` without a fixed dimension in the shared table so multiple model dimensions can coexist.

Approximate indexes are created as model-specific partial/expression indexes.

```sql
CREATE INDEX idx_embedding_model_x_hnsw
ON search.embedding
USING hnsw ((embedding::vector(1536)) vector_cosine_ops)
WHERE embedding_model_id = 'MODEL_UUID'
  AND status = 'ACTIVE';
```

## 7. Dimension integrity

Because the physical column is unconstrained `vector`, validate:

```text
vector_dims(NEW.embedding)
=
search.embedding_model.dimensions
```

Use both application validation and a database trigger/constraint mechanism.

A malformed vector must fail the write.

## 8. Retrieval profiles

Store search behavior as data.

```sql
CREATE TABLE search.retrieval_profile (
    retrieval_profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    version int NOT NULL,
    configuration jsonb NOT NULL,
    status text NOT NULL DEFAULT 'ACTIVE',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(name, version)
);
```

Example names:

- `SIMILAR_PROBLEM`
- `TEACH_CONCEPT`
- `SOLUTION_ANALOGY`
- `FIND_PREREQUISITE`
- `NEXT_PROBLEM`
- `MISCONCEPTION_DIAGNOSIS`
- `CORPUS_RESEARCH`

## 9. Embedding jobs

```sql
CREATE TABLE search.embedding_job (
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

    UNIQUE(representation_id, embedding_model_id, input_hash)
);
```

Embedding work therefore participates in the same durable restart/retry model as the corpus backfill.

## 10. Historical retention

When canonical content changes:

1. mark the old representation `SUPERSEDED`;
2. generate a new representation and new hash;
3. create new chunks;
4. generate embeddings;
5. activate the new retrieval surface;
6. retain or purge old vectors according to policy.

Never mutate an embedding without preserving which source text generated it.
