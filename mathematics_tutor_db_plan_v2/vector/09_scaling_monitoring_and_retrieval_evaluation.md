# Vector 09 — Scaling, Monitoring, and Retrieval Evaluation

## 1. Two classes of metrics

### Systems metrics

Track:

- p50/p95/p99 query latency;
- index size;
- table size;
- cache hit ratio;
- rows/candidates scanned;
- HNSW settings;
- CPU/memory/I/O;
- connection-pool pressure;
- WAL volume;
- embedding throughput;
- embedding-provider latency/errors.

### Retrieval-quality metrics

Track:

- recall@K;
- precision@K;
- nDCG@K;
- MRR;
- duplicate rate;
- source diversity;
- concept match quality;
- difficulty suitability;
- human preference;
- downstream tutor-task success.

Fast irrelevant search is still failure.

## 2. Versioned benchmark set

Build a benchmark from real Mathematics Tutor tasks.

Each case should specify:

```text
query
query type
filters
gold relevant items
acceptable alternatives
forbidden items
difficulty expectation
taxonomy expectation
notes
```

Include:

- similar problem;
- concept explanation;
- solution analogy;
- misconception retrieval;
- prerequisite retrieval;
- next-problem recommendation.

## 3. Human judgments

```sql
CREATE TABLE search.retrieval_judgment (
    judgment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    benchmark_query_id uuid NOT NULL,
    chunk_id uuid NOT NULL REFERENCES search.chunk,
    relevance_grade int NOT NULL,
    rationale text,
    judged_by text,
    judged_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(benchmark_query_id, chunk_id, judged_by)
);
```

Use graded relevance when possible.

## 4. Evaluation runs

```sql
CREATE TABLE search.retrieval_evaluation (
    evaluation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    benchmark_version text NOT NULL,
    retrieval_profile text NOT NULL,
    embedding_model_id uuid REFERENCES search.embedding_model,
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    configuration jsonb NOT NULL,
    code_revision text
);
```

Every change to model, chunking, HNSW parameters, RRF/ranking, filtering, or reranking should be comparable on the same benchmark.

## 5. Query logging

Store diagnostics while respecting privacy/retention requirements.

Useful fields:

```text
query_id
timestamp
retrieval profile
query hash
embedding model
latency
candidate counts
returned source IDs
filters
error state
```

Raw learner text should follow the platform privacy policy rather than being stored by default merely for vector debugging.

## 6. PostgreSQL monitoring

Use tools such as:

```text
pg_stat_statements
pg_stat_progress_create_index
EXPLAIN (ANALYZE, BUFFERS)
```

Track index build duration, vacuum behavior, index bytes, ANN latency and exact-query baseline latency.

## 7. Scale stages

### Stage 1 — development / early corpus

```text
single PostgreSQL instance
HNSW
full vectors
< approximately 1M active vectors
```

### Stage 2 — growing corpus

```text
millions to tens of millions of vectors
larger RAM
read replica for retrieval
careful HNSW sizing
evaluate half-precision indexes
```

### Stage 3 — high retrieval load

```text
retrieval-specific read replicas
pool/resource isolation
model-specific physical design
possible quantization
aggressive telemetry
```

### Stage 4 — reconsider dedicated vector infrastructure

Only after measured PostgreSQL cost/latency/operational limits justify the move.

## 8. Backup and recovery priorities

Embeddings are reproducible.

Disaster-recovery priority should therefore be:

1. canonical corpus;
2. provenance and audit;
3. reviewed taxonomy/knowledge assertions;
4. pipeline/run state;
5. vector configuration/model registry;
6. generated numeric embeddings.

Numeric vectors can be regenerated if necessary.

## 9. Capacity model

Estimate:

```text
number_of_chunks
× vector_dimensions
× bytes_per_component
+ row overhead
+ HNSW overhead
+ relational/FTS indexes
```

Measure separately:

- base vector-table bytes;
- HNSW bytes;
- active-model bytes;
- deprecated-model bytes.

Model migration temporarily duplicates storage.

## 10. Production acceptance criteria

The vector layer is ready only when:

- every result is source-traceable;
- ANN recall is measured against exact search;
- hybrid search beats vector-only on the benchmark;
- model migration is reversible;
- incomplete backfills are visible;
- hard filters are respected;
- p95 latency meets the tutor requirement;
- retrieval regressions are caught before deployment.
