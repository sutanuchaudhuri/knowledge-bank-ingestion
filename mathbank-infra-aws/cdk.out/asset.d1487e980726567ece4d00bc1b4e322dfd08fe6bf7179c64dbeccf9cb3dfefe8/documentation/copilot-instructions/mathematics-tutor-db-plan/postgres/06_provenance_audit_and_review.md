# PostgreSQL 06 — Provenance, Audit, and Human Review

## Provenance chain

Every important derived record should be traceable through:

`entity -> assertion/revision -> source locator -> source document -> ingestion run`

This permits answering, "Why do we believe this problem uses inversion?" or "Which PDF supplied this answer?"

## Source documents and locators

Keep the source document immutable where practical. If bytes change, create a new version/checksum. A locator describes exact evidence: page number, worksheet + row, paragraph, image region, or URL fragment.

## Audit events

Create `audit.event` as append-only:

- `event_id`
- `occurred_at`
- `actor_type`
- `actor_id`
- `action`
- `entity_type`
- `entity_id`
- `before_json`
- `after_json`
- `request_id`
- `run_id`

For high-volume machine updates, a compact diff is preferable to full row snapshots when size becomes material.

## Review queue

Machine-generated claims enter a review queue when they cross configured rules, e.g.:

- low confidence
- disagreement between models
- new taxonomy concept candidate
- inconsistent answer
- extracted problem count differs from expected
- conflicting duplicate problem

Suggested table `knowledge.review_task`: `review_task_id`, target entity/assertion, reason, priority, status, assignee, resolution, timestamps.

## Corrections

Never silently overwrite a previously accepted classification. Mark the older assertion `SUPERSEDED`, add the replacement assertion, and link them by `supersedes_assertion_id` where useful.

## Reproducibility metadata

Machine-produced records should preserve:

- pipeline code version / git SHA
- parser version
- prompt template version
- response schema version
- model/provider/model-version
- temperature or deterministic setting when relevant
- source content hash

The goal is not to store every token of every prompt forever; it is to reproduce or explain the decision path.
