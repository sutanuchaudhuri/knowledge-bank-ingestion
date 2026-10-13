# mathbank-ml-inference

The **only** place a live prediction/recommendation/tutor-action-score is served (see
[documentation/requirements/54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md](../documentation/requirements/54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md)
and
[documentation/requirements/56_ML_INFERENCE_SERVICE_REQUIREMENTS.md](../documentation/requirements/56_ML_INFERENCE_SERVICE_REQUIREMENTS.md)).

**Status: scaffolded, not implemented, not tested.** The FastAPI app boots and every
route in requirements/56 §2 exists and responds — with a structured `501 Not Implemented`
body, not real predictions. See requirements/56 for the full endpoint table and status.

## What this service does NOT do

- Train models (that's `mathbank-ml-training`).
- Write to canonical Postgres content tables.
- Compute features from live mutable OLTP joins (requirements/01 §4) — it only ever reads
  already-materialized `ml.feature_snapshot`/`ml.content_feature_snapshot` rows (written
  by `mathbank-ml-training`'s reindexing jobs, requirements/57).

## Getting started

```bash
make install
cp .env.example .env   # fill in read-only Postgres credentials
make start              # http://localhost:8010/docs
```

## Who calls this service

- `mathbank-web`'s `app/api/rest/ml/[[...path]]/route.js` proxy (not yet built — see
  requirements/54 §5), for student/admin-facing pages inside the existing app.
- `mathbank-ml-frontend`, for the ML-ops-facing dashboards (model registry, training runs,
  cohort clusters, tutor-policy status).

## Explicit non-goals (this pass)

- No model is actually loaded or scored.
- No caching backend is wired up (`cache.py` has the key-builder shape only).
- No FastMCP tool surface — blocked on doc 49's still-open `mathbank-agent` reconciliation
  question (requirements/56 §6).
