# 55. ML training pipeline requirements (`mathbank-ml-training`)

> **Status: scaffolded, not implemented, not tested.** Grounded in
> [01_SYSTEM_ARCHITECTURE.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/copilot-instructions/intellitutor-ml-rl/01_SYSTEM_ARCHITECTURE.md),
> [02_DATA_MODEL_AND_EVENT_CONTRACTS.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/copilot-instructions/intellitutor-ml-rl/02_DATA_MODEL_AND_EVENT_CONTRACTS.md),
> [03_FEATURE_STORE_AND_LABELS.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/copilot-instructions/intellitutor-ml-rl/03_FEATURE_STORE_AND_LABELS.md),
> [11_RL_BANDIT_AND_OFFLINE_POLICY.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/copilot-instructions/intellitutor-ml-rl/11_RL_BANDIT_AND_OFFLINE_POLICY.md),
> and [13_TRAINING_INFERENCE_MLOPS.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/copilot-instructions/intellitutor-ml-rl/13_TRAINING_INFERENCE_MLOPS.md).
> See [54](54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md) for the overall project map.

## 1. Scope

Everything that happens **offline**, before a model is ever asked to answer a request:
extraction → validation → feature/label building → dataset manifesting → training →
calibration → offline evaluation → registration. Owned entirely by `mathbank-ml-training`.
Nothing in this document runs online; `mathbank-ml-inference` (doc 56) is the only project
that serves a live prediction.

## 2. Pipeline stages (verbatim from doc 13 §1, now mapped to code)

| Stage | Module | Status |
|---|---|---|
| EXTRACT | `extract/postgres_extract.py`, `extract/neo4j_extract.py` | 🟡 signatures only |
| VALIDATE | `datasets/manifest.py::validate_dataset()` | 🟡 signature only |
| FEATURE_BUILD | `features/*.py` | 🟡 signatures only |
| LABEL_BUILD | `labels/*.py` | 🟡 signatures only |
| SPLIT | `datasets/builder.py::time_and_student_split()` | 🟡 signature only |
| TRAIN | `models/*.py` | ⬜ raises `NotImplementedError` |
| CALIBRATE | `evaluation/calibration.py` | ⬜ raises `NotImplementedError` |
| OFFLINE_EVAL | `evaluation/offline_policy_eval.py` | ⬜ raises `NotImplementedError` |
| REGISTER | `registry/model_registry_client.py` | 🟡 signature only |
| APPROVE / DEPLOY / MONITOR | Out of scope for `mathbank-ml-training` — owned by `mathbank-ml-inference`'s deployment story (doc 56) | N/A |

## 3. Data contracts (pydantic, scaffolded in `contracts.py`)

