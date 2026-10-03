# Product Requirements

## Objective

Build a reliable corpus pipeline for competition math preparation that ingests existing structured spreadsheet data and paper artifacts, converts the content to canonical markdown, indexes by category and skills, and serves retrieval through APIs for agentic usage.

## In Scope

- Import from the master workbook tabs into canonical corpus entities.
- Attach competition/year/paper/question lineage.
- Convert paper/question content to markdown.
- Preserve full-document and chunk-level storage.
- Build category-aware RAG query capability.
- Expose read APIs for downstream learning assistants.

## Out Of Scope (v1)

- Auto-grading of student answers.
- Adaptive scheduling engine.
- Student-facing UI application.
- Human feedback loop tooling beyond basic correction endpoints.

## Functional Requirements

- PRD-001: System shall ingest all configured tabs from the spreadsheet source.
- PRD-002: System shall map rows to normalized entities (competition, event, paper, question, concept, tag).
- PRD-003: System shall preserve provenance for each field, including source tab and row identifier.
- PRD-004: System shall convert textual content to markdown with deterministic formatting.
- PRD-005: System shall support storing each paper as full document and as segmented chunks.
- PRD-006: System shall support question-level and concept-level retrieval.
- PRD-007: System shall support adding new categories without schema-breaking migrations.
- PRD-008: System shall expose APIs for search, retrieval, and metadata inspection.
- PRD-009: System shall support question prompts such as "Show me all questions on Probability".

## Non-Functional Requirements

- PRD-010: Deterministic ingestion, idempotent reruns, and replay safety.
- PRD-011: Observability with batch-level status, per-row errors, and retry audit trails.
- PRD-012: PII-safe operations (student data separated from corpus content).
- PRD-013: Query latency target p95 <= 2.5s for top-20 retrieval.
- PRD-014: Cost-aware indexing and embedding refresh strategy.

## Success Metrics

- Corpus coverage >= 98% of valid source rows ingested.
- Validation pass >= 99% for required fields.
- Topic retrieval precision@10 >= 0.8 on evaluation set.
- First complete corpus build run reproducible from clean environment.
