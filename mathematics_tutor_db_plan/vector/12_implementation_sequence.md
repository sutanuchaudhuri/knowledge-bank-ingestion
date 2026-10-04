# Vector 12 — Implementation Sequence

## Phase 0 — prerequisite

Complete canonical identifiers for:

- problem;
- solution;
- solution step;
- concept;
- technique;
- provenance/source.

Vector design depends on stable IDs.

## Phase 1 — extension and schema

1. enable `pgvector` and `pg_trgm`;
2. create `search.embedding_model`;
3. create `search.preprocessing_profile`;
4. create `search.representation`;
5. create `search.chunk`;
6. create `search.embedding`;
7. create `search.embedding_job`;
8. add FTS/trigram indexes;
9. add integrity checks.

Deliverable: migrations only, no semantic search traffic yet.

## Phase 2 — representation generator

Implement deterministic rendering for:

- `PROBLEM_STATEMENT`;
- `SOLUTION_FULL`;
- `SOLUTION_STEP`;
- `CONCEPT_DEFINITION`;
- `TECHNIQUE_SIGNATURE`.

Every representation must produce a stable content hash.

Deliverable: representation/chunk backfill with counts and reconciliation.

## Phase 3 — first embedding model

1. register one model/revision;
2. generate vectors for a representative corpus slice;
3. validate dimensions;
4. add model-specific HNSW index;
5. expose exact and ANN diagnostic queries.

Deliverable: semantic search over a controlled corpus subset.

## Phase 4 — evaluation benchmark

Create real test cases from Mathematics Tutor use cases.

At minimum:

- 50 similar-problem queries;
- 20 concept explanation queries;
- 20 solution-step analogy queries;
- 20 taxonomy/misconception queries.

Record human relevance judgments.

Deliverable: repeatable retrieval-quality report.

## Phase 5 — hybrid retrieval

Implement:

- FTS candidate retrieval;
- semantic retrieval;
- RRF fusion;
- SQL filters;
- deduplication;
- retrieval profiles.

Compare against vector-only and lexical-only baselines.

Deliverable: `/v1/search/problems` and `/v1/search/knowledge`.

## Phase 6 — full corpus backfill

Use durable `pipeline.run` and work-item state.

Required completion checks:

```text
expected active chunks
embedded active chunks
missing chunks
failed chunks
stale embeddings
```

No run is marked completed with unresolved unexplained gaps.

## Phase 7 — graph integration

Use vectors to propose candidate relations and graph/taxonomy traversal to constrain retrieval.

Do not make semantic-neighbor edges canonical automatically.

Deliverable: graph-assisted retrieval profile.

## Phase 8 — learner-aware retrieval

Add:

- attempt-history exclusion;
- mastery filters;
- target difficulty;
- prerequisite constraints;
- hint-level visibility rules.

Deliverable: `NEXT_PROBLEM`, `HINT`, and `DIAGNOSE_ATTEMPT` retrieval profiles.

## Phase 9 — model migration framework

Register a second embedding model and perform a complete dry-run migration:

```text
register → backfill → index → evaluate → canary → activate → rollback test
```

Do this before the first urgent model migration is needed.

## Phase 10 — scale optimization

Only after metrics justify it, evaluate:

- retrieval read replicas;
- half-precision indexing;
- binary quantization;
- partitioning;
- IVFFlat for selected workloads;
- external vector infrastructure.

## Definition of done

The vector subsystem is not complete merely when `ORDER BY embedding <=> query` works.

It is complete when:

- lineage is auditable;
- re-embedding is restartable;
- hybrid retrieval is evaluated;
- hard filters are correct;
- ANN recall is measured;
- model migration is reversible;
- every tutor result can be traced to canonical content;
- missing/stale embeddings are automatically detectable.
