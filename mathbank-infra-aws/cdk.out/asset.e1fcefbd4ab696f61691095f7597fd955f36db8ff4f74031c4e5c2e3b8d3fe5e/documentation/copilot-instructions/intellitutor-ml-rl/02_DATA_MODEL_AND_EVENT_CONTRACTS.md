# 02 — Data Model and Event Contracts

## 1. New schemas

Use an `ml` schema unless repository conventions dictate otherwise.

### `ml.feature_snapshot`

```text
feature_snapshot_id
student_id
as_of_time
feature_set_version
lookback_days
features_json
source_watermark
created_at
```

Store high-value derived feature snapshots, not arbitrary unbounded copies.

### `ml.content_feature_snapshot`

For problem/course/route features:

```text
entity_type
entity_id
feature_set_version
features_json
content_hash
created_at
```

### `ml.training_run`

```text
training_run_id
model_family
model_version
feature_set_version
label_version
dataset_query_hash
train_start/end
validation_start/end
test_start/end
hyperparameters
metrics_json
artifact_uri
git_sha
status
created_at
```

### `ml.model_registry`

```text
model_key
model_version
model_family
artifact_uri
feature_set_version
label_version
approval_status
approved_by
approved_at
deployment_stage
metrics_json
```

### `ml.prediction`

Optional durable inference audit:

```text
prediction_id
student_id
model_key/version
prediction_type
target_entity_type/id
value_json
feature_snapshot_id
explanation_json
created_at
```

### `ml.recommendation`

```text
recommendation_id
student_id
recommendation_type
entity_type/id
rank
score
reason_codes
explanation_json
model_key/version
feature_snapshot_id
status
created_at
```

### `ml.reward_event`

For tutor-policy learning:

```text
reward_event_id
student_id
trajectory_id
turn_id
policy_version
action_id
reward_components_json
total_reward
delayed_reward
source REAL | SIMULATED
created_at
```

### `ml.tutor_trajectory`

```text
trajectory_id
student_id nullable
student_profile_id nullable
source REAL | SIMULATED
course_release_id nullable
route_release_id nullable
start_state_json
policy_version
outcome_json
created_at
```

### `ml.tutor_turn`

```text
trajectory_id
turn_index
observation_json
allowed_action_ids
selected_action_id
action_payload
student_response_summary
evaluation_json
reward_json
created_at
```

### `ml.data_quality_issue`

```text
issue_id
scope_type STUDENT|COURSE|EXAM|COHORT|GLOBAL
scope_id
signal_key
issue_type MISSING|SPARSE|STALE|INCONSISTENT|BIASED|LEAKAGE_RISK
severity
details_json
recommended_metadata
status
created_at
```

## 2. Canonical event contract

Every learner event should carry where applicable:

```text
student_id
timestamp
request_id
client_event_id
course_release_id
course_state_id
problem_id
solution_route_release_id
route_step_id
interaction_instance_id
learning_item_id
concept_ids
technique_ids
skill_ids
misconception_candidate_ids
correctness
partial_credit
response_time_ms
active_time_ms
hint_count
hint_levels
attempt_number
exam_session_id
device/context metadata if policy allows
```

## 3. Exam session

Add/ensure:

```text
learner.exam_session
  session_id
  student_id
  exam_family
  source_paper_id nullable
  generated_exam_id nullable
  started_at
  submitted_at
  active_duration_ms
  paused_duration_ms
  target_time_limit_ms
  environment_code nullable
  self_report_energy nullable
  self_report_focus nullable
```

Per question:

```text
learner.exam_question_event
  session_id
  problem_id
  ordinal
  first_seen_at
  first_answer_at
  final_answer_at
  active_time_ms
  revisit_count
  answer_changes
  skipped_then_returned
  correctness
  confidence_self_report nullable
```

Without per-question timing, pacing recommendations will be weak.

## 4. Tutor feedback signal

Capture:
- thumbs up/down
- "too easy / too hard"
- "gave away answer"
- "confusing"
- "helpful"
- student reattempt success after hint
- delayed transfer success
- abandonment
- hint escalation depth

Feedback is an outcome signal, not direct model truth.
