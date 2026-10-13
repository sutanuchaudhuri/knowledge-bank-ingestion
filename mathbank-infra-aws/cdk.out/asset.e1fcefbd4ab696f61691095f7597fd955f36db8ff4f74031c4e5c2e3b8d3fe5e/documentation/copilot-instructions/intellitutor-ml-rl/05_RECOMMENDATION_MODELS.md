# 05 — Recommendation Models

## 1. Recommendation types

```text
NEXT_PROBLEM
NEXT_ROUTE
NEXT_MICRO_COURSE
REMEDIATION
TRANSFER_SET
FULL_MOCK
EXAM_STRATEGY
REST/STOP
```

## 2. Candidate generation

Candidates come only from approved canonical content.

```text
Graph prerequisites
+ target exam blueprint
+ vector similarity
+ explicit curriculum sequence
+ recent weak/scratchy nodes
```

No runtime generation of canonical lessons.

## 3. Ranking features

Student:
- mastery / uncertainty / trend
- hint dependence
- recent fatigue/time
- exam goals
- recent exposures
- prerequisite readiness

Candidate:
- difficulty
- target concepts/techniques
- estimated duration
- novelty
- post-completion lift
- historical completion
- route quality

Cross:
- predicted success
- predicted time
- expected learning gain
- exam relevance
- redundancy
- prerequisite mismatch

## 4. Multi-objective ranking

Example utility:

```text
0.35 expected learning gain
+0.25 exam relevance
+0.15 transfer value
+0.10 confidence gain / uncertainty reduction
+0.10 spacing benefit
-0.15 predicted frustration
-0.10 redundancy
```

Weights are policy/config, versioned and evaluated.

## 5. Course recommendation

Example output:

```json
{
  "type": "NEXT_MICRO_COURSE",
  "entity_id": "MC-MARKOV-FIRST-STEP",
  "score": 0.87,
  "reason_codes": [
    "TARGET_EXAM_RELEVANT",
    "PERSISTENT_TRANSFER_GAP",
    "PREREQUISITES_READY"
  ],
  "confidence": 0.82,
  "data_sufficiency": "GOOD"
}
```

## 6. Exploration

Avoid always serving only easy/high-confidence content.

Use safe exploration:
- uncertainty sampling
- contextual bandit among approved candidates
- small exploration budget
- never violate prerequisites/grade-level/published status

## 7. Cold start

New student:
- diagnostic
- historical exam results if imported
- self-declared goals
- school/course background
- generic exam blueprint

Do not fabricate personalization with no evidence.
