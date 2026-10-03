# Roadmap And Acceptance Criteria

## Phases

### Phase 0 — Foundation (1–2 weeks)
Bootstrap the environment, validate source data, and confirm all APIs are accessible.

| Task | Owner | Done When |
|---|---|---|
| Install Python env and project dependencies | Dev | `pip install -e .` succeeds |
| Enable Google Drive and Sheets APIs | Dev | Service account can list sheet tabs |
| Read all tabs from master Excel file | Dev | `ingest_excel.py --stage discover` runs without error |
| Taxonomy pre-load validates cleanly | Dev | Zero validation errors on Canonical_Taxonomy tab |
| GCS bucket created and service account granted access | Dev | Upload test file succeeds |

### Phase 1 — Excel Ingestion And Markdown (2–3 weeks)
Full import of all spreadsheet rows into canonical entities and markdown artifacts.

| Task | Owner | Done When |
|---|---|---|
| Stage 1 (row extraction) for all tabs | Dev | All `_raw.jsonl` files generated |
| Stage 2 (validation) reports errors | Dev | `_errors.jsonl` counts < 2% of total rows |
| Stage 3 (entity construction) for all questions | Dev | question_id assigned to every valid row |
| Stage 4 (markdown generation) for all papers | Dev | `paper.md` generated for every paper |
| Stage 4 (markdown generation) for all questions | Dev | `question.md` generated for every question |
| Stage 5 (Drive upload) mirrors all markdown | Dev | Drive folder matches local file tree |
| Stage 6 (Sheets sync) populates Question_Index | Dev | All rows in Question_Index tab |
| Category index files generated | Dev | `categories.md` + all topic index files present |

### Phase 2 — Vector Index And RAG (2–3 weeks)
Embedding and retrieval layer built and validated.

| Task | Owner | Done When |
|---|---|---|
| Vertex AI embedding model accessible | Dev | Test embed returns 768-dim vector |
| Stage 7 (chunking and embedding) runs | Dev | All chunks embedded and upserted to Vector Search |
| Firestore populated with question metadata | Dev | Query by topic returns correct results |
| RAG evaluation set created (50 queries) | Dev | `evals/topic_queries.jsonl` committed |
| Topic filter precision@10 >= 0.8 | Dev | `eval_rag.py` passes threshold |
| Semantic search returns correct results | Dev | Manual spot-check of 10 queries passes |

### Phase 3 — API Service (2–3 weeks)
REST API deployed on Cloud Run, ready for agentic callers.

| Task | Owner | Done When |
|---|---|---|
| FastAPI app scaffolded | Dev | `GET /v1/categories` returns data |
| All Phase 1+2 endpoints implemented | Dev | All API-001 through API-012 respond correctly |
| OpenAPI spec generated at `/v1/openapi.json` | Dev | Spec validates with Redocly |
| Authentication enforced | Dev | Unauthenticated requests rejected with 401 |
| Rate limiting enforced | Dev | 61st request in a minute returns 429 |
| Cloud Run deployment succeeds | Dev | Service URL returns 200 on health check |
| API key issued for first agentic caller | Dev | End-to-end test from agentic system passes |

### Phase 4 — Hardening And Monitoring (1 week)
Production readiness.

| Task | Owner | Done When |
|---|---|---|
| Cloud Logging structured output verified | Dev | Logs appear in Cloud Console |
| Alerting policies active | Dev | Test alert fires and is received |
| `pip-audit` passes in CI | Dev | Zero known-vulnerable dependencies |
| Rollback procedure documented and tested | Dev | Previous image successfully redeployed |
| Corpus coverage report generated | Dev | >= 98% of source rows ingested |

## Acceptance Criteria Summary

- AC-001: All tabs from the master spreadsheet are processed without data loss on valid rows.
- AC-002: Every question has a canonical markdown document stored in GCS and on Drive.
- AC-003: Querying `GET /v1/questions?topic=Probability` returns all questions tagged to Probability.
- AC-004: Querying `POST /v1/search` with a free-text math description returns semantically relevant questions.
- AC-005: Adding a new category via `POST /v1/admin/categories` makes it immediately queryable.
- AC-006: Full pipeline is reproducible from a clean GCS and Firestore state using only the source spreadsheet.
- AC-007: API p95 latency <= 2.5s under 20 concurrent requests.
- AC-008: No secrets are visible in code, logs, or API responses.

## Future Phases (Out Of Scope For v1)

- Student performance tracking and adaptive question selection.
- Automated paper ingestion from web sources (PDF download and classification).
- Student-facing web application UI.
- Hint generation and worked-solution agentic flows.
- Multi-student support and parent/teacher dashboard.
