# 16 — Master Copilot Instructions

You are implementing MathBank's learning-intelligence and tutor-improvement platform.

## Mission

Create a production ML system that consumes canonical PostgreSQL, structural Neo4j and
pgvector data to produce:
- mastery and misconception time series
- student/content feature snapshots
- next-best problem/route/course recommendations
- exam readiness/pacing/strategy
- dynamic approved-content exams
- cohort analytics/clustering
- data readiness and metadata-gap proposals
- tutor action policy
- tutor simulation environment
- RL/bandit/offline-policy training and evaluation
- tutor feedback datasets
- MLOps/registry/monitoring

## Architecture invariants

1. PostgreSQL remains canonical.
2. Neo4j remains structural/rebuildable.
3. No learner-specific misconception/mastery edges in shared Neo4j.
4. pgvector is retrieval/similarity, not truth/mastery.
5. Published curriculum content is immutable/versioned.
6. Recommendations select approved content only.
7. Dynamic exams select approved problems/variants only.
8. Tutor RL action space is authored/approved.
9. Production tutor never self-modifies directly from a conversation.
10. Synthetic trajectories stay labeled and weighted separately.

## Implement schemas

Inspect current migrations first.

Add/adapt:
- `ml.feature_snapshot`
- `ml.content_feature_snapshot`
- `ml.training_run`
- `ml.model_registry`
- `ml.prediction`
- `ml.recommendation`
- `ml.reward_event`
- `ml.tutor_trajectory`
- `ml.tutor_turn`
- `ml.tutor_feedback_event`
- `ml.data_quality_issue`
- `ml.exam_blueprint`
- `ml.generated_exam`
- `ml.generated_exam_item`
- exam-session/question timing tables if absent

Use real repository PK types/names.

## Build feature pipelines

Feature groups:
- mastery
- transfer
- hints
- timing
- exam pacing
- misconception trend
- content difficulty
- graph prerequisites
- course/route outcomes
- interaction behavior

All features are point-in-time safe.

## Build labels

- future no-reveal correctness
- active response time
- transfer outcome
- course lift
- exam outcomes
- tutor multi-component reward

Prevent leakage.

## Start with strong baselines

Mastery:
BKT/Bayesian/EWMA.

Success/time:
calibrated interpretable/GBM models.

Recommendation:
candidate generator + learning-to-rank.

Dynamic exam:
prediction + CP-SAT/ILP.

Clustering:
validated KMeans/HDBSCAN.

Tutor:
supervised policy -> contextual bandit -> offline RL.

Do not jump to deep architectures until baselines are beaten.

## Tutor simulation

Build:
- calibrated behavioral student simulator
- optional LLM surface-response renderer
- scenario library
- synthetic source labels
- calibration metrics

The LLM never decides latent student truth.

## Tutor RL

Observation:
current authored state + learner features.

Actions:
approved action IDs only.

Reward:
correctness + delayed transfer + misconception resolution + efficiency
minus hint dependence/time/abandonment/premature reveal/policy violations.

Log action propensity.

Evaluate with direct/IPS/doubly-robust methods where valid.

No unrestricted online RL.

## Tutor improvement

Separate:
1. policy learning
2. retrieval/reranking
3. language realization

Train/evaluate independently.

Real feedback enters a curated dataset, not automatic fine-tuning.

## Data readiness

Every use case returns:
- READY / PARTIAL / NOT_READY
- confidence
- blockers
- recommended metadata/data collection

Generate admin tasks for missing:
- expected time
- difficulty
- taxonomy/technique
- transfer labels
- source lineage
- duplicate family
- timestamp coverage

Never auto-edit canonical metadata.

## APIs/UI

Implement student:
- learning profile
- recommendations
- exam strategy
- generated mock
- misconception trend
- readiness

Implement admin:
- student intelligence
- cohort clusters
- course effectiveness
- data gaps
- model registry
- training runs
- tutor-policy dashboard

Integrate through existing REST/FastMCP surfaces.

## MLOps

Every model artifact pins:
- feature version
- label version
- dataset manifest
- git SHA
- content/projection watermark
- hyperparameters
- metrics
- approval
- deployment stage

Support:
- shadow
- canary
- rollback
- drift monitoring
- calibration monitoring

## Testing

Must include:
- point-in-time leakage tests
- feature reproducibility
- cold-start
- low-data abstention
- graph feature consistency
- dynamic exam constraints
- reward hacking
- simulator calibration
- offline policy evaluation
- action-mask enforcement
- learner privacy
- model rollback

## Implementation order

```text
Phase 1  inventory current learner/content/event metadata
Phase 2  data readiness report
Phase 3  exam timing/event completeness
Phase 4  feature/label schemas + point-in-time pipeline
Phase 5  mastery/misconception time series
Phase 6  success/time baselines
Phase 7  next-best recommendation ranker
Phase 8  exam pacing/readiness
Phase 9  dynamic exam optimizer
Phase 10 cohort analytics
Phase 11 tutor trajectory/reward logging
Phase 12 calibrated student simulator
Phase 13 supervised tutor action model
Phase 14 contextual bandit
Phase 15 offline RL evaluation/training
Phase 16 retrieval/language feedback datasets
Phase 17 shadow/canary/production MLOps
```

## Definition of done

The system must be able to explain:

```text
what it recommends
why
which model/version
which evidence
how confident it is
which data is missing
what outcome would change the recommendation
```

And for the tutor:

```text
why action A was selected instead of B
which actions were allowed
what reward was observed later
whether the policy is actually better than the prior version
```
