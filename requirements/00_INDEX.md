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

## Scope Summary

- Source data: multi-tab spreadsheet corpus and related PDF/HTML artifacts.
- Output artifacts: canonical markdown per paper and per question-part chunks.
- Storage model: store each document as whole object and chunked objects.
- Indexing model: category + concept + competition + year + difficulty indexes.
- Retrieval model: hybrid reviewed graph evidence, vector similarity and lexical RAG for curriculum and question search.
- Integration model: APIs for future agentic workflows.

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
- Version baseline: v1.0 for spreadsheet migration and first production RAG.