Mirrors doc 02 §1 table-for-table: `FeatureSnapshot`, `ContentFeatureSnapshot`,
`TrainingRun`, `ModelRegistryEntry`, `Prediction`, `Recommendation`, `RewardEvent`,
`TutorTrajectory`, `TutorTurn`, `DataQualityIssue`. Every field in doc 02 is present as a
typed pydantic field; **no business-rule validators** (e.g. "features_json must contain
key X for feature_set_version Y") are implemented yet — each such rule is a `# TODO:`
comment at the exact field it would constrain.

## 4. Feature groups to implement (doc 03 §1, in priority order per doc 16's phase list)

1. Mastery/transfer/hint/recency features (`features/mastery_features.py`) — **highest
   priority**, blocks everything else in the "recognition path" half of this project's
   stated purpose.
2. Content/problem features (`features/content_features.py`) — difficulty, contest family,
   graph prerequisite depth, historical success rate.
3. Exam pacing features (`features/exam_features.py`) — requires `learner.exam_session` /
   `learner.exam_question_event` (doc 02 §3); **blocked** until doc 57's reindexing job
   confirms those tables have adequate per-question timestamp coverage (data-readiness
   gate, doc 09).

## 5. Label groups to implement (doc 03 §3, doc 16)

`labels/success_labels.py` (`problem_correct_without_reveal`), `labels/transfer_labels.py`
(future transfer-item outcome, course lift), `labels/reward_labels.py` (multi-component
tutor reward per doc 11 §4/§5 — `immediate_correctness`, `transfer`, `time_cost`,
`hint_cost`, `engagement`, `policy_violation`, `total`, stored as separate fields, never
collapsed to one scalar before storage).

## 6. Model families (doc 01 §5, doc 16 "start with strong baselines")

| Family | Baseline | Module | Deep model later? |
|---|---|---|---|
| Mastery | BKT/Bayesian/EWMA | `models/mastery_bkt.py` | DKT/transformer only if it beats baseline on held-out student/time split |
| Success | Calibrated logistic/GBM | `models/success_gbm.py` | — |
| Response time | Robust/survival regression | `models/time_regression.py` | — |
| Recommendation | Rule + learning-to-rank hybrid | `models/recommendation_ranker.py` | — |
| Exam pacing | IRT-like difficulty + pacing features | `models/exam_pacing.py` | CP-SAT/ILP dynamic assembly lives in doc 57 (it's a nightly batch job, not a trained model) |
| Cohort clustering | Standardized features + KMeans/HDBSCAN, bootstrap-validated | `models/cohort_clustering.py` | — |
| Tutor policy | Stage 0→4 per doc 11 §1 | `models/tutor_policy.py` | Never jump straight to offline RL — `# TODO` enforces stage order in the module docstring |

**No code in this pass trains anything.** Every `models/*.py::train()` function raises
`NotImplementedError("see requirements/55 §6 — baseline not yet implemented")`.

## 7. Dataset manifest (doc 13 §3) — mandatory fields, enforced by `contracts.py`

`dataset_id`, `feature_set_version`, `label_version`, `source_watermarks`,
`student_cohort_query_hash`, `content_release_filters`, `time_window`, `row_counts`,
`exclusion_counts`, `leakage_checks`, `schema_hash`. `datasets/manifest.py::build_manifest()`
is scaffolded to assemble this dict; **no leakage-check logic is implemented** — doc 03 §4's
leakage rules (no future attempts, no future course completion, no post-timestamp
hint/solution reveal, time+student-based splits) are each a named `# TODO` in
`evaluation/leakage_checks.py`.

## 8. Explicit non-goals (this pass)

- No model is trained, calibrated, or registered.
- No SageMaker resources are created (§4 of doc 54 is a plan, not infrastructure).
- No data-readiness report is actually run against the live database (doc 58 owns that
  pipeline's requirements; this doc only consumes a `DataQualityIssue` contract from it).
- No RL/bandit training happens before the supervised-imitation stage (doc 11 §1) — the
  `tutor_policy.py` stub enforces this by requiring a `stage: Literal[0,1,2,3,4]` argument
  and raising on any stage > the last one that has a non-stub implementation.

## 9. Requirement inventory (MLT-*)

| ID | Requirement | Acceptance evidence | Status |
|---|---|---|---|
| MLT-1 | Project scaffolds with the exact doc 54 §3 layout | `ls mathbank-ml-training` | ✅ |
| MLT-2 | All doc 02 §1 tables represented as pydantic contracts | `contracts.py` | ✅ |
| MLT-3 | Every pipeline stage in §2 has a stub function with a design-doc-citing `# TODO` | Spot check | ✅ |
| MLT-4 | No stage actually executes real training logic | `models/*.py` all raise `NotImplementedError` | ✅ (intentional) |
| MLT-5 | Feature/label/dataset-manifest functions are callable (import without error) even though they do no real work | `python -c "import mathbank_ml_training"` succeeds | 🟡 verify in §ml-sanity-check |
| MLT-6 | Tutor-policy stage ordering (doc 11 §1) is enforced structurally, not just documented | `models/tutor_policy.py` | ✅ |

## Cross-document relationship

Part of the [54](54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md) plan. Feeds
[56](56_ML_INFERENCE_SERVICE_REQUIREMENTS.md) (trained-model consumer) and
[57](57_ML_NIGHTLY_REINDEXING_REQUIREMENTS.md) (shares extraction code).
