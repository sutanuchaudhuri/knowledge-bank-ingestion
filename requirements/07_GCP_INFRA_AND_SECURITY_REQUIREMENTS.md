# GCP Infrastructure And Security Requirements

## Google Cloud Project

- GCP-001: All resources live in a single GCP project dedicated to the MathBank corpus platform.
- GCP-002: Project ID convention: `mathbank-prod` (production), `mathbank-dev` (development).
- GCP-003: Billing budget alert at 80% and 100% of monthly budget.

## Services Used

| Service | Purpose |
|---|---|
| Google Sheets API | Corpus metadata source of truth and sync target |
| Google Drive API | Artifact file storage (markdown, PDFs, visuals) |
| Cloud Run | API service hosting |
| Cloud Storage | Bulk markdown and source file archive |
| Firestore | Structured question and category query index |
| Vertex AI Vector Search | Embedding index for semantic RAG |
| Vertex AI (text-embedding-004) | Embedding generation |
| Artifact Registry | Container image storage |
| Cloud Build | CI/CD pipeline |
| Secret Manager | Credential and API key storage |
| Cloud Logging | Structured logs from pipeline and API |
| Cloud Monitoring | Metrics and alerts |

## Identity And Access Management

- GCP-004: A dedicated service account `corpus-pipeline@mathbank-prod.iam.gserviceaccount.com` is used for all automated pipeline operations.
- GCP-005: A separate service account `corpus-api@mathbank-prod.iam.gserviceaccount.com` is used for the API Cloud Run service.
- GCP-006: Principle of least privilege; each service account has only the permissions listed below.

### Pipeline Service Account Permissions
- `roles/sheets.editor` (via Sheets API OAuth scope)
- `roles/drive.file` (access only to pipeline-created files)
- `roles/storage.objectAdmin` on `gs://mathbank-corpus-docs/`
- `roles/datastore.user` on Firestore database
- `roles/aiplatform.user` for embedding and Vector Search upsert
- `roles/secretmanager.secretAccessor`

### API Service Account Permissions
- `roles/datastore.viewer` on Firestore database
- `roles/storage.objectViewer` on `gs://mathbank-corpus-docs/`
- `roles/aiplatform.user` for Vector Search query

## Secret Management

- GCP-007: All secrets stored in Secret Manager; no secrets in environment variables or source code.
- GCP-008: Secrets accessed via the Secret Manager Python SDK at runtime.
- GCP-009: Required secrets:
  - `corpus-spreadsheet-id`
  - `corpus-drive-root-folder-id`
  - `embedding-api-key` (if using OpenAI fallback)
  - `corpus-api-keys` (issued API keys for service callers)

## Cloud Storage Layout

```
gs://mathbank-corpus-docs/
  papers/
    <paper_id>.md
  questions/
    <question_id>.md
  chunks/
    <chunk_id>.md
  index/
    categories.md
    topics/
      <topic_slug>.md
    competitions/
      <competition_id>.md
    difficulty/
      <band>.md
  source/
    <competition_id>/
      <year>/
        <test_id>/
          problem.pdf
          solution.pdf
```

- GCP-010: Bucket versioning enabled; objects retained for 90 days on deletion.
- GCP-011: Bucket is not publicly accessible; access is via signed URLs or service account.

## Firestore Database

- GCP-012: Native mode Firestore in the same region as the API Cloud Run service.
- GCP-013: Collections:
  - `questions` — one document per question_id.
  - `papers` — one document per paper_id.
  - `categories` — one document per canonical_topic_id.
  - `chunks` — one document per chunk_id (metadata only; content in GCS).
- GCP-014: Composite indexes for common query patterns:
  - (primary_topic, difficulty_band)
  - (competition_id, year)
  - (primary_topic, subtopic)

## Vertex AI Vector Search

- GCP-015: One index per environment (dev, prod).
- GCP-016: Dimension: 768 (text-embedding-004).
- GCP-017: Approximate neighbours algorithm: HNSW with 100 leaves.
- GCP-018: Index is updated incrementally via streaming upsert at ingest time.
- GCP-019: Deployed endpoint has a minimum replica count of 1.

## Cloud Run API Service

- GCP-020: Region: `us-central1` or match Firestore region.
- GCP-021: Min instances: 1, max instances: 10.
- GCP-022: Memory: 512Mi, CPU: 1.
- GCP-023: HTTPS only; HTTP redirected.
- GCP-024: Custom domain optional; internal DNS sufficient for agentic callers.
- GCP-025: Ingress: all (restrict to internal + Cloud Run invokers once callers are known).

## CI/CD

- GCP-026: Cloud Build trigger on push to `main` branch in the pipeline repository.
- GCP-027: Build steps:
  1. Run `pytest` (unit tests).
  2. Build container image.
  3. Push to Artifact Registry.
  4. Deploy to Cloud Run.
- GCP-028: Rollback: prior container image tag retained; rollback via `gcloud run deploy --image <prev-tag>`.

## Logging And Monitoring

- GCP-029: Pipeline scripts emit structured JSON logs to Cloud Logging via `google-cloud-logging` SDK.
- GCP-030: API service emits request/response structured logs (exclude question content from logs).
- GCP-031: Alerting policies:
  - API error rate > 5% over 5 minutes.
  - Pipeline batch failure (any stage exit code != 0).
  - Embedding cost anomaly (> 2x daily baseline).

## Security Posture

- GCP-032: No student personal data stored in corpus (corpus is question content only).
- GCP-033: API keys never returned in API responses or stored in logs.
- GCP-034: All inter-service communication uses service-account tokens; no static passwords.
- GCP-035: Security review required before opening any API endpoint to the public internet.
- GCP-036: OWASP Top 10 mitigations applied to the API service:
  - Input validation on all query parameters.
  - Rate limiting to prevent abuse.
  - No SQL injection surface (Firestore uses typed queries).
  - No XML parsing (JSON only).
  - Dependency scanning via `pip-audit` in CI.
