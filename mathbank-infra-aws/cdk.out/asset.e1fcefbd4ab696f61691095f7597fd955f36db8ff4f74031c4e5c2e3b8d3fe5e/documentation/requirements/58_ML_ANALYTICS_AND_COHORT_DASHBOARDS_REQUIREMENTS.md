# 58. ML analytics and cohort dashboards requirements

> **Status: scaffolded, not implemented, not tested.** Grounded in
> [08_COHORT_CLUSTERING_ADMIN_ANALYTICS.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/copilot-instructions/intellitutor-ml-rl/08_COHORT_CLUSTERING_ADMIN_ANALYTICS.md)
> and [09_DATA_READINESS_METADATA_GAPS.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/copilot-instructions/intellitutor-ml-rl/09_DATA_READINESS_METADATA_GAPS.md).
> See [54](54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md) for the overall project map.

## 1. Scope

Two related but distinct outputs, both consumed by `mathbank-ml-frontend` (admin audience)
and, in summarized form, surfaced inside `mathbank-web`'s admin area (doc 54 §5):

1. **Cohort clustering** — "what patterns of students exist" (doc 08).
2. **Data readiness** — "is there enough data to trust a given recommendation" (doc 09),
   which is also the mechanism that turns ML findings into **admin content tasks** (e.g.
   "add expected-time calibration to these 312 problems") rather than silent bad
   predictions — this is the direct implementation of "guide admin to recalibrate or
   publish a new course based on collected feedback" from the original request.

Training-side code (the clustering model itself) lives in `mathbank-ml-training`
(`models/cohort_clustering.py`, doc 55 §6); this document's own code is the **analytics
service layer** inside `mathbank-ml-inference` that serves cluster assignments, course-
effectiveness comparisons, and data-readiness reports to the two frontends.

## 2. Cohort clustering requirements (doc 08)

- Feature groups: normalized mastery-by-domain, transfer gap, hint dependency,
  speed-by-difficulty, skip/revisit style, careless-error proxies, persistence-after-
  failure, misconception-family prevalence, course-completion behavior, data sparsity
  (doc 08 §2). **Explicitly excluded**: raw PII, protected/sensitive demographic
  attributes, unvalidated embedding clusters (doc 08 §2's own exclusion list, enforced by
  a `# TODO: assert no PII/demographic column is ever passed into the feature vector`
  guard comment in `services/cohort.py`).
- Cluster assignments are **temporal, not identity labels**: `student_id`,
  `cluster_model_version`, `as_of_time`, `cluster_id`, `membership_probability` (doc 08 §6)
  — `contracts.CohortAssignment` in `mathbank-ml-inference` models exactly this; there is
  **no** field anywhere in this scaffold that stores a permanent "this student is a
  Cluster-B student" label.
- Validation gate before any cluster is ever shown to an admin: stability across bootstrap
  samples, interpretable feature differences, minimum cluster size, time-window
  consistency (doc 08 §4) — `evaluation/cluster_validation.py` (in `mathbank-ml-training`)
  is scaffolded with one stub function per criterion; **none are implemented**, and
  `services/cohort.py::get_cohort_clusters()` is documented to refuse to serve a cluster
  set that hasn't passed all four checks once they exist.
- Intervention-effectiveness comparisons (doc 08 §8) use **associative, not causal**
  language — `contracts.InterventionEffect.summary_text` has a `# TODO` reminder quoting
  doc 08 §8's exact phrasing rule ("associated with," never "caused") so this doesn't get
  silently violated once real copy is written.

## 3. Data readiness requirements (doc 09)

- Every training/inference workflow must be able to emit a `DataReadinessReport`
  (`status: READY|PARTIAL|NOT_READY`, `confidence`, `blocking_signals`,
  `recommended_data`) — already a pydantic contract shared between `mathbank-ml-training`
  and `mathbank-ml-inference` (doc 55 §3 lists it).
- Quality dimensions tracked (doc 09 §2): coverage, recency, volume, balance,
  consistency, label quality, timestamp quality, graph mapping, difficulty calibration,
  duplication, leakage risk — `contracts.DataQualityIssue.issue_type` is a `Literal` over
  exactly doc 02's `MISSING|SPARSE|STALE|INCONSISTENT|BIASED|LEAKAGE_RISK` enum, not a
  free-text field (consistent with this session's own doc 45 finding about avoiding
  free-text fields that should be enumerated).
- **Admin never gets silent auto-correction.** `services/data_readiness.py` is documented
  to only ever *propose* a metadata fix (doc 09 §6's exact JSON shape — `problem_id`,
  `proposed_technique`, `confidence`, `evidence`) as a review candidate; nothing in this
  scaffold writes to any canonical Postgres content table.
- The "what data should improve?" ranked admin page (doc 09 §8) is the single most
  directly-requested feature from the original ask ("guide admin to recalibrate... based on
  collected feedback") — `services/data_readiness.py::rank_missing_data_by_expected_value()`
  is stubbed with the doc 09 §8 example ranking as a worked docstring example so the
  eventual real implementation has a concrete target shape to match.

## 4. Requirement inventory (MLA-*)

| ID | Requirement | Acceptance evidence | Status |
|---|---|---|---|
| MLA-1 | Cohort assignments are temporal (never a permanent label) | `contracts.CohortAssignment` has no "permanent label" field | ✅ |
| MLA-2 | Cluster validation gate exists structurally before serving | `evaluation/cluster_validation.py` stubs + `get_cohort_clusters()` docstring | 🟡 stub only |
| MLA-3 | `DataQualityIssue.issue_type` is enumerated, not free text | `contracts.py` | ✅ |
| MLA-4 | Data-readiness proposals never auto-mutate canonical metadata | `services/data_readiness.py` docstring + no write-capable DB handle is imported | ✅ (by construction) |
| MLA-5 | Associative (not causal) language rule is recorded against the exact field it applies to | `contracts.InterventionEffect.summary_text` | ✅ |

## Cross-document relationship

Part of the [54](54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md) plan. Training-side
model in [55](55_ML_TRAINING_PIPELINE_REQUIREMENTS.md) §6, feature refresh scheduling in
[57](57_ML_NIGHTLY_REINDEXING_REQUIREMENTS.md), served by
[56](56_ML_INFERENCE_SERVICE_REQUIREMENTS.md)'s admin endpoints, surfaced in
`mathbank-ml-frontend` and (summarized) `mathbank-web`.
