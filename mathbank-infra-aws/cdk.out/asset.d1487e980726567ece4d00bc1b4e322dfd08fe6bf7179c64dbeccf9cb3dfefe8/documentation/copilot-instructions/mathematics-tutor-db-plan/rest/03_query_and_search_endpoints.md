# REST 03 — Query and Search Endpoints

## Structured problem query

`GET /v1/problems`

Filters may include:

- competition
- year range
- paper code/type
- problem number
- concept IDs
- technique IDs
- difficulty range
- answer type
- review status

Use repeated query params or a POST search object when filters become complex.

## Search endpoint

`POST /v1/search/problems`

Example:

```json
{
  "query": "cyclic quadrilateral power of a point",
  "filters": {
    "competition": ["AMC 10", "AIME"],
    "year": {"gte": 2000, "lte": 2026}
  },
  "retrieval": {
    "lexical": true,
    "semantic": true,
    "graph_expand": false
  },
  "limit": 25
}
```

Return component scores separately when debugging/evaluation is enabled.

## Taxonomy exploration

- `GET /v1/concepts/{id}/problems`
- `GET /v1/concepts/{id}/neighbors`
- `GET /v1/techniques/{id}/problems`
- `POST /v1/query/problems/by-knowledge`

## Corpus coverage

`GET /v1/corpus/coverage?competition=...` should expose expected, completed, partial, failed, and missing papers based on the explicit inventory and run state.
