# REST 04 — Insert, Update, and Idempotency

## Idempotency

All ingestion-facing POST endpoints accept `Idempotency-Key`. The server stores the key, request hash, canonical result, and expiration/retention policy.

If the same key and same payload are replayed, return the original result. If the same key is used with a different payload, return `409 Conflict`.

## Problem ingestion

`PUT /v1/problems/by-code/{canonical_code}` is attractive for deterministic importer upsert semantics.

Request should distinguish:

- source-provided fields
- derived fields
- provenance locator
- parser/extractor version

Do not let machine imports overwrite human-accepted taxonomy assertions automatically.

## Optimistic concurrency

For curator edits use `revision` or `ETag` / `If-Match`. Reject stale updates with `409` or `412` rather than silently overwriting concurrent changes.

## Taxonomy assertion writes

`POST /v1/problems/{id}/concept-assertions`

Fields:

- concept ID
- role
- source type
- confidence
- evidence locator
- review status permitted by caller role

## Bulk insert

Use explicit bulk endpoints with per-item results. One bad item should not hide the status of the others unless atomic mode was specifically requested.
