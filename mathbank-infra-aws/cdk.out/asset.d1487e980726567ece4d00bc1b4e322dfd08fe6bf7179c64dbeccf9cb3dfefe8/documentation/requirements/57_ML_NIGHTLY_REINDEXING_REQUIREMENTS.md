# 57. Nightly reindexing requirements (feature snapshots + Neo4j projection refresh)

> **Status: scaffolded, not implemented, not tested.** Grounded in
> [13_TRAINING_INFERENCE_MLOPS.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/copilot-instructions/intellitutor-ml-rl/13_TRAINING_INFERENCE_MLOPS.md) §2/§6/§10
> and this session's own earlier work on Neo4j projection batching (docs 50–51,
> [GOTCHAS.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/GOTCHAS.md) §23/§25 — the canonical projector's
> interrupted-mid-run and per-batch-commit lessons apply directly here and must not be
> relearned). See [54](54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md) for the overall
> project map.

## 1. Scope

The scheduled **batch** half of doc 01 §3: materializing versioned feature snapshots from
Postgres (`ml.feature_snapshot`, `ml.content_feature_snapshot`) on a schedule, and keeping
Neo4j's structural projection consistent with whatever new canonical content lands between
runs. This is the thing that makes doc 01 §4's "no direct OLTP feature joins in hot
inference" rule actually hold in production — if this job doesn't run, `mathbank-ml-
inference` has nothing fresh to read.

This document's code lives inside `mathbank-ml-training` (it reuses
`extract/postgres_extract.py`/`extract/neo4j_extract.py` and `features/*.py` verbatim —
"reindexing" is just "the feature-build stage, run on a schedule against the full student
population instead of a training cohort") — **no fourth project is created for this.**

## 2. Jobs (doc 13 §6, now with a concrete owner module each)

| Job | Cadence | Module | Status |
|---|---|---|---|
| `feature_refresh_daily` | Daily | `jobs/feature_refresh.py` | 🟡 signature only |
| `mastery_update_hourly` | Hourly (lighter weight subset) | `jobs/mastery_update.py` | 🟡 signature only |
| `recommendation_model_weekly` | Weekly | Owned by doc 55 (training, not reindexing) | N/A here |
| `exam_model_weekly` | Weekly | Owned by doc 55 | N/A here |
| `clustering_monthly` | Monthly | Owned by doc 58 | N/A here |
| `tutor_policy_dataset_daily` | Daily | `jobs/tutor_trajectory_export.py` | 🟡 signature only |
| `data_readiness_daily` | Daily | `jobs/data_readiness_scan.py` | 🟡 signature only, feeds doc 58 |
| `graph_projection_refresh_nightly` | Nightly | `jobs/graph_projection_refresh.py` | 🟡 signature only — **must reuse `mathbank-graph`'s existing `project_from_postgres.py`/`project_textbook_steps.py`, not reimplement projection** |

`jobs/__init__.py` documents that these are **plans for a scheduler** (cron, Airflow,
SageMaker Pipelines schedule, or the existing `mathbank-db` `make` targets' pattern) — no
scheduler is wired up in this pass. Each job module is directly runnable as a script
(`python -m mathbank_ml_training.jobs.feature_refresh_daily`) so it can be smoke-tested
manually before any scheduler exists.

## 3. Idempotency and batching — non-negotiable, per this session's own prior incident

Every job in §2 **must**:
- be safely re-runnable (re-running `feature_refresh_daily` for an `as_of_time` that
  already has snapshots must not duplicate rows — `ON CONFLICT` upsert or
  delete-then-insert within one transaction per batch, never per-row).
- commit in bounded batches, **never** one unbatched transaction across the whole student
  population (this is exactly the GOTCHAS.md §25 lesson — the canonical projector's
  original unbatched `DETACH DELETE` only became safe once it moved to Neo4j 5's native
  `CALL (...) { ... } IN TRANSACTIONS`; the equivalent Postgres pattern here is batched
  `INSERT ... ON CONFLICT` in chunks of a few thousand rows, not one giant statement).
- be safe to interrupt mid-run: if `feature_refresh_daily` is killed at 60% completion, the
  next run must pick up cleanly, not leave half the population on a stale snapshot forever
  (GOTCHAS.md §23's lesson — the earlier Neo4j rebuild incident was caught and fixed, but
  the lesson here is to design for interruption *before* it happens, not discover it live).
- record `source_watermark` on every snapshot row so `mathbank-ml-inference`'s cache
  invalidation (doc 56 §5) has something concrete to key on.

`jobs/_batching.py` scaffolds a `run_in_batches(query, batch_size, on_batch)` helper used by
every job in §2 — **not implemented yet** (`# TODO`), but its signature exists so every job
stub already calls through it rather than each job inventing its own batching later.

## 4. Neo4j projection refresh — explicitly reuses `mathbank-graph`, does not fork it

`jobs/graph_projection_refresh.py` is a thin wrapper that shells out to (or imports, if a
clean function boundary exists) `mathbank-graph`'s existing `project_from_postgres.py`. This
document does **not** define a new graph-projection algorithm — doc 16's invariant #2 ("Neo4j
remains structural/rebuildable") and invariant #3 ("no learner-specific misconception/
mastery edges in shared Neo4j") both forbid writing per-student ML features into the shared
graph at all. The only "reindexing" Neo4j needs here is picking up *canonical content*
changes (new problems/techniques/courses), which is already `mathbank-graph`'s job — this
module exists only to make sure that job runs on the same nightly cadence as the Postgres
feature refresh, so the two data sources don't drift relative to each other.

## 5. What "reindex Postgres" means here (not a new search index)

Despite the name, this is **not** about rebuilding a Postgres full-text/pgvector index
(those already have their own maintenance story — `mathbank-rest/scripts/
generate_similarity_embeddings.py` and the existing HNSW index migration `041`). "Reindexing"
in this document's scope means refreshing the **derived `ml.*` feature-snapshot tables** —
a documentation choice made explicit here to avoid the term being misread as a request to
touch the unrelated, already-working vector-index maintenance path.

## 6. Requirement inventory (MLRX-*)

| ID | Requirement | Acceptance evidence | Status |
|---|---|---|---|
| MLRX-1 | Every job in §2 has a runnable-as-script stub | `python -m mathbank_ml_training.jobs.<name> --help` doesn't crash | 🟡 verify in §ml-sanity-check |
| MLRX-2 | Batching helper exists and every job stub calls through it | `jobs/_batching.py`, grep for `run_in_batches(` in each job | ✅ (stub level) |
| MLRX-3 | Graph projection refresh reuses `mathbank-graph`, does not reimplement | `jobs/graph_projection_refresh.py`'s docstring + import | ✅ (stub cites the reused module; actual call wiring is a `# TODO`) |
| MLRX-4 | No job is wired to an actual scheduler yet | No cron/Airflow/SageMaker-schedule config exists in this pass | ✅ (intentional — explicitly out of scope) |

## Cross-document relationship

Part of the [54](54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md) plan. Lives inside
`mathbank-ml-training` (doc 55), feeds `mathbank-ml-inference` (doc 56) and the analytics
pipeline (doc 58). Reuses `mathbank-graph` (unmodified) for the Neo4j half.
