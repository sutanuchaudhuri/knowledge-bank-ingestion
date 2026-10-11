# API Requirements

## Purpose

Expose corpus data to downstream agentic systems and the student learning application via a well-defined REST/JSON API. The API is consumed by:
- The future student-facing learning assistant.
- Agentic orchestrators that select practice questions, generate hints, and track topics.
- Admin tools for corpus management.

## API Design Principles

- JSON over HTTPS.
- Versioned under `/v1/`.
- Authentication via Google Cloud Identity or API key (for internal services).
- Pagination for list endpoints: `page_token` cursor pattern.
- Consistent error envelope: `{ "error": { "code": string, "message": string } }`.

## Endpoints

### Corpus Search

#### API-001: Topic Question List
```
GET /v1/questions?topic=Probability&difficulty=medium&limit=20&page_token=<cursor>
```
Returns questions matching topic and optional difficulty filter.

Response:
```json
{
  "questions": [
    {
      "question_id": "AMC10A_2023_Q05",
      "paper_id": "PAPER_AMC10A_2023",
      "competition": "AMC10",
      "year": 2023,
      "q_number": 5,
      "primary_topic": "Probability",
      "subtopic": "Conditional Probability",
      "difficulty_band": "medium",
      "correct_answer": "C",
      "doc_url": "/v1/documents/questions/AMC10A_2023_Q05"
    }
  ],
  "total": 142,
  "next_page_token": "eyJv..."
}
```

#### API-002: Semantic Search
```
POST /v1/search
Content-Type: application/json

{
  "query": "probability with replacement from a bag of marbles",
  "filters": {
    "topic": "Probability",
    "competition": ["AMC10", "AMC12"],
    "difficulty": ["medium", "hard"]
  },
  "limit": 10,
  "include_chunks": true
}
```

Response: ranked list of matching questions or chunks with relevance scores.

#### API-003: Category Index
```
GET /v1/categories
GET /v1/categories/{topic_id}
GET /v1/categories/{topic_id}/subtopics
```
Returns topic tree with question counts, usable for building category browsers.

Response for `/v1/categories`:
```json
{
  "categories": [
    {
      "topic_id": "PROB",
      "display_name": "Probability",
      "question_count": 142,
      "subtopics": [
        { "subtopic_id": "PROB_COND", "display_name": "Conditional Probability", "question_count": 29 }
      ]
    }
  ]
}
```

### Document Retrieval

#### API-004: Get Full Paper
```
GET /v1/documents/papers/{paper_id}?format=md
```
Returns the full paper markdown or structured JSON representation.

#### API-005: Get Question Document
```
GET /v1/documents/questions/{question_id}?format=md
GET /v1/documents/questions/{question_id}?format=json
```
Returns the canonical question document in markdown or structured form.

#### API-006: Get Question Chunk
```
GET /v1/documents/chunks/{chunk_id}
```
Returns a specific chunk with metadata.

### Corpus Metadata

#### API-007: List Competitions
```
GET /v1/competitions
```

#### API-008: List Papers For Competition
```
GET /v1/competitions/{competition_id}/papers?year=2023
```

#### API-009: Paper Detail
```
GET /v1/papers/{paper_id}
```
Returns paper metadata including question count, classification status, and Drive links.

### Corpus Management (Admin)

#### API-010: Ingest Status
```
GET /v1/admin/batches/{batch_id}/status
```
Returns per-stage status, counts, and error summaries.

#### API-011: Trigger Index Rebuild
```
POST /v1/admin/indexes/rebuild
```
Queues a background task to rebuild category indexes.

#### API-012: Add Category
```
POST /v1/admin/categories
{
  "canonical_topic_id": "NEW_TOPIC_ID",
  "domain": "Algebra",
  "topic": "Matrix Algebra",
  "node_type": "Topic",
  "parent_id": "ALG"
}
```
Writes a new taxonomy node to the Canonical Taxonomy Sheets tab.

## Authentication And Authorisation

- API-013: All endpoints require a valid Google Cloud identity token (Bearer) or an issued API key.
- API-014: Admin endpoints require an IAM role with `corpus.admin` permission.
- API-015: Read endpoints may accept service-account credentials for agentic callers.
- API-016: API keys are rotated quarterly; keys never logged in plain text.

## Rate Limiting

- API-017: Public read endpoints: 60 requests per minute per key.
- API-018: Semantic search: 20 requests per minute per key (embedding cost management).
- API-019: Admin endpoints: 10 requests per minute.

## Deployment

- API-020: Deployed as a Cloud Run service (`mathbank-api`).
- API-021: Framework: FastAPI (Python 3.11+).
- API-022: Container image built and pushed to Artifact Registry via Cloud Build.
- API-023: Service account has Firestore read, Sheets read, GCS read, and Vector Search query permissions.
- API-024: Minimum instances: 1 (no cold start for student-facing queries).

## OpenAPI Specification

- API-025: A machine-readable OpenAPI 3.1 spec is generated at `/v1/openapi.json`.
- API-026: Spec is used by agentic callers to auto-discover available endpoints and schema.
