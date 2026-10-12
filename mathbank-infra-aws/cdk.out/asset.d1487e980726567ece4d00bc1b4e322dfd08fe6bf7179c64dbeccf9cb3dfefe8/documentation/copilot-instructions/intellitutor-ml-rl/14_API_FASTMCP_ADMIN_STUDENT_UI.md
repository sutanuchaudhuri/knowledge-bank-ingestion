# 14 — API, FastMCP, Student and Admin UI

## 1. ML is a service behind existing experiences

Do not expose raw model internals directly to learners.

FastMCP/REST calls service functions.

## 2. Student APIs

Suggested:

```text
GET /v1/ml/me/state
GET /v1/ml/me/recommendations
GET /v1/ml/me/exam-strategy?exam_family=AMC10
POST /v1/ml/me/generated-exams
GET /v1/ml/me/misconception-trends
GET /v1/ml/me/data-readiness
```

## 3. Admin APIs

```text
GET /v1/admin/ml/students/{id}/profile
GET /v1/admin/ml/students/{id}/recommendations
GET /v1/admin/ml/cohorts/clusters
GET /v1/admin/ml/course-effectiveness
GET /v1/admin/ml/data-readiness
GET /v1/admin/ml/model-registry
GET /v1/admin/ml/training-runs
GET /v1/admin/ml/tutor-policy
```

## 4. Student progress wireframe

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Your Learning Profile                                               │
├─────────────────────────────────────────────────────────────────────┤
│ EXCELLENT          STRONG           SCRATCHY          WEAK           │
│ Geometry angles    AM-GM            Vieta transform   Markov hitting │
├─────────────────────────────────────────────────────────────────────┤
│ Recommended next                                                    │
│ 1. Markov First-Step mini-course        22 min     High value       │
│ 2. Vieta transformed-root set           35 min     Transfer         │
│ 3. AMC full mock                        Saturday    Readiness 0.79   │
├─────────────────────────────────────────────────────────────────────┤
│ Misconception trend                                                 │
│ MC-M05 ████████▆▅▃▂  improving                                     │
│ VIETA-M01 ▂▃▅▅▃▃      still unstable                               │
├─────────────────────────────────────────────────────────────────────┤
│ Data confidence                                                     │
│ Pacing: Good      Time-of-day: Not enough data                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 5. Admin student intelligence wireframe

```text
┌────────────────────────────────────────────────────────────────────────┐
│ Student Learning Intelligence                                          │
├──────────────────┬─────────────────────────────────────────────────────┤
│ SUMMARY          │ MASTERY / TIME-SERIES                               │
│ Pred AMC10 117   │ graph: mastery by topic over 12 weeks              │
│ Readiness 0.82   │ misconception trajectories                          │
│ Speed: scratchy  │ time efficiency by difficulty                       │
│ Reliability high │                                                     │
├──────────────────┼─────────────────────────────────────────────────────┤
│ RECOMMENDATIONS  │ EXAM ANALYTICS                                      │
│ mini-course X    │ Q1-10 excellent                                    │
│ route Y          │ Q16-20 overinvestment                               │
│ mock Saturday    │ revisit strategy positive                           │
├──────────────────┴─────────────────────────────────────────────────────┤
│ DATA GAPS: need 2 more afternoon full mocks; 44 problems lack time cal │
└────────────────────────────────────────────────────────────────────────┘
```

## 6. Cohort admin wireframe

```text
Cluster A: strong knowledge / poor pacing       22 students
Cluster B: fast / brittle                       17 students
Cluster C: scaffold dependent                   11 students

[View feature differences]
[Suggested intervention]
[Compare outcomes]
```

## 7. Recommendation explanation

Student:
simple.

Admin:
detailed.

Admin explanation example:

```text
Recommendation: Markov First-Step mini-course

Model:
course_ranker v8

Top reasons:
+ target mastery 0.43
+ prerequisite mastery 0.84
+ 4/6 recent transfer failures
+ predicted completion 21.7 min
+ estimated post-course lift +0.11

Confidence 0.82

Data warnings:
- only 9 recent target items
```

## 8. FastMCP

Model-visible:

```text
open_learning_profile
open_exam_strategy
open_generated_mock
open_admin_student_intelligence
open_cohort_dashboard
```

Backend tools:
- refresh recommendation
- generate approved mock
- accept/dismiss recommendation
- mark admin follow-up
- run data-readiness scan

The model sees concise summaries through ToolResult, not raw feature vectors.
