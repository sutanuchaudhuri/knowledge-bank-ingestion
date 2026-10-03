# Graph 03 — PostgreSQL-to-Graph Projection

## Projection pipeline

1. Read a consistent PostgreSQL watermark/version.
2. Select changed canonical entities and accepted assertions.
3. Upsert nodes by `canonical_id`.
4. Upsert relationships using deterministic relationship identity.
5. Remove or deactivate edges no longer accepted.
6. Record projection version and source watermark.
7. Reconcile counts/checksums.

## Change capture options

Initial implementation: timestamp/revision based incremental export.

Later options:

- PostgreSQL logical decoding / CDC
- outbox table populated in the same transaction as authoritative writes

An outbox is preferable when near-real-time graph freshness becomes important.

## Projection metadata

Create `pipeline.graph_projection` in PostgreSQL with:

- `projection_run_id`
- `graph_name`
- `source_watermark`
- `started_at`
- `completed_at`
- node/edge upsert/delete counts
- status/error

## Idempotency

Use MERGE on stable `canonical_id`. Relationship keys should derive from source assertion IDs where possible. Re-running the same projection must not duplicate edges.

## Deletes

Prefer soft deactivation in PostgreSQL for knowledge records. Projection then removes or marks graph edges/nodes accordingly. Hard deletes require explicit propagation.

## Rebuildability test

Periodically destroy a nonproduction graph and rebuild it from PostgreSQL. A successful rebuild is an architectural acceptance criterion.
