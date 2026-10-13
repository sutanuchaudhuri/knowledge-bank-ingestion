# 13 — Training, Inference and MLOps

## 1. Pipeline stages

```text
EXTRACT
→ VALIDATE
→ FEATURE_BUILD
→ LABEL_BUILD
→ SPLIT
→ TRAIN
→ CALIBRATE
→ OFFLINE_EVAL
→ REGISTER
→ APPROVE
→ DEPLOY
→ MONITOR
```

Every stage is reproducible.

## 2. Data extraction

Read from Postgres using point-in-time-safe queries.

Use Neo4j snapshots/exports only for structural graph features.

Use pgvector for:
- nearest-neighbor candidate generation
- semantic similarity
- representation features

Do not train from live mutable graph state without a recorded projection watermark.

## 3. Dataset manifest

Every training dataset records:

```text
dataset_id
feature_set_version
label_version
source watermarks
student cohort query hash
content release filters
time window
row counts
exclusion counts
leakage checks
schema hash
```

## 4. Storage

Recommended:
- Postgres for metadata/registry/small snapshots
- Parquet in object storage for training datasets
- object storage for model artifacts
- pgvector for retrieval embeddings
- Neo4j for structural online/offline graph queries

Do not store large model binaries in Postgres.

## 5. Model registry

Can use:
- MLflow or equivalent
- plus canonical MathBank `ml.model_registry` row

MathBank registry owns:
- business approval
- deployment stage
- compatibility versions

External registry may own:
- binaries
- metrics
- artifacts

## 6. Training orchestration

Reuse existing pipeline/outbox patterns where practical.

For heavy training use an orchestrator/job runner.

Jobs:

```text
feature_refresh_daily
mastery_update_hourly/daily
recommendation_model_weekly
exam_model_weekly
clustering_monthly/weekly
tutor_policy_dataset_daily
tutor_policy_training_periodic
data_readiness_daily
```

No requirement that all use same cadence.

## 7. Inference service

Suggested:

```text
mathbank-ml-inference
```

Endpoints/service functions:

```text
get_student_state
predict_problem_success
predict_problem_time
recommend_next
recommend_exam_strategy
generate_exam_plan
score_tutor_actions
get_data_readiness
```

Latency budgets:
- recommendation: sub-second to low seconds
- tutor action scoring: low hundreds ms where possible
- dynamic exam assembly: seconds acceptable
- batch analytics: asynchronous

## 8. Caching

Cache keyed by:

```text
student feature snapshot ID
model version
request parameters
content projection watermark
```

Invalidate when relevant learner event watermark advances.

## 9. Model monitoring

Monitor:
- prediction calibration
- AUC/log loss where appropriate
- MAE for time
- ranking NDCG/Recall
- recommendation acceptance
- downstream transfer
- drift
- coverage
- abstention rate
- subgroup performance
- tutor reward
- action distribution

## 10. Drift

Types:
- student behavior
- exam content
- course changes
- taxonomy changes
- tutor policy changes

When canonical taxonomy changes:
- feature version changes
- affected models may require retraining

## 11. Shadow mode

Before active recommendations:
- compute predictions silently
- compare to actual outcomes
- validate calibration
- inspect explanations

## 12. Rollback

Every inference response records model/policy version.
Deployment system supports immediate rollback to prior approved version.
