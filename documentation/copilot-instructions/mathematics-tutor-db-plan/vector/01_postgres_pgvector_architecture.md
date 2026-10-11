# Vector 01 — PostgreSQL + pgvector Architecture

## 1. Purpose

The Mathematics Tutor needs semantic retrieval across competition problems, solutions, solution steps, concepts, techniques, hints, misconceptions, proofs, derivations, and eventually learner artifacts.

The recommended first production architecture is **PostgreSQL + pgvector**, not a separate vector-database service.

PostgreSQL remains the canonical system of record. Vector search is an indexed retrieval capability inside PostgreSQL.

This gives the platform four retrieval modes in one data platform:

1. **Relational retrieval** — competition, year, paper, difficulty, source, review state, learner state.
2. **Lexical retrieval** — PostgreSQL full-text search and trigram search.
3. **Semantic retrieval** — pgvector nearest-neighbor search.
4. **Knowledge retrieval** — taxonomy joins in PostgreSQL and optional graph traversal in the graph projection.

The tutor combines them rather than treating vector similarity as the only search signal.

## 2. Architectural principle

The vector layer must never become an independent source of truth.

A vector row is always derived from a canonical source entity such as:

- problem;
- solution;
- solution step;
- concept;
- technique;
- hint;
- theorem;
- worked example;
- misconception;
- curriculum note;
- learner artifact.

The canonical text and provenance remain in PostgreSQL domain tables.

The vector layer stores:

- searchable representation;
- semantic chunk boundaries;
- preprocessing version;
- embedding-model version;
- embedding vector;
- retrieval metadata;
- content hashes;
- indexing/backfill state.

Every embedding must be regenerable.

## 3. Logical deployment

```text
                         Mathematics corpus
                     PDFs / HTML / CSV / notes
                               │
                               ▼
                     ingestion / normalization
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                        PostgreSQL                           │
│                                                             │
│ core.*        canonical papers/problems/solutions           │
│ knowledge.*   concepts/techniques/assertions                │
│ pipeline.*    runs/work-items/checkpoints                   │
│ search.*      representations/chunks/vectors/FTS            │
│ audit.*       provenance/review/mutations                   │
│                                                             │
│     pgvector + pg_trgm + PostgreSQL full-text search        │
└────────────────────────────┬────────────────────────────────┘
                             │
             ┌───────────────┴──────────────────┐
             ▼                                  ▼
        REST / Tutor API                  Graph projection
        hybrid retrieval                  Neo4j/property graph
```

## 4. Why PostgreSQL first

Most tutor searches are semantic **and** structured.

Examples:

- Find problems similar to this one, but only AMC 10 from 2015–2026.
- Find an easier problem involving power of a point.
- Retrieve telescoping examples that do not require generating functions.
- Find a similar solution approach only from human-reviewed sources.
- Find prerequisite examples restricted to concepts a learner has already mastered.

With pgvector, these constraints remain SQL joins rather than duplicated metadata filters maintained in another product.

```sql
SELECT ...
FROM search.embedding e
JOIN search.chunk c ON c.chunk_id = e.chunk_id
JOIN core.problem p ON p.problem_id = c.problem_id
JOIN core.paper pa ON pa.paper_id = p.paper_id
JOIN knowledge.problem_concept pc ON pc.problem_id = p.problem_id
WHERE pa.paper_type = 'AMC10'
  AND pc.concept_id = :concept_id
ORDER BY e.embedding <=> :query_embedding
LIMIT 20;
```

## 5. Logical schema

Keep vector objects under the `search` schema.

Recommended objects:

```text
search.embedding_model
search.preprocessing_profile
search.retrieval_profile
search.representation
search.chunk
search.embedding
search.embedding_job
search.query_log
search.retrieval_evaluation
search.retrieval_judgment
```

Do not put a single embedding column directly on `core.problem` because:

- one problem can have several semantic representations;
- solutions and steps need independent retrieval;
- multiple embedding models may coexist;
- embedding dimensions may change;
- chunking changes over time;
- embeddings are disposable derived data.

## 6. Representation vs embedding

Keep them separate.

```text
canonical source
      │
      ▼
representation
      │
      ├── representation kind
      ├── preprocessing profile
      └── content hash
      │
      ▼
chunk(s)
      │
      ▼
embedding
      ├── model A / revision 1
      ├── model B / revision 3
      └── future local math model
```

Examples of representation kinds:

- `PROBLEM_STATEMENT`
- `STRUCTURAL_NORMALIZED`
- `PROBLEM_WITH_TAXONOMY`
- `SOLUTION_FULL`
- `SOLUTION_STEP`
- `TECHNIQUE_SIGNATURE`
- `CONCEPT_DEFINITION`
- `CONCEPT_INTUITION`
- `MISCONCEPTION`

## 7. V1 recommendation

Use:

- PostgreSQL 16+
- pgvector
- HNSW indexes
- cosine distance for general text-semantic embeddings unless the selected model specifies otherwise
- PostgreSQL full-text search for lexical search
- Reciprocal Rank Fusion for the first hybrid ranker
- optional cross-encoder/LLM reranking later

Do not add a second vector service until measured scale or latency justifies it.

## 8. Operational isolation

Even when colocated, vector work should be isolated logically:

- independent `search` schema;
- separate retrieval connection pool;
- independent embedding workers;
- model-specific index migrations;
- read replica for search when needed;
- query-budget and timeout controls;
- vector latency/recall metrics.

This creates an easy future split boundary without paying the synchronization cost today.

## 9. Future split criteria

Re-evaluate a dedicated vector system only when measured evidence shows one or more of:

1. active vectors no longer fit an economically useful PostgreSQL working set;
2. semantic QPS dominates relational workload;
3. p95/p99 retrieval remains unacceptable after tuning/hardware/read replicas;
4. geo-distributed vector retrieval becomes necessary;
5. vector operations require a different independent scaling model;
6. corpus grows into hundreds of millions/billions of active vectors;
7. specialized GPU vector infrastructure has a clear measured benefit.

## 10. Non-negotiable invariants

1. Every vector has a canonical source.
2. Every vector records the exact embedding model revision.
3. Every representation has a deterministic content hash.
4. Re-embedding preserves lineage rather than silently overwriting history.
5. Every tutor result can be traced to source text and provenance.
6. Exact user filters remain hard filters.
7. Vector similarity is not mathematical equivalence.
8. Vector-discovered graph relationships are candidates until asserted/reviewed.
