# MathBank Corpus Requirements Index

This folder defines the implementation plan and requirements for building the MathBank competition math corpus pipeline from the master spreadsheet into a Google Cloud-backed corpus with RAG and APIs.

## Document Map

1. [01_PRODUCT_REQUIREMENTS.md](01_PRODUCT_REQUIREMENTS.md)
2. [02_DATA_MODEL_AND_STORAGE.md](02_DATA_MODEL_AND_STORAGE.md)
3. [03_INGESTION_PIPELINE_REQUIREMENTS.md](03_INGESTION_PIPELINE_REQUIREMENTS.md)
4. [04_MARKDOWN_CATALOG_REQUIREMENTS.md](04_MARKDOWN_CATALOG_REQUIREMENTS.md)
5. [05_RAG_AND_INDEXING_REQUIREMENTS.md](05_RAG_AND_INDEXING_REQUIREMENTS.md)
6. [06_API_REQUIREMENTS.md](06_API_REQUIREMENTS.md)
7. [07_GCP_INFRA_AND_SECURITY_REQUIREMENTS.md](07_GCP_INFRA_AND_SECURITY_REQUIREMENTS.md)
8. [08_ROADMAP_AND_ACCEPTANCE.md](08_ROADMAP_AND_ACCEPTANCE.md)
9. [09_PIPELINE_SEQUENCE.md](09_PIPELINE_SEQUENCE.md)
10. [10_AGENTIC_TUTOR_AND_STUDENT_MASTERY_REQUIREMENTS.md](10_AGENTIC_TUTOR_AND_STUDENT_MASTERY_REQUIREMENTS.md) — ADK/OpenAI agent architecture, scaling requirements for more papers/graph nodes/REST endpoints, and the student mastery extraction design (new `learner.*` schema, new graph attributes).
11. [11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md](11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md) — entity-relationship diagram, sequence diagrams for every end-to-end flow (ingestion, student login, attempts/mastery, agent query), how to test each flow independently, how to inject future question papers, the test framework, the precision/recall metrics framework with trend tracking, and the agentic-layer/ingestion-layer evals + feedback/analytics endpoints.
12. [12_STUDENT_PROFILE_AND_ADMIN_LOGIN_UI_REQUIREMENTS.md](12_STUDENT_PROFILE_AND_ADMIN_LOGIN_UI_REQUIREMENTS.md) — student login/register/profile dashboard UI (past attempts, strength/weakness by concept, improvement plan) and a predefined-credential admin login gating `/admin`, both an explicit bridge until real OAuth; entity-relationship diagram for the extended `learner.*` schema (`first_name`/`last_name`).
13. [13_PEDAGOGICAL_GRAPH_AND_TUTOR_REQUIREMENTS.md](13_PEDAGOGICAL_GRAPH_AND_TUTOR_REQUIREMENTS.md) — P0 measurable skills, reviewed prerequisites/hierarchy, rich graph metadata, and anonymous diagnostic/progressive-hint UI; P1 solution steps, misconceptions, versioned courses and P2 learner evidence roadmap.
14. [14_AUTOMATIC_ENRICHMENT_RECOVERY.md](14_AUTOMATIC_ENRICHMENT_RECOVERY.md) — automatic metadata recovery and publication retries.
15. [15_RELATIONSHIP_ENRICHMENT.md](15_RELATIONSHIP_ENRICHMENT.md) — semantic taxonomy relationship generation and graph publication.
16. [16_PIPELINE_JOB_CONSOLE_AND_HYBRID_RAG.md](16_PIPELINE_JOB_CONSOLE_AND_HYBRID_RAG.md) — per-paper/competition completion evidence, timestamps and live metrics across all layers; graph + vector + lexical tutor retrieval.
17. [17_DOMAIN_AND_TECHNICAL_GLOSSARY.md](17_DOMAIN_AND_TECHNICAL_GLOSSARY.md) — domain/technical vocabulary, actual database and graph representations, exact strength/weakness scoring, operational states and implemented-vs-planned distinctions.
18. [18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md) — verifiable progress tracker for the v2 pack (phases 0–13): Prasolov package import, reconciliation, step-graph projection, safety SQL and commands.
19. [19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md](19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md) — every known pitfall (source data, PostgreSQL/locking, graph, pipeline runners, credentials/tools, UI/REST, tests), each with its symptom, cause, fix or rule, and where it is enforced.
20. [20_NOT_YET_IMPLEMENTED.md](20_NOT_YET_IMPLEMENTED.md) — register of what is not built yet: open v2 phases 6–13, gaps inside delivered phases, and the verified operational backlog (failed papers, failed enrichment jobs, stale runs).
21. [21_V2_PACK_IMPLEMENTATION_AUDIT.md](21_V2_PACK_IMPLEMENTATION_AUDIT.md) — file-by-file audit of how much of the v2 pack (incl. `runtime_extension/`) is implemented (~79 % after doc 26), acceptance/golden-flow and what-not-to-do compliance; open gaps merged into 20.
22. [22_AGENT_SESSION_TRANSCRIPTS.md](22_AGENT_SESSION_TRANSCRIPTS.md) — student_id ↔ agent session link (migration 016) and rebuilding full conversations for the student or an admin.
23. [23_E2E_REGRESSION_SUITE.md](23_E2E_REGRESSION_SUITE.md) — Playwright browser regression suite: how to run, coverage, paid `@llm` opt-in, baseline.
24. [24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md](24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md) — admin Prasolov corpus dashboard (problems, solutions/steps, transformations, taxonomy, diagrams) and the measured source → Postgres → pgvector → Neo4j coverage matrix.
25. [25_LEARNING_ITEM_CONCEPT_EDGES.md](25_LEARNING_ITEM_CONCEPT_EDGES.md) — `LearningItem -[:TARGETS_CONCEPT|TARGETS_SUBCONCEPT]->` graph edges (NYI-ATB-7): contract, implementation, run results, queries, acceptance.
26. [26_GEOMETRY_RUNTIME_COMPLETION_PLAN.md](26_GEOMETRY_RUNTIME_COMPLETION_PLAN.md) — Prasolov-only completion of the runtime extension: step→technique tags (WP1), agent step-runtime tools (WP2), admin import/reconciliation/DAG review UI (WP3), outbox consumers and event lifecycle (WP4), remaining WPs, and the NULL policy + runtime population plan for non-Prasolov corpora.

