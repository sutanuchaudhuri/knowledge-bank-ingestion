# 01 — System Architecture

## 1. Existing systems remain authoritative

### PostgreSQL
Canonical:
- problems / solutions / solution steps
- concepts / techniques / skills
- misconceptions
- learning items / activities
- micro-course releases/states
- tutoring-route releases/steps
- learner attempts/events
- interaction events/evidence
- course enrollments/runtime
- audit/outbox

### Neo4j
Derived structural graph:
- problem/concept/technique/skill relationships
- course/state/interactions/routes
- misconception diagnostic/remediation structure

Do not write learner-specific mastery/misconception edges to shared Neo4j.

### pgvector
Use for:
- semantic retrieval
- similar problem/course/route discovery
- explanation/course-state embeddings
- optional learned student/course representations

Do not use vector similarity alone as mastery.

## 2. New ML subsystem

Recommended package boundaries:

```text
mathbank-ml/
  features/
  labels/
  datasets/
  models/
    mastery/
    success/
    time/
    recommendation/
    exam/
    clustering/
    tutor_policy/
  training/
  inference/
  evaluation/
  simulation/
  registry/
  jobs/
  api/
```

## 3. Batch + online split

### Batch
- feature materialization
- labels
- training sets
- model training
- calibration
- clustering
- cohort analytics
- offline policy evaluation
- data-quality reports

### Online inference
- next-best course/problem
- predicted success
- predicted time
- current mastery
- exam strategy
- tutor next action
- recommendation explanation

## 4. No direct OLTP feature joins in hot inference

Create versioned feature snapshots.

Bad:

```text
recommendation request
-> 19 joins across raw event tables
-> Neo4j traversal
-> vector search
-> 3 ad hoc aggregations
```

Preferred:

```text
event processors / scheduled jobs
-> learner feature snapshot
-> content feature snapshot
-> inference service
```

## 5. Model hierarchy

Start with interpretable baselines:

```text
Mastery:
  EWMA/Bayesian/BKT baseline

Success:
  calibrated logistic regression / gradient boosting

Response time:
  robust regression / survival-style model

Recommendation:
  rule + learning-to-rank hybrid

Exam:
  IRT-like difficulty + pacing features

Clustering:
  standardized behavior/mastery features + HDBSCAN/KMeans after validation

Tutor policy:
  contextual bandit / offline RL over approved actions
```

Only adopt deeper models (DKT/transformers/GNNs) when they materially beat strong baselines
under held-out student/time splits.

## 6. Student state is temporal

A student is not a vector that is overwritten forever.

Every feature snapshot has:

```text
student_id
as_of_time
feature_version
lookback_window
source_watermark
```

Recommendations are reproducible "as of" a time.

## 7. Recommendation explanation

Every recommendation should include:

```text
recommendation
reason codes
supporting features
confidence
data sufficiency
alternative
what data would change the recommendation
```

Example:

```text
Do Markov First-Step Recursion mini-course next.

Why:
- 3 recent failures tagged PROB_MARKOV
- row-normalization misconception improving
- first-step boundary errors remain
- predicted completion time: 22 min
- expected gain on similar AMC12 questions: medium-high

Confidence: 0.83
Missing data: only one full timed mock in last 30 days.
```
