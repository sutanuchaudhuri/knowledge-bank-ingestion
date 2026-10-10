# IntelliTutor ML + Recommendation + Tutor-RL Pipeline — Copilot Pack

## Mission

Build an industry-grade learning-intelligence layer on top of the existing MathBank stack:

```text
PostgreSQL canonical data
+ Neo4j structural knowledge graph
+ pgvector/search representations
+ learner attempts/events
+ micro-courses
+ tutoring routes
+ interaction/misconception evidence
+ exam timing/performance data
+ AI tutor conversations
= training/inference/recommendation platform
```

The platform should answer, with evidence and calibrated confidence:

- What is this student weak at?
- What is improving over time?
- What is still scratchy / fragile?
- What is excellent / transfer-ready?
- Which micro-course should the student do next?
- Which problems/routes should be practiced next?
- How should the student prepare for AMC/AIME/HMMT/etc.?
- Which topics and techniques cost too much time?
- When should this student take full mocks?
- What exam pacing strategy fits this student?
- What should an instructor/admin change for one student?
- What should be changed for a cluster/cohort?
- Which metadata/signals are missing or too noisy to support a reliable recommendation?
- Which dynamic mock should be assembled next?
- How should the AI tutor improve from simulated and real interactions?

## Core design rule

Do **not** build one giant opaque "student model."

Use a common feature/label foundation with specialized models:

```text
Mastery / misconception time-series
Question success probability
Question response-time model
Next-best-problem/course ranker
Exam score/pacing model
Dynamic exam assembler
Cohort clustering
Tutor-action policy
Tutor explanation/ranking model
Data-readiness / abstention model
```

## Production learning loop

```text
Canonical + learner events
        ↓
Feature snapshots
        ↓
Labels / outcomes
        ↓
Training datasets
        ↓
Train specialized models
        ↓
Offline evaluation
        ↓
Model registry / approval
        ↓
Inference
        ↓
Recommendations / tutor actions
        ↓
Student interactions
        ↓
Reward / outcome events
        ↓
New training data
```

The production tutor does not self-modify after a conversation.

## Tutor RL rule

Use this maturity path:

```text
Stage 0: deterministic authored tutor
Stage 1: supervised scoring / imitation
Stage 2: contextual bandit for approved action selection
Stage 3: offline RL over approved actions
Stage 4: controlled online experimentation
Stage 5: optional LLM fine-tuning from approved preference data
```

Never start with unrestricted online RL against real students.

## Read order

1. `01_SYSTEM_ARCHITECTURE.md`
2. `02_DATA_MODEL_AND_EVENT_CONTRACTS.md`
3. `03_FEATURE_STORE_AND_LABELS.md`
4. `04_MASTERY_AND_MISCONCEPTION_TIMESERIES.md`
5. `05_RECOMMENDATION_MODELS.md`
6. `06_EXAM_ANALYTICS_AND_STRATEGY.md`
7. `07_DYNAMIC_EXAM_ASSEMBLY.md`
8. `08_COHORT_CLUSTERING_ADMIN_ANALYTICS.md`
9. `09_DATA_READINESS_METADATA_GAPS.md`
10. `10_TUTOR_STUDENT_SIMULATION.md`
11. `11_RL_BANDIT_AND_OFFLINE_POLICY.md`
12. `12_TUTOR_FEEDBACK_AND_MODEL_IMPROVEMENT.md`
13. `13_TRAINING_INFERENCE_MLOPS.md`
14. `14_API_FASTMCP_ADMIN_STUDENT_UI.md`
15. `15_EVALUATION_SAFETY_AND_ACCEPTANCE.md`
16. `16_COPILOT_MASTER_PROMPT.md`
