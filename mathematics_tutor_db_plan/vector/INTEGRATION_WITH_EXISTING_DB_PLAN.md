# Integration with the Existing Mathematics Tutor Database Plan

This vector package is intended to be added as a new top-level `vector/` section beside:

```text
postgres/
graph/
rest/
crosscut/
```

Recommended combined layout:

```text
mathematics_tutor_db_plan/
├── postgres/
├── vector/
│   ├── 01_postgres_pgvector_architecture.md
│   ├── 02_embedding_and_chunk_schema.md
│   ├── 03_math_aware_chunking_and_representations.md
│   ├── 04_pgvector_indexing_and_physical_design.md
│   ├── 05_hybrid_search_ranking_and_filters.md
│   ├── 06_embedding_pipeline_reembedding_and_versioning.md
│   ├── 07_vector_relational_graph_integration.md
│   ├── 08_tutor_rag_query_flows.md
│   ├── 09_scaling_monitoring_and_retrieval_evaluation.md
│   ├── 10_reference_sql_and_query_examples.md
│   ├── 11_rest_vector_search_contracts.md
│   └── 12_implementation_sequence.md
├── graph/
├── rest/
└── crosscut/
```

## Changes to the original architecture

The earlier statement that `pgvector` is merely part of PostgreSQL indexing should be strengthened:

> **Vector retrieval is a first-class subsystem implemented inside PostgreSQL using pgvector.**

The four major platform layers are therefore:

1. canonical PostgreSQL relational store;
2. PostgreSQL-native vector/search subsystem (`search.*` + pgvector + FTS);
3. derived graph projection;
4. REST/tutor service layer.

The vector subsystem is physically in PostgreSQL initially but has its own schema, lifecycle, evaluation, and operating model.

## PostgreSQL DDL integration

Extend the existing `postgres/03_reference_schema_ddl.md` with the schemas/tables in `10_reference_sql_and_query_examples.md`.

Do not store one fixed embedding directly on `core.problem`.

## REST integration

Extend the existing `rest/03_query_and_search_endpoints.md` with the contracts in `11_rest_vector_search_contracts.md`.

## Pipeline integration

Embedding backfills should reuse the existing durable `pipeline.run` / `pipeline.work_item` machinery and add vector-specific job details under `search.embedding_job`.

## Graph integration

Use the design in `07_vector_relational_graph_integration.md`: vector similarity can generate graph candidates, while graph/taxonomy traversals can constrain vector retrieval. Canonical graph-worthy assertions must still be written back to PostgreSQL before projection.
