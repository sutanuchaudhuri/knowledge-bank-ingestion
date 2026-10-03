# Mathematics Tutor Data Platform — Database, Graph, and API Plan

## Purpose

This repository is the implementation blueprint for turning a large mathematics corpus—competition papers, problems, solutions, concepts, techniques, prerequisite chains, taxonomy labels, source metadata, and learner interactions—into a durable queryable platform.

The architecture has three principal layers:

1. **PostgreSQL — system of record.** All authoritative content, ingestion state, provenance, taxonomy assignments, solution structure, and audit data live here first.
2. **Graph database — derived semantic projection.** Concepts, techniques, problems, prerequisites, similarity links, and learning-path relationships are projected from PostgreSQL into a property graph.
3. **REST API — controlled read/write boundary.** Corpus ingestion, taxonomy edits, problem lookup, graph traversal, search, tutor retrieval, and batch operations are exposed through versioned API contracts.

The governing rule is: **nothing exists only in the graph.** Every durable graph node and edge must be reproducible from PostgreSQL or be recorded there as an asserted relationship before projection.

## Recommended initial stack

- PostgreSQL 16+
- `pgvector` for embeddings
- `pg_trgm` + PostgreSQL full-text search
- Neo4j 5.x or another property-graph database for graph projection
- Python/FastAPI for REST services
- SQLAlchemy 2 + Alembic, or equivalent typed persistence layer
- Redis optional for cache/short-lived jobs, never as canonical state
- Object storage for PDFs/images/large artifacts, with metadata and checksums in PostgreSQL

## Document map

### PostgreSQL

- `postgres/01_architecture_principles.md`
- `postgres/02_canonical_domain_model.md`
- `postgres/03_reference_schema_ddl.md`
- `postgres/04_taxonomy_and_knowledge_model.md`
- `postgres/05_ingestion_backfill_and_run_state.md`
- `postgres/06_provenance_audit_and_review.md`
- `postgres/07_search_embeddings_and_indexing.md`
- `postgres/08_query_patterns_and_materialized_views.md`
- `postgres/09_migrations_operations_and_scaling.md`

### Graph database

- `graph/01_graph_architecture.md`
- `graph/02_nodes_edges_and_constraints.md`
- `graph/03_postgres_to_graph_projection.md`
- `graph/04_query_patterns_and_cypher.md`
- `graph/05_learning_paths_and_reasoning.md`
- `graph/06_similarity_misconceptions_and_student_state.md`
- `graph/07_graph_versioning_reconciliation_and_ops.md`

### REST API

- `rest/01_api_architecture.md`
- `rest/02_resource_model_and_identifiers.md`
- `rest/03_query_and_search_endpoints.md`
- `rest/04_insert_update_and_idempotency.md`
- `rest/05_batch_run_control_and_status.md`
- `rest/06_graph_and_tutor_endpoints.md`
- `rest/07_security_validation_observability.md`

### Cross-cutting

- `crosscut/01_identifier_version_contract.md`
- `crosscut/02_end_to_end_data_flow.md`
- `crosscut/03_implementation_roadmap.md`
- `crosscut/04_testing_and_acceptance.md`

### Agentic layer (implemented — Google ADK + OpenAI, React frontend)

- `agent/00_index.md` — start here
- `agent/01_architecture_and_design.md`
- `agent/02_ingestion_pipeline_flow.md`
- `agent/03_inference_and_retrieval_flow.md`
- `agent/04_example_queries.md`
- `agent/05_frontend_and_api_contract.md`
- `agent/06_security_and_access_model.md`

Implementation: `mathbank-agent/` (ADK agent + tools), `mathbank-web/`
(React chat UI), both consuming `mathbank-rest/`. See
`00_implementation_progress.md` for the full build log of every layer
(Postgres through vector/RAG).

## Recommended implementation order

Implement PostgreSQL first through migrations and ingestion state. Load a representative slice of the corpus, validate provenance and taxonomy, then implement REST reads/writes. Only after those contracts stabilize should the graph projection be built. This prevents graph schema churn from becoming the source of truth.
