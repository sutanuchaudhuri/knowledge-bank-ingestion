# REST 05 — Batch Run Control and Status

## Creating a run

`POST /v1/runs`

```json
{
  "run_type": "MPG_ARCHIVE_BACKFILL",
  "scope": {
    "years": [2018, 2021, 2022],
    "paper_types": ["qualifying", "final"]
  },
  "idempotency_key": "mpg-backfill-2018-2022-v3"
}
```

The service creates the run and expected work items transactionally.

## Status

`GET /v1/runs/{run_id}` returns:

- durable status
- started/completed/heartbeat time
- expected/completed/failed/pending counts
- current claimed work items
- stale lease count
- last errors
- reconciliation metrics

This is the authoritative answer to "what has actually been processed?"

## Work-item listing

`GET /v1/runs/{run_id}/items?status=FAILED`

## Retry

`POST /v1/runs/{run_id}/retry`

Allow scopes: failed-only, stale-only, named work items. Retrying creates new attempt history; it does not erase failure history.

## Cancel

Cancellation should set a requested-cancel flag and stop new claims. Workers finish or cooperatively abort at safe transaction boundaries.
