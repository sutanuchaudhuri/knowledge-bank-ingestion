# 12 — Tutor Feedback and Model Improvement

## 1. Separate three learning problems

### A. Pedagogical policy
What should the tutor do next?

```text
ASK_DIAGNOSTIC
GIVE_H1
SHOW_THEORY
OPEN_INTERACTION
ASK_RETRY
ADVANCE
```

Train with:
- supervised learning
- contextual bandits
- offline RL

### B. Retrieval / grounding
What approved content should be available to answer?

Train/evaluate:
- retrieval ranking
- graph traversal
- embedding model
- reranker
- citation/source selection

### C. Language realization
How should the approved action/content be phrased?

Improve with:
- prompt/version iteration
- preference data
- optional SFT/DPO-style training later
- style/clarity evaluation

Do not fine-tune the LLM to compensate for a bad policy or bad retrieval.

## 2. Feedback sources

### Explicit
- thumbs up/down
- too verbose
- too short
- confusing
- gave away answer
- not relevant
- helpful
- "I still don't understand"

### Behavioral
- successful retry
- hint escalation
- time to next correct response
- abandonment
- route completion
- transfer success
- same misconception recurring
- learner asks same question again

### Delayed
- next-day transfer
- next mock
- exam performance
- reduced hint dependency

## 3. Feedback event

```text
ml.tutor_feedback_event
-----------------------
feedback_event_id
trajectory_id
turn_id
student_id
feedback_type
value
free_text nullable
source EXPLICIT | BEHAVIORAL | DELAYED
created_at
```

Free text needs privacy/retention handling.

## 4. Training data curation

Create an approval/quality layer:

```text
candidate trace
-> automatic policy/safety checks
-> de-identification where applicable
-> quality score
-> human review sample
-> training-eligible flag
```

Do not train automatically from every conversation.

## 5. Preference pairs

Useful for language realization:

```text
observation + approved action + grounding
response A
response B
preference
reason
```

Reasons:
- clearer
- less revealing
- better Socratic question
- uses notation correctly
- concise
- better grounding

## 6. Negative examples

Capture:
- answer revealed too early
- ignored current hint level
- unsupported claim
- wrong canonical technique
- too much scaffolding for strong learner
- insufficient feedback
- invented next step
- hallucinated source

These are high-value training/eval records.

## 7. Tutor evaluation suite

Per tutor model/prompt/policy version:

```text
grounding accuracy
action-policy compliance
answer-reveal rate
mathematical correctness
pedagogical relevance
verbosity fit
misconception-target fit
citation correctness
student retry success
delayed transfer
latency
cost
```

## 8. Improvement cadence

Recommended:
- continuous data collection
- weekly/biweekly dataset build
- offline retraining
- benchmark
- shadow evaluation
- canary
- promotion

No continuous autonomous production fine-tuning.

## 9. Tutor model promotion

A new language model/prompt is eligible only if:
- no regression on math correctness
- no increase in premature answer reveal
- grounding >= baseline
- policy compliance >= baseline
- learner outcome proxy improves
- latency/cost acceptable

## 10. Feedback loop diagram

```text
Real interactions ─────┐
                       ├──> curated tutor dataset
Simulated interactions ┘
                              |
               +--------------+--------------+
               |              |              |
               v              v              v
         Policy model    Retrieval model  Language model
               |              |              |
               +--------------+--------------+
                              |
                        offline benchmark
                              |
                           canary
                              |
                         production
```

Synthetic and real sources stay labeled and separately weighted.
