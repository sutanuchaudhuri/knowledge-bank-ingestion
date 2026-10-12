# 11 — RL, Contextual Bandits and Offline Tutor Policy

## 1. Recommended progression

Do not start with full online RL.

### Stage 0 — deterministic policy
Rules from authored pedagogy.

### Stage 1 — supervised action scorer
Train from high-quality tutor traces:
`observation -> selected approved action`.

### Stage 2 — contextual bandit
Choose among approved actions for one-step utility.

Useful decisions:
- hint vs retry
- example vs diagnostic
- interaction vs explanation
- H1 vs H2 within allowed range

### Stage 3 — offline RL
Optimize multi-turn learning outcomes using logged trajectories.

### Stage 4 — controlled online exploration
Small, bounded exploration among actions already judged pedagogically safe.

## 2. Why policy layer before LLM fine-tuning

Keep action selection separate from language generation.

```text
TutorPolicy
   chooses action ID
      ↓
Approved content / grounded LLM renderer
      ↓
learner
```

This makes:
- rewards auditable
- actions bounded
- rollback easy
- offline evaluation possible

## 3. Markov Decision Process

State/observation:
- current course/route step
- student feature snapshot
- recent event sequence
- hint history
- misconception evidence
- elapsed time
- question/problem features

Action:
approved pedagogical action ID.

Transition:
new learner response/evidence/time.

Reward:
multi-component.

## 4. Reward design

Never reward immediate correctness alone.

Example:

```text
+1.0 correct without answer reveal
+0.7 delayed transfer success
+0.5 misconception probe resolved
+0.3 correct after low-level hint
+0.2 productive self-explanation
-0.2 excessive time
-0.3 repeated unproductive hint
-0.5 abandonment
-0.8 answer reveal before policy allowed
-1.0 unsafe/unapproved action
```

Delayed reward:
- transfer item 24h/7d later
- next similar competition problem
- reduced hint dependence
- faster correct solution

## 5. Reward components stored separately

Do not keep only scalar reward.

```json
{
  "immediate_correctness": 0.3,
  "transfer": 0.7,
  "time_cost": -0.1,
  "hint_cost": -0.1,
  "engagement": 0.1,
  "policy_violation": 0,
  "total": 0.9
}
```

This enables reward-policy revision.

## 6. Action masks

Before the policy scores:
- remove actions not authored for current state
- remove future hint levels
- remove disallowed route branches
- remove unapproved interventions
- enforce prerequisite/age/context policies

The policy ranks only allowed actions.

## 7. Offline policy evaluation

Before deployment use:
- direct method outcome model
- inverse propensity scoring when logging propensities exist
- doubly robust estimate
- replay where deterministic compatibility allows

Store logging probability of the chosen action for bandit/RL data.

## 8. Conservative optimization

Prefer methods that avoid out-of-distribution actions:
- conservative Q-learning style methods
- behavior-regularized policy learning
- fitted Q evaluation
- contextual bandit with bounded exploration

The exact algorithm is implementation-dependent; do not lock the architecture to one library.

## 9. Online exploration

If enabled:
- approved action set only
- small epsilon/exploration
- no answer-reveal exploration
- stop-loss metrics
- per-student session cap
- canary cohort
- automatic rollback

## 10. Fairness and stability

Monitor policy behavior by:
- experience level
- course
- exam family
- data-rich vs data-poor students

Do not use sensitive demographic attributes for personalization unless separately approved
for a legitimate fairness analysis.

## 11. Policy artifact

Registry records:

```text
policy_version
action_vocabulary_version
observation_feature_version
reward_version
behavior_policy_version
training_run_id
offline_eval
canary_eval
approval
```

Never deploy a policy without all versions pinned.
