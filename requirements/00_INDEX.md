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

## Scope Summary

- Source data: multi-tab spreadsheet corpus and related PDF/HTML artifacts.
- Output artifacts: canonical markdown per paper and per question-part chunks.
- Storage model: store each document as whole object and chunked objects.
- Indexing model: category + concept + competition + year + difficulty indexes.
- Retrieval model: hybrid keyword and vector RAG for curriculum and question search.
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
- Version baseline: v1.0 for spreadsheet migration and first production RAG.
