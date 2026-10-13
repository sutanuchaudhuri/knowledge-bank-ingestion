# 56. ML inference service requirements (`mathbank-ml-inference`)

> **Status: scaffolded, not implemented, not tested.** Grounded in
> [13_TRAINING_INFERENCE_MLOPS.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/copilot-instructions/intellitutor-ml-rl/13_TRAINING_INFERENCE_MLOPS.md) §7–8
> and [14_API_FASTMCP_ADMIN_STUDENT_UI.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/copilot-instructions/intellitutor-ml-rl/14_API_FASTMCP_ADMIN_STUDENT_UI.md).
> See [54](54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md) for the overall project map.

## 1. Scope

The **only** place a live prediction/recommendation/tutor-action-score is served. Reads
versioned feature snapshots (written by doc 57's reindexing job) and approved model
artifacts (written by doc 55's training pipeline + its registry). Never trains, never
writes to canonical Postgres/Neo4j content tables, never computes a feature from a live
19-join OLTP query (doc 01 §4's explicit anti-pattern).

## 2. Endpoints (doc 14 §2/§3, now with HTTP methods and status)

### Student-facing (called by `mathbank-web`'s proxy, §5 of doc 54)

| Method | Path | Service function | Status |
|---|---|---|---|
| GET | `/v1/ml/me/state` | `services.student_state.get_student_state` | 🟡 route exists, returns `501` |
| GET | `/v1/ml/me/recommendations` | `services.recommendation.recommend_next` | 🟡 route exists, returns `501` |
| GET | `/v1/ml/me/exam-strategy` | `services.exam_strategy.recommend_exam_strategy` | 🟡 route exists, returns `501` |
| POST | `/v1/ml/me/generated-exams` | `services.exam_strategy.generate_exam_plan` | 🟡 route exists, returns `501` |
| GET | `/v1/ml/me/misconception-trends` | `services.student_state.get_misconception_trend` | 🟡 route exists, returns `501` |
| GET | `/v1/ml/me/data-readiness` | `services.data_readiness.get_data_readiness` | 🟡 route exists, returns `501` |

### Admin-facing

| Method | Path | Service function | Status |
|---|---|---|---|
| GET | `/v1/admin/ml/students/{id}/profile` | `services.student_state.get_student_state` (admin view, fuller explanation per doc 14 §7) | 🟡 route exists, returns `501` |
| GET | `/v1/admin/ml/students/{id}/recommendations` | `services.recommendation.recommend_next` (admin explanation detail) | 🟡 route exists, returns `501` |
| GET | `/v1/admin/ml/cohorts/clusters` | `services.cohort.get_cohort_clusters` | 🟡 route exists, returns `501` |
| GET | `/v1/admin/ml/course-effectiveness` | `services.cohort.get_course_effectiveness` | 🟡 route exists, returns `501` |
| GET | `/v1/admin/ml/data-readiness` | `services.data_readiness.get_data_readiness` (global/cohort scope) | 🟡 route exists, returns `501` |
| GET | `/v1/admin/ml/model-registry` | `registry.model_loader.list_registry` | 🟡 route exists, returns `501` |
| GET | `/v1/admin/ml/training-runs` | `registry.model_loader.list_training_runs` | 🟡 route exists, returns `501` |
| GET | `/v1/admin/ml/tutor-policy` | `services.tutor_action.get_policy_status` | 🟡 route exists, returns `501` |
| POST | `/v1/admin/ml/tutor-policy/score-actions` | `services.tutor_action.score_tutor_actions` | 🟡 route exists, returns `501` |

Every `501` response body is itself structured, not a bare error string — it returns the
same `MLUnavailable` pydantic shape `{"status": "NOT_IMPLEMENTED", "todo_ref": "requirements/56 §2", "design_doc_ref": "14_API_FASTMCP_ADMIN_STUDENT_UI.md §2/§3"}`
so that a partial frontend integration (doc 54 §5) can already render a "coming soon"
EmptyState rather than a raw 500.

## 3. Explanation contract (doc 01 §7, doc 14 §7) — enforced structurally now

Every prediction/recommendation response, once implemented, **must** populate:

```text
recommendation | prediction
reason_codes: list[str]
supporting_features: dict
confidence: float (0-1)
data_sufficiency: Literal["READY","PARTIAL","NOT_READY"]
alternative: optional
what_data_would_change_this: list[str]
model_key: str
model_version: str
```

This is already a pydantic model (`contracts.Explanation`) that every response-shape
contract (`contracts.RecommendationResponse`, `contracts.PredictionResponse`) embeds as a
required field — so no endpoint can be "finished" later without also filling in an
explanation; the type system blocks it.

## 4. Latency budgets (doc 13 §7, recorded as code comments + a settings constant)

`config.py::LATENCY_BUDGET_MS = {"recommendation": 2000, "tutor_action_scoring": 200,
"dynamic_exam_assembly": 5000, "batch_analytics": None}` — `None` means asynchronous/job-based,
not a live-request budget. **Not yet enforced** (no timeout/circuit-breaker wired) — `# TODO`
in `main.py`.

## 5. Caching (doc 13 §8)

`cache.py` scaffolds a cache-key builder:
`cache_key(student_id, model_version, request_params, content_projection_watermark)`. Backing
store is an open choice — `# TODO: decide Redis vs in-process LRU vs Postgres-backed cache
table once request volume is known; do not default to Redis without confirming ops capacity`.
Invalidation-on-watermark-advance (doc 13 §8) is a named but unimplemented function,
`cache.invalidate_for_watermark()`.

## 6. Follow-on work explicitly deferred (not in this pass's scaffolding)

- `mathbank-web` integration pages (doc 54 §5) — tracked here, not built.
- Shadow-mode comparison harness (doc 13 §11).
- Canary/rollback deployment tooling (doc 13 §12) — `registry/model_loader.py` has a
  `# TODO: rollback_to_version()` stub but no deployment automation.
- FastMCP tool surface (doc 14 §8) — depends on doc 49's still-open FastMCP/`mathbank-agent`
  reconciliation question; do not build `open_learning_profile`/etc. FastMCP tools until
  that's resolved, to avoid creating a *third* agent-tool surface alongside `mathbank-agent`
  and whatever doc 49 eventually decides.

## 7. Requirement inventory (MLI-*)

| ID | Requirement | Acceptance evidence | Status |
|---|---|---|---|
| MLI-1 | FastAPI service scaffolds with every doc 14 endpoint present (even if `501`) | `GET /docs` lists all routes in §2 | ✅ |
| MLI-2 | Every response contract embeds a mandatory `Explanation` | `contracts.py` | ✅ |
| MLI-3 | Latency budgets are recorded even though unenforced | `config.py` | ✅ |
| MLI-4 | No endpoint reads mutable OLTP tables directly (doc 01 §4) | `db.py` only exposes read functions against feature-snapshot tables, not arbitrary queries | ✅ (by construction — no raw query helper is exposed) |
| MLI-5 | Service boots and responds `501` structured JSON for every route | Manual `uvicorn` smoke check, not an automated test (per scope) | 🟡 verify in §ml-sanity-check |

## Cross-document relationship

Part of the [54](54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md) plan. Consumes
[55](55_ML_TRAINING_PIPELINE_REQUIREMENTS.md)'s model artifacts and
[57](57_ML_NIGHTLY_REINDEXING_REQUIREMENTS.md)'s feature snapshots. Depends on doc 49's
open FastMCP question before any FastMCP tool surface is added (§6).
