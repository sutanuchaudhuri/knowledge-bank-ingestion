# 10 — Tutor ↔ Student Simulation Environment

## 1. Purpose

Run many tutor/student trajectories offline before exposing policy changes to real learners.

Simulation supports:
- tutor-action evaluation
- reward shaping
- edge-case testing
- curriculum flow testing
- exploration without learner risk
- synthetic augmentation

Simulation is not a substitute for real student evidence.

## 2. Environment

Observation:

```json
{
  "course_state": "...",
  "route_step": "...",
  "problem_features": {...},
  "student_mastery": {...},
  "misconception_state": {...},
  "hint_history": [...],
  "attempt_history": [...],
  "time_in_step_ms": 42000,
  "last_response_type": "WRONG_ALGEBRA",
  "allowed_action_ids": [...]
}
```

Action space is constrained:

```text
ASK_DIAGNOSTIC
GIVE_H1
GIVE_H2
GIVE_H3
SHOW_THEORY
SHOW_EXAMPLE
OPEN_INTERACTION
START_REMEDIATION
ASK_RETRY
ASK_EXPLAIN_REASONING
MOVE_TO_NEXT_STEP
RETURN_TO_PREREQUISITE
STOP_AND_RECOMMEND_BREAK
```

No arbitrary hidden answer reveal action unless explicitly available by route policy.

## 3. Student simulator profiles

A simulator is parameterized by latent traits:

```text
mastery by skill
misconceptions
speed
guess tendency
persistence
hint dependence
careless error rate
reading comprehension proxy
transfer ability
fatigue curve
```

Profiles should be calibrated from real aggregate distributions.

## 4. Hybrid simulator

Use two layers:

### Behavioral engine
Deterministic/probabilistic simulator decides:
- correctness
- response latency
- hint uptake
- dropout
- misconception persistence

### LLM response renderer
Optional LLM converts simulator state into realistic student free text.

Important:
The LLM does not decide latent truth.
It verbalizes a state sampled by the behavioral model.

## 5. Example

Latent student:

```text
Vieta mastery .72
sign misconception .68
hint dependence .35
speed medium
```

Tutor action:
`ASK_DIAGNOSTIC(VIETA_SIGN)`

Behavioral simulator samples:
- incorrect probability .62
- latency 18s

Then LLM renders:
> I think the x^2 coefficient should just be the sum of the roots.

This preserves controlled ground truth.

## 6. Synthetic-data labeling

Every synthetic trajectory has:

```text
source=SIMULATED
simulator_version
profile_seed
policy_version
scenario_id
```

Never mix synthetic and real data without source weighting.

## 7. Scenario library

Include:
- correct but slow
- fast careless
- persistent misconception
- prerequisite gap
- over-hinting risk
- disengagement
- adversarial/confusing free text
- multiple valid solution routes
- misconception resolved then recurs
- strong student bored by excessive scaffolding

## 8. Calibration

Compare simulator distributions to real:
- success by difficulty
- hint usage
- response time
- dropout
- misconception transition
- transfer success

Simulator updates require evaluation just like tutor policies.

## 9. Uses

Safe:
- regression tests
- policy pretraining
- reward sensitivity
- rare scenario testing

Unsafe:
- claiming educational effectiveness from synthetic data alone
- replacing real evaluation
- training final tutor exclusively on simulator preferences
