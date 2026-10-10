# 07 — Dynamic Exam Assembly

## 1. Principle

Dynamic exam generation is not free-form LLM question generation.

The production exam assembler selects only from:
- approved canonical problems;
- approved transformed variants;
- approved generated items that passed review;
- published learning items suitable for assessment.

The ML layer estimates suitability. A constrained optimizer builds the exam.

## 2. Exam blueprint

Create/version:

```text
ml.exam_blueprint
-----------------
blueprint_id
exam_family
version
total_questions
time_limit_ms
sections_json
topic_targets_json
difficulty_targets_json
novelty_policy_json
calculator_policy
scoring_policy_json
status
```

Example AMC-style blueprint:

```json
{
  "questions": 25,
  "time_minutes": 75,
  "difficulty_bands": {
    "1-10": {"easy": 0.7, "medium": 0.3},
    "11-20": {"medium": 0.6, "hard": 0.4},
    "21-25": {"hard": 0.4, "very_hard": 0.6}
  },
  "topic_floor": {
    "algebra": 5,
    "geometry": 4,
    "number_theory": 3,
    "combinatorics_probability": 4
  }
}
```

## 3. Student-tailored mock modes

### Diagnostic mock
Maximize information gain over uncertain mastery.

### Weakness-focused mock
Over-sample weak/scratchy topics while preserving exam flavor.

### Realistic simulation
Match historical exam distribution and expected difficulty.

### Transfer mock
Exclude recently practiced exact problems and near-duplicates.

### Speed mock
Favor questions with known time-management value.

## 4. Candidate scoring

For each candidate problem:

```text
exam_fit
target_weakness_gain
information_gain
difficulty_match
novelty
predicted_time
predicted_success
duplicate_similarity_penalty
recent_exposure_penalty
```

## 5. Constraints

Hard constraints:
- exact question count
- total expected time within tolerance
- topic floors/ceilings
- difficulty distribution
- no duplicate problem
- no high-similarity variants of same source unless allowed
- no already-seen exact problem for unseen mock mode
- approved status only
- valid answer/solution available
- no broken asset dependencies

Optional:
- competition/year diversity
- technique coverage
- graph prerequisite coverage
- balanced answer choices

## 6. Optimization

Start with integer linear programming / CP-SAT.

Decision:
`x_p ∈ {0,1}` whether problem p is included.

Objective:
maximize weighted utility under constraints.

Do not use an LLM to "pick 25 good questions" without optimization.

## 7. Generated exam record

```text
ml.generated_exam
-----------------
generated_exam_id
student_id nullable
blueprint_id
generation_mode
model_versions_json
feature_snapshot_id nullable
seed
objective_value
constraints_json
created_at
```

Items:

```text
ml.generated_exam_item
----------------------
generated_exam_id
ordinal
problem_id
expected_time_ms
predicted_success
target_nodes
selection_reason_json
```

## 8. Leakage prevention

When generating a diagnostic:
- do not use the same future responses as features;
- exclude recent exact problem exposures;
- detect semantic near-duplicates using embeddings + source lineage;
- exclude transformation siblings if policy requires novelty.

## 9. Post-exam learning

After completion:
- compare predicted vs actual success/time;
- update model evaluation;
- update student time-series features;
- compute strategy recommendations;
- record whether dynamic selection improved information gain and downstream outcomes.

## 10. Admin view

Show:
- blueprint compliance
- target weaknesses
- predicted score range
- expected duration
- novelty checks
- excluded recent/similar items
- confidence/data sufficiency