## Scope Summary

- Source data: multi-tab spreadsheet corpus and related PDF/HTML artifacts.
- Output artifacts: canonical markdown per paper and per question-part chunks.
- Storage model: store each document as whole object and chunked objects.
- Indexing model: category + concept + competition + year + difficulty indexes.
- Retrieval model: hybrid reviewed graph evidence, vector similarity and lexical RAG for curriculum and question search.
- Integration model: APIs for future agentic workflows.
- Current implementation reference: [reference/](reference/) contains the canonical source-derived PostgreSQL schema/DML, Neo4j graph projection schema, REST/OpenAPI snapshot and web/agent HTTP notes.

## Naming And Versioning

- Requirement IDs use prefixes:
  - PRD-* for product requirements
  - DMR-* for data model requirements
  - IGR-* for ingestion requirements
  - MDR-* for markdown requirements
  - RAG-* for retrieval requirements
  - API-* for service requirements
  - GCP-* for infrastructure and security requirements
  - AGT-* for agentic tutor / agent-layer requirements
  - MST-* for student mastery extraction requirements
  - SPL-* for student profile / login UI requirements (and the admin login bridge)
  - PED-* for pedagogical graph and anonymous tutoring requirements
  - GOT-* for gotchas / operational pitfalls (doc 19)
- Version baseline: v1.0 for spreadsheet migration and first production RAG.
