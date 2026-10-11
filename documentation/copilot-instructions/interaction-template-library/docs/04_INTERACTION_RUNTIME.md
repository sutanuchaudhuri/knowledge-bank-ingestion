# 04 — Interaction Runtime

## Standard state machine

```text
PRESENT
  ↓
INTERACT
  ↓
EMIT SEMANTIC EVENT
  ↓
VALIDATE / EVALUATE
  ↓
┌───────────┬──────────────┬───────────┐
│           │              │           │
CORRECT   PARTIAL        ERROR      UNCERTAIN
│           │              │           │
SUCCESS   FOCUSED       SIGNATURE      PROBE
          FEEDBACK         │           │
                           +-----+-----+
                                 ↓
                          EVIDENCE UPDATE
                                 ↓
                        CONFIDENCE THRESHOLD?
                            /                                    no            yes
                          │              │
                        RETRY       INTERVENTION
                                         │
                                     DIAGNOSTIC
                                         │
                                       RETRY
```

## Runtime endpoints

```text
POST /v1/interactions/{instance_id}/start
POST /v1/interactions/{instance_id}/event
POST /v1/interactions/{instance_id}/submit
POST /v1/interactions/{instance_id}/reset
GET  /v1/interactions/{instance_id}/state
```

## Semantic event

```json
{
  "interaction_instance_id": "...",
  "event_type": "CONTROL_CHANGED",
  "semantic_action": "SET_TRANSITION_PROBABILITY",
  "control_key": "P_A_TO_B",
  "object_id": "transition:A:B",
  "before_state": {"value": 0.5},
  "action_payload": {"value": 0.8},
  "after_state": {"value": 0.8}
}
```

Pedagogical logic must not depend only on DOM events.

## Evaluation result

```json
{
  "outcome": "ERROR",
  "error_signature": "ROW_SUM_INVALID",
  "details": {
    "row": "A",
    "sum": 1.2,
    "expected": 1.0
  },
  "candidate_misconception_ids": ["MC-M05"]
}
```

## Partial correctness

Example Vieta task:

```text
E1 correct
E2 wrong
E3 correct
```

Return:

```json
{
  "outcome": "PARTIAL",
  "accepted_components": ["E1","E3"],
  "focus_components": ["E2"]
}
```

Do not wipe correct work.

## Object-specific feedback

For an invalid Markov matrix row:
- highlight that row
- pulse outgoing state-graph edges from same state
- show current total and required total
- use icon + text, not color only

## Runtime LLM

May:
- rephrase approved feedback
- explain approved content
- classify open text among predeclared candidates

May not:
- invent misconception
- alter evidence weights
- create remediation
- create controls/icons
- change correctness
- mutate graph
