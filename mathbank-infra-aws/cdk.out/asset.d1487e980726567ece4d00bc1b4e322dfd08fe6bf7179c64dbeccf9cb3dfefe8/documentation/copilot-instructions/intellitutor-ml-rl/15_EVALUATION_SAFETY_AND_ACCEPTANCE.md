# 15 — Evaluation, Safety and Acceptance

## 1. Model-specific metrics

### Mastery
- future transfer calibration
- Brier score
- calibration error
- temporal stability
- coverage

### Success
- log loss
- ROC-AUC
- calibration
- difficulty slices

### Time
- MAE / median absolute error
- log-time error
- censored handling quality

### Ranking
- NDCG@k
- Recall@k
- expected learning gain
- recommendation acceptance

### Exam
- score MAE
- interval coverage
- pacing recommendation uplift

### Clusters
- stability
- silhouette as secondary
- interpretability
- actionability

### Tutor policy
- offline policy value
- transfer reward
- answer-reveal violation
- abandonment
- hint efficiency

## 2. Splits

Require:
- temporal holdout
- student holdout
- content/problem holdout
- exam-family slices
- cold-start tests

## 3. Counterfactual evaluation

Recommendations/RL need logging propensities when exploration exists.

Do not claim offline policy uplift from simple historical correlation.

## 4. Human review

Before deployment inspect:
- top recommendation examples
- bad recommendation examples
- abstentions
- cluster profiles
- tutor trajectories
- reward hacking
- data-gap reports

## 5. Reward hacking tests

Tutor policy should not learn:
- reveal answer quickly
- repeatedly choose easy problems
- avoid testing weak skills
- keep learner engaged with irrelevant content
- spam hints
- prematurely mark completion

Add explicit constraints/penalties.

## 6. Dynamic exam safety

Must satisfy:
- blueprint
- approved content
- novelty
- solution availability
- timing
- no leakage

## 7. Student-facing uncertainty

If uncertain say:
- "I don't have enough timed mocks to recommend a best time of day yet."
- "This topic looks strong, but there are only three recent transfer problems."

Do not turn low-data predictions into confident labels.

## 8. Promotion gates

Model:
- offline metric threshold
- calibration
- no critical subgroup regression
- explainability
- data readiness
- shadow/canary

Tutor policy:
- action compliance 100%
- no increased reveal violations
- positive lower-bound offline policy value
- canary stop-loss configured

## 9. Comprehensive acceptance scenario

For one student:

```text
historical attempts
→ feature snapshot
→ mastery time series
→ data readiness
→ recommend micro-course
→ complete course
→ collect interactions
→ update mastery
→ generate weakness-focused mock
→ complete timed mock
→ pacing analytics
→ admin explanation
→ tutor simulated trajectories
→ train candidate tutor policy
→ offline evaluation
→ shadow/canary
→ new real interactions
→ feedback/reward events
→ next training cycle
```

Verify every step is reproducible by version and timestamp.
