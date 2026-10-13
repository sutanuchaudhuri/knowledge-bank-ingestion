# REST 07 — Security, Validation, and Observability

## Authorization roles

Suggested roles:

- reader
- curator
- ingestion-worker
- reviewer
- admin

Machine workers should have the minimum write scope required.

## Validation

Validate at both API and database layers. Examples:

- canonical problem code format
- year bounds
- problem number uniqueness within paper
- confidence in [0,1]
- relationship endpoints exist
- allowed status transitions
- content hash matches payload

## Rate and workload control

Graph traversals and semantic search can be expensive. Apply bounded depth, result limits, timeouts, and quotas. Batch initiation should not spawn unbounded synchronous work.

## Observability

Every request gets a `request_id`. Propagate it into database audit records and job metadata. Emit structured logs with route, latency, status, actor, run ID, and trace ID.

Metrics:

- p50/p95/p99 latency
- error rate
- search latency
- graph traversal latency
- database pool saturation
- run queue depth
- worker throughput
- failed/stale items

## Secrets

No database credentials or provider keys in code or corpus metadata. Use a secrets manager/environment injection and rotate credentials.
