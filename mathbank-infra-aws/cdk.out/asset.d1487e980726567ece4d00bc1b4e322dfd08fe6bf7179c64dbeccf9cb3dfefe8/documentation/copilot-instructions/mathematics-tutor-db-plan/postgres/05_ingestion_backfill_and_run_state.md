# PostgreSQL 05 — Ingestion, Backfill, and Durable Run State

## Why this layer matters

Archive processing must survive scheduler restarts, worker crashes, partial extraction, and duplicate invocations. The database—not chat history or scheduler logs—must show what actually happened.

## Run model

`pipeline.run` represents one requested execution, for example:

- `MPG_ARCHIVE_BACKFILL`
- `AMC_TAXONOMY_BACKFILL`
- `EMBEDDING_REBUILD`
- `GRAPH_PROJECTION`

A run records scope, start/end time, heartbeat, counts, software version, configuration, and terminal status.

## Work-item model

Create one `pipeline.work_item` per independently retryable unit, normally one paper or one problem. For archive work, a paper is usually the best unit because it provides visible progress while keeping transaction cost manageable.

State transition:

`PENDING -> IN_PROGRESS -> COMPLETED`

Failure:

`IN_PROGRESS -> FAILED -> PENDING/IN_PROGRESS` on retry.

A run becomes `COMPLETED` only when all required work items are terminal and successful. `PARTIAL` is appropriate when some are permanently failed or intentionally skipped.

## Lease and heartbeat

Workers claim work using `SELECT ... FOR UPDATE SKIP LOCKED`. Set `lease_owner` and `lease_expires_at`. Workers extend the lease periodically. A watchdog can return expired `IN_PROGRESS` items to a retryable state after preserving the failed attempt.

Example claim:

```sql
WITH candidate AS (
  SELECT work_item_id
  FROM pipeline.work_item
  WHERE status = 'PENDING'
     OR (status = 'IN_PROGRESS' AND lease_expires_at < now())
  ORDER BY created_at NULLS FIRST, work_item_id
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE pipeline.work_item w
SET status='IN_PROGRESS',
    lease_owner=:worker,
    lease_expires_at=now() + interval '10 minutes',
    started_at=COALESCE(started_at, now()),
    attempt_count=attempt_count+1
FROM candidate
WHERE w.work_item_id=candidate.work_item_id
RETURNING w.*;
```

## Attempt history

Create `pipeline.work_item_attempt` rather than relying only on the current item row. Record attempt number, worker, started/ended, status, exception category, stack trace reference, input/output hashes, and metrics.

## Checkpoints

For long items, use `pipeline.checkpoint` with:

- `run_id`
- `work_item_id`
- `checkpoint_type`
- `checkpoint_key`
- `sequence_no`
- `payload`
- `created_at`

Examples: pages parsed, questions extracted, taxonomy stage completed.

## Reconciliation counters

At completion of each paper, persist:

- expected questions
- extracted questions
- questions with statements
- questions with answers
- solutions found
- taxonomy assignments produced
- validation errors

Never infer completion merely because no exception was thrown.

## Resume algorithm

1. Load or create run.
2. Materialize expected work items idempotently.
3. Claim one item.
4. Write an attempt record.
5. Perform extraction/classification.
6. Validate expected vs observed counts.
7. Commit authoritative data and checkpoint.
8. Mark the work item `COMPLETED` only after validation.
9. Recompute run counters.
10. Mark the run terminal only after all required items are terminal.

## Scheduler requirement

A scheduler should invoke `POST /runs/{type}` or enqueue work; it should not contain corpus logic. Multiple scheduler invocations must be safe because run creation uses an idempotency key or scope hash.
