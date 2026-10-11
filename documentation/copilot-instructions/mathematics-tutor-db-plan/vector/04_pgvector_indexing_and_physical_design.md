# Vector 04 — pgvector Indexing and Physical Design

## 1. Exact and approximate retrieval

The platform should support both.

Use exact search for:

- evaluation baselines;
- small/strongly filtered candidate sets;
- recall measurement;
- correctness checks.

Use approximate nearest-neighbor search for interactive retrieval at scale.

## 2. Default index: HNSW

Start with HNSW for active semantic models.

```sql
CREATE INDEX CONCURRENTLY idx_embedding_model_v1_hnsw
ON search.embedding
USING hnsw ((embedding::vector(1536)) vector_cosine_ops)
WITH (m = 16, ef_construction = 64)
WHERE embedding_model_id = 'MODEL_UUID'
  AND status = 'ACTIVE';
```

Treat `m=16` and `ef_construction=64` as starting defaults, not sacred tuning values.

HNSW is attractive because it has a strong speed/recall tradeoff and can be created without a training stage.

## 3. Query-time tuning

Use transaction-local settings.

```sql
BEGIN;
SET LOCAL hnsw.ef_search = 100;
SET LOCAL hnsw.iterative_scan = strict_order;

SELECT ...
ORDER BY embedding::vector(1536) <=> :query_embedding
LIMIT 50;
COMMIT;
```

Higher `ef_search` generally increases search effort and recall at the cost of latency.

## 4. Filtered ANN searches

Approximate retrieval plus SQL filters needs special attention because filtering may remove ANN candidates after index scanning.

Use iterative scans for filtered retrieval when required:

```sql
SET LOCAL hnsw.iterative_scan = strict_order;
```

or, where appropriate:

```sql
SET LOCAL hnsw.iterative_scan = relaxed_order;
```

If relaxed ordering is used, rerank/re-sort the candidate set before final output.

## 5. IVFFlat

IVFFlat is a secondary option.

Consider it when:

- index construction speed is more important;
- memory must be reduced;
- the corpus is relatively stable;
- measured recall is acceptable.

It should not be the initial default.

IVFFlat needs enough rows to train useful clusters, a chosen list count, and query-time `probes` tuning.

## 6. Multiple embedding dimensions

Use one model-specific index for each active model/dimension combination.

```sql
CREATE INDEX idx_emb_model_a_hnsw
ON search.embedding
USING hnsw ((embedding::vector(1536)) vector_cosine_ops)
WHERE embedding_model_id = 'MODEL_A_UUID';

CREATE INDEX idx_emb_model_b_hnsw
ON search.embedding
USING hnsw ((embedding::vector(3072)) vector_cosine_ops)
WHERE embedding_model_id = 'MODEL_B_UUID';
```

This supports zero-downtime migration:

1. register model B;
2. backfill model B embeddings;
3. build B index;
4. benchmark A vs B;
5. canary B;
6. switch retrieval profile;
7. retire A later.

## 7. Ordinary indexes still matter

Vector indexes do not replace relational indexes.

```sql
CREATE INDEX idx_chunk_problem
ON search.chunk(problem_id);

CREATE INDEX idx_chunk_concept
ON search.chunk(concept_id);

CREATE INDEX idx_chunk_technique
ON search.chunk(technique_id);

CREATE INDEX idx_repr_kind
ON search.representation(representation_kind, status);

CREATE INDEX idx_embedding_model_status
ON search.embedding(embedding_model_id, status);
```

Core tables should retain indexes for competition, paper, year, difficulty, review state, and other common filters.

## 8. Partial vector indexes

Create special partial HNSW indexes only for very high-value stable slices with demonstrated need.

Do not create one vector index per concept; maintenance cost will explode.

## 9. Partitioning

Partition only after measurements justify it.

Potential keys:

- embedding model family;
- major corpus family;
- tenant/environment;
- active vs archival content.

Avoid extremely fine-grained partitions.

## 10. Half precision

At larger scale, evaluate `halfvec` indexing to reduce working-set/index size.

A useful pattern is:

```text
full vector storage
      ↓
half-precision ANN candidate generation
      ↓
full-vector reranking
```

Only adopt after recall evaluation.

## 11. Binary quantization

For very large indexes, pgvector supports binary quantization with reranking.

Treat it as an optimization stage, not a V1 requirement.

## 12. Index lifecycle

```text
backfill vectors
    ↓
validate dimensions
    ↓
CREATE INDEX CONCURRENTLY
    ↓
ANALYZE
    ↓
benchmark recall/latency
    ↓
activate retrieval profile
```

Do not route default traffic to a new model just because its backfill completed.

## 13. Recall measurement

Build exact nearest-neighbor results as the baseline and compare ANN overlap.

Representative exact evaluation:

```sql
BEGIN;
SET LOCAL enable_indexscan = off;
SELECT ...
ORDER BY embedding::vector(1536) <=> :query_embedding
LIMIT 20;
COMMIT;
```

Track recall@K together with p50/p95/p99 latency.
