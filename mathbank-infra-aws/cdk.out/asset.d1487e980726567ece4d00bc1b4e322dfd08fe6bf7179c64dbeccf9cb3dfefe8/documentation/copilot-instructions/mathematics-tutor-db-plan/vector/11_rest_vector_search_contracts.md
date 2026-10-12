# Vector 11 — REST Contracts for pgvector Retrieval

## 1. Design goal

Vector operations should be exposed through task-oriented APIs, not raw SQL/vector primitives.

Clients should not need to know:

- embedding dimensions;
- HNSW parameters;
- physical table names;
- active model UUIDs;
- RRF implementation details.

Those belong to versioned retrieval profiles.

## 2. Hybrid problem search

`POST /v1/search/problems`

```json
{
  "query": "cyclic quadrilateral power of a point",
  "reference_problem_id": null,
  "retrieval_profile": "SIMILAR_PROBLEM",
  "filters": {
    "competition": ["AMC 10", "AIME"],
    "year": {"gte": 2000, "lte": 2026},
    "review_status": ["VERIFIED"]
  },
  "retrieval": {
    "semantic": true,
    "lexical": true,
    "graph_expand": false
  },
  "limit": 25,
  "debug": false
}
```

Response:

```json
{
  "query_id": "...",
  "retrieval_profile": "SIMILAR_PROBLEM:v3",
  "results": [
    {
      "problem_id": "...",
      "canonical_code": "2022-AIME-I-07",
      "statement": "...",
      "matched_chunk_id": "...",
      "retrieval": {
        "semantic_rank": 2,
        "lexical_rank": 7,
        "final_rank": 1
      }
    }
  ]
}
```

## 3. Search by reference entity

`POST /v1/search/similar`

```json
{
  "entity_type": "PROBLEM",
  "entity_id": "uuid",
  "representation_kind": "PROBLEM_STATEMENT",
  "filters": {
    "exclude_same_source": true
  },
  "limit": 20
}
```

The service should reuse the stored embedding when possible instead of re-embedding canonical text.

## 4. Concept retrieval

`POST /v1/search/knowledge`

Supports concepts, techniques, hints, misconceptions, and worked examples.

```json
{
  "query": "why does telescoping cancellation work",
  "target_types": [
    "CONCEPT_DEFINITION",
    "CONCEPT_INTUITION",
    "WORKED_EXAMPLE",
    "MISCONCEPTION"
  ],
  "limit_per_type": 3
}
```

This prevents one representation type from dominating the result set.

## 5. Internal embedding API

If embedding generation is a separate worker/service boundary, keep it internal.

`POST /internal/v1/embeddings/jobs`

Payload should reference canonical representation/chunk IDs rather than allowing arbitrary untracked text for corpus embeddings.

```json
{
  "chunk_ids": ["...", "..."],
  "embedding_model_id": "...",
  "idempotency_key": "..."
}
```

## 6. Re-embedding backfill

`POST /internal/v1/vector-backfills`

```json
{
  "embedding_model_id": "new-model-uuid",
  "scope": {
    "representation_kinds": [
      "PROBLEM_STATEMENT",
      "SOLUTION_STEP"
    ]
  }
}
```

Return a persistent `run_id`.

Use the general pipeline endpoints for status:

- `GET /v1/runs/{run_id}`
- `GET /v1/runs/{run_id}/work-items`
- `POST /v1/runs/{run_id}/retry`

## 7. Retrieval profiles

`GET /v1/retrieval-profiles`

`GET /v1/retrieval-profiles/{name}`

Admin-only mutation endpoints can version profile configuration rather than editing active configuration in place.

## 8. Debug response

With authorized `debug=true`, include:

```json
{
  "embedding_model_revision": "...",
  "representation_kinds": ["..."],
  "candidate_counts": {
    "semantic": 100,
    "lexical": 68,
    "graph": 12
  },
  "hnsw": {
    "ef_search": 100,
    "iterative_scan": "strict_order"
  },
  "fusion": "RRF:v1"
}
```

Do not expose raw internal details to ordinary clients unless needed.

## 9. Insert semantics

The public content-ingestion APIs should insert/update canonical entities first.

Embedding creation is an asynchronous derived-data pipeline step:

```text
REST canonical insert
       ↓
transaction commits
       ↓
outbox/work item created
       ↓
representation/chunk generation
       ↓
embedding generation
       ↓
search-ready
```

The canonical write must not fail merely because an external embedding provider is temporarily unavailable.

## 10. Search readiness

API resources should expose search-index state where useful:

```json
{
  "search_state": {
    "representations": "READY",
    "active_embedding_model": "READY",
    "last_indexed_at": "..."
  }
}
```

This is preferable to silently returning incomplete results during large backfills.
