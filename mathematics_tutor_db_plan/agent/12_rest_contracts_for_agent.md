> **Status**: `mathbank-rest`'s actual endpoints
> (`/v1/search/problems`, `/v1/problems/by-code/{code}`, `/v1/concepts`,
> `/v1/corpus/coverage`, ...) are the *implemented, simpler* subset of this
> fuller `/v1/search/questions`-style contract — see
> `mathematics_tutor_db_plan/rest/03_query_and_search_endpoints.md` and
> `mathbank-rest/src/mathbank_rest/routers/v1.py` for what's live today.

# 12 — REST Contracts for the ADK Agent

## 1. Versioning

Use `/v1`.

The ADK tool layer depends on semantic contracts, not internal table structures.

---

## 2. Search questions

### `POST /v1/search/questions`

Request:

```json
{
  "query": "combinatorics",
  "filters": {
    "topic_slugs": ["combinatorics"],
    "competition_slugs": [],
    "year_from": null,
    "year_to": null,
    "time_policy": "recent",
    "difficulty_min": null,
    "difficulty_max": null
  },
  "retrieval": {
    "mode": "hybrid",
    "profile": "question_search_v1"
  },
  "page": {
    "limit": 12,
    "cursor": null
  }
}
```

Response:

```json
{
  "request_id": "req_123",
  "effective_filters": {
    "topic_slugs": ["combinatorics"],
    "year_from": 2024,
    "year_to": 2026,
    "time_policy": "recent",
    "time_basis": "competition_year"
  },
  "total_hits": 31,
  "next_cursor": null,
  "results": []
}
```

---

## 3. Canonical question lookup

### `GET /v1/questions/{problem_id}`

Return:

- canonical statement
- competition/paper/year/number
- answer format if public
- canonical taxonomy
- source citations
- visibility-safe metadata

---

## 4. Problem context

### `GET /v1/questions/{problem_id}/context`

Optional query parameters:

```text
include=taxonomy,related,source
```

Anonymous users receive only public context.

---

## 5. Concepts

### `GET /v1/taxonomy/concepts/{slug}`

### `POST /v1/search/concepts`

Useful for direct concept explanation/search and ambiguity handling.

---

## 6. Similar questions

### `POST /v1/search/similar-questions`

Input may reference:

- a canonical `problem_id`
- user-supplied text

Example:

```json
{
  "problem_id": "problem:...",
  "filters": {
    "exclude_same_paper": true
  },
  "limit": 10
}
```

---

## 7. Corpus analytics

Avoid forcing aggregate questions through top-k RAG.

Examples:

### `POST /v1/analytics/topic-frequency`

### `POST /v1/analytics/technique-frequency`

### `POST /v1/analytics/competition-topic-matrix`

These return calculated values from PostgreSQL.

---

## 8. Admin endpoints

### `GET /v1/admin/questions/{problem_id}/provenance`

### `POST /v1/admin/retrieval/debug`

### `GET /v1/admin/pipeline/runs/{run_id}`

These require explicit admin authorization.

---

## 9. Standard error envelope

```json
{
  "error": {
    "code": "INVALID_FILTER",
    "message": "Unknown competition slug.",
    "details": {},
    "request_id": "req_..."
  }
}
```

Tool functions convert this to a safe, concise result for the agent.

---

## 10. REST invariants

- REST decides visibility.
- REST reports effective filters.
- REST returns canonical IDs.
- REST supplies provenance.
- REST controls retrieval profile.
- REST limits result counts.
- REST never trusts an `admin=true` field from the client.
