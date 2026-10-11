# REST 01 — API Architecture

## Purpose

The REST layer is the stable boundary for ingestion, curation, query, graph traversal, and tutor retrieval. Clients should not write directly to PostgreSQL or Neo4j.

## Service boundaries

Start with one modular service rather than microservices:

- corpus module
- knowledge/taxonomy module
- search module
- graph module
- pipeline/run module
- admin/review module

Split later only when scale or organizational boundaries justify it.

## Versioning

Use `/v1/...` and evolve additively where possible. Breaking changes require `/v2` or explicit content negotiation.

## Response envelope

Recommended fields:

```json
{
  "data": {},
  "meta": {
    "request_id": "...",
    "api_version": "v1"
  }
}
```

Errors use a stable code, human message, field-level details, and request ID.

## Pagination

Prefer cursor pagination for large ordered collections. Offset pagination is acceptable for small admin views.

## Read-after-write

Writes commit to PostgreSQL first. If graph projection is asynchronous, the response should state the canonical revision and projection status rather than pretending the graph is immediately updated.
