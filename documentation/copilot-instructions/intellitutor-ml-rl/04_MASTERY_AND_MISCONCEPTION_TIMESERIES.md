# 04 — Mastery and Misconception Time-Series

## 1. Goal

For every student x canonical node:

```text
current estimate
uncertainty
trend
stability
recency
transfer status
```

## 2. Baseline

Implement an interpretable state estimator before DKT.

Example state:

```json
{
  "node_id": "ALG_VIETA",
  "as_of": "...",
  "mastery": 0.81,
  "uncertainty": 0.09,
  "trend_30d": 0.12,
  "stability": 0.67,
  "transfer_mastery": 0.61,
  "hint_dependency": 0.28,
  "classification": "SCRATCHY"
}
```

## 3. Bayesian/BKT baseline

Per skill:
- prior mastery
- probability learn after opportunity
- slip
- guess

Extend observations with:
- problem difficulty
- hints
- partial correctness
- transfer flag

Do not pretend vanilla BKT handles all these without extension.

## 4. Misconception series

For misconception m over time:

```text
observed evidence
diagnostic failure
remediation success
transfer failure
transfer success
decay / recurrence
```

Store derived daily/weekly points:

```text
student_id
misconception_id
period_start
confidence
evidence_count
probe_count
remediation_count
transfer_success_rate
state SUSPECTED|CONFIRMED|RESOLVED|RECURRED
```

## 5. Improvement visualization

Admin/student should be able to see:

```text
MC-M05 Markov row normalization
Jan  .82 CONFIRMED
Feb  .56 REMEDIATING
Mar  .27 RESOLVED
Apr  .21 stable
May  .48 RECURRED?  (probe needed)
```

## 6. Mastery graph propagation

The canonical graph can inform features:

```text
Skill REQUIRES Skill
Technique REQUIRES Skill
Problem REQUIRES Skill
```

But do not automatically propagate mastery as truth.

Use graph-derived features:
- prerequisite mastery min/mean
- missing prerequisite count
- distance to target
- neighbor mastery

A model may learn their predictive value.

## 7. Time decay

Old mastery evidence should decay more if:
- no recent transfer evidence
- concept is known to be fragile
- past success was highly scaffolded

Do not decay immutable accomplishments; decay current readiness estimates.
