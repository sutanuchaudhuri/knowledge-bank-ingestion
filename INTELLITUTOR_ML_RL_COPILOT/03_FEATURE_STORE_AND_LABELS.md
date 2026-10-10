# 03 — Feature Store and Labels

## 1. Feature groups

### Student mastery
Per Concept/Technique/Skill:
- attempts 7/30/90 days
- weighted accuracy
- no-hint accuracy
- first-attempt accuracy
- transfer accuracy
- difficulty-adjusted accuracy
- recency
- spacing
- hint dependence
- response-time percentile
- misconception confidence
- misconception slope
- mastery slope

### Problem behavior
- difficulty
- contest family
- expected time
- topic/subtopic/technique
- graph prerequisite depth
- representation embedding
- historical success rate
- discrimination estimate
- common misconception distribution

### Course/route
- target nodes
- prerequisite nodes
- estimated duration
- historic completion
- historic post-course lift
- route quality
- interaction density
- assessment density

### Exam behavior
- early/mid/late accuracy
- skip strategy
- revisit value
- answer-change value
- time spent by difficulty
- time spent by topic
- end-of-exam collapse
- unanswered count
- careless-error proxy
- overinvestment on low-yield questions

## 2. "Scratchy" and "excellent"

Do not use subjective labels without explicit definitions.

Example:

```text
EXCELLENT
  mastery_probability >= .90
  AND transfer_accuracy >= .80
  AND no-hint sample >= N
  AND time efficiency <= benchmark p60
  AND no unresolved misconception above threshold

STRONG
  mastery >= .78

DEVELOPING
  mastery .55-.78

SCRATCHY
  recent apparent mastery but high variance / hint dependence / transfer drop

WEAK
  mastery < .55 with sufficient evidence

UNKNOWN
  insufficient evidence
```

`SCRATCHY` is intentionally different from `WEAK`.

Example scratchy:
- 80% ordinary practice
- 45% transfer
- high hints
- unstable time
- recent misconception recurrence

## 3. Labels

### Success model
`problem_correct_without_reveal`

### Time model
`active_time_ms`, censored for abandonment.

### Mastery
Latent / proxy labels built from future transfer items, not same-item correctness.

### Course effectiveness
Compare post-course held-out target performance to pre-course baseline controlling for
difficulty/selection.

### Recommendation
Future utility:

```text
learning_gain
+ exam relevance
- excessive time cost
- redundancy
- frustration/abandonment penalty
```

### Tutor action
Reward is multi-component, defined in RL docs.

## 4. Avoid leakage

Never use:
- future attempts in current features
- future course completion
- solution/hint reveal after the prediction timestamp
- final exam result to predict earlier question success

Training split should be by time and preferably by student:
- train earlier periods
- validation later
- test latest held-out
- additional cold-student/cold-problem tests
