# 05 — Hints, Steps, Tutoring Routes and Misconceptions

## 1. Use FastMCPApp for tutoring controls

Hints and steps are authoritative state changes.

Use app-only tools:

```text
request_hint
request_next_step
submit_route_response
start_route_interaction
complete_intervention
return_to_course
```

## 2. Hint ladder

Route compiler preauthors:

```text
H1 strategic nudge
H2 technique cue
H3 setup
H4 near-complete guidance
H5 canonical step reveal
```

Runtime never jumps ahead silently.

## 3. Hint UI

```text
Current step:
“Define h_i as the chance of reaching 4 before disappearance.”

Your work:
[ response / interaction ]

[Check]
[Hint 1]
[Ask about this step]

After Hint 1:
“Condition on the first move from the current state.”

[Try again] [Hint 2]
```

Server decides which hint level may be returned.

## 4. Backend hint example

```python
@tutoring_app.tool()
def request_hint(
    attempt_id: str,
    route_step_id: str,
    requested_level: int | None = None,
) -> dict:
    actor = require_student()
    attempt = route_service.require_owned_attempt(actor, attempt_id)
    return route_service.get_next_allowed_hint(
        attempt=attempt,
        route_step_id=route_step_id,
        requested_level=requested_level,
    )
```

Do not accept arbitrary route release/step IDs without verifying they belong to the pinned
attempt.

## 5. Step reveal

`request_next_step` does not return the entire future route. It returns only the next
allowed step or completion envelope.

## 6. Misconception evidence

Interaction/quiz/route events produce deterministic error signatures.

Example Markov:

```text
ROW_SUM_INVALID
  -> evidence for MC-M05
  -> neutral feedback
  -> repeat
  -> diagnostic probe
  -> threshold
  -> fixed row-sum remediation
```

Wrong answer alone is not enough to assert a confirmed misconception.

## 7. Prefab misconception feedback

Use fixed semantic components:

```text
Badge("Try again")
Text("Row A totals 1.2.")
Text("All mutually exclusive next states from A must total 1.")
Button("Show why")
```

Avoid identity-level labels such as:
"You don't understand transition matrices."

## 8. Agentic question on current step

UI:

```text
Input / Textarea question
[Ask]
```

Backend `ask_route_step` builds a grounding envelope:
- pinned route release;
- current step;
- current hint level;
- approved theory;
- current interaction;
- allowed misconceptions;
- approved examples;
- safe learner evidence summary.

The tutor model may rephrase/explain but cannot:
- reveal future steps;
- invent a new route;
- create a new misconception;
- alter correctness.

## 9. Route tool visibility

Recommended:

```text
@app.ui()
open_problem_tutor(...)   # model-visible entry

@app.tool()
request_hint(...)

@app.tool()
submit_route_response(...)

@app.tool()
request_next_step(...)
```

The host/model gets one clean entry point; the UI owns the detailed loop.

## 10. Route completion

On completion:
- persist route result;
- emit outbox event;
- return to origin course state;
- apply authored course transition only when requested/allowed.
