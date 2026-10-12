# 04 — Micro-Course, Quiz and Navigation Flows

## 1. Course state is server-authoritative

The Prefab app renders the current published/pinned state. It does not compute the next
course state from local rules.

```text
Button Continue
  -> CallTool(advance_course)
  -> CourseRuntimeService validates requirements
  -> applies authored transition
  -> returns next student-safe state DTO
  -> Prefab SetState updates UI
```

## 2. Do not send answer keys to student UI

Student DTO:

```json
{
  "activity_id": "LI-MARKOV-004",
  "prompt": "Which row can be a transition row?",
  "options": [
    "(0.2,0.3,0.5)",
    "(0.3,0.3,0.5)",
    "(-0.1,0.6,0.5)"
  ],
  "response_contract": {"kind": "CHOICE_INDEX"}
}
```

Server-only:
- correct index;
- scoring predicate;
- misconception rule;
- answer-bearing explanation until submit.

## 3. Quiz Prefab example

```python
from prefab_ui.components import Button, Column, Select, SelectOption, Text
from prefab_ui.actions import SetState, ShowToast
from prefab_ui.actions.mcp import CallTool
from prefab_ui.rx import RESULT, STATE

def render_quiz(q):
    with Column(gap=2):
        Text(q.prompt)

        with Select(name="quiz_choice", label="Choose one"):
            for index, option in enumerate(q.options):
                SelectOption(value=str(index), label=option)

        Button(
            "Check answer",
            on_click=CallTool(
                submit_quiz,
                arguments={
                    "activity_id": q.activity_id,
                    "choice": STATE.quiz_choice,
                    "client_event_id": STATE.client_event_id,
                },
                on_success=[
                    SetState("quiz_result", RESULT),
                    ShowToast("Answer checked"),
                ],
                on_error=ShowToast("Could not check answer", variant="error"),
            ),
        )
```

The server tool validates enrollment/state ownership before grading.

## 4. Quiz result UI

Result should expose:

```text
outcome
approved feedback
focus objects
next action
optional intervention ID
```

Do not expose:
- evidence-rule internals;
- thresholds;
- future answers;
- other students' data.

## 5. PRE / intermediate / POST quiz composition

For a micro-course:

```text
ORIENTATION
  -> PRE diagnostic
  -> explanatory states
  -> intermediate checkpoint
  -> practice route
  -> transfer
  -> POST transfer assessment
```

Each checkpoint is fixed content attached to the published release.

## 6. Deterministic branching

Example:

```text
CHECKPOINT
  CORRECT       -> NEXT_CONCEPT
  INCORRECT     -> SAME_STATE / RETRY
  MISCONCEPTION -> FIXED_INTERVENTION
  PREREQ_GAP    -> FIXED_PREREQUISITE_MODULE
```

The model does not invent destinations.

## 7. Course dashboard Prefab

A learner home/course list can use:
- `Card` per course;
- `Badge` for status;
- `Metric` for percent complete;
- `DataTable` for longer lists;
- `BarChart` for weekly progress.

Backend returns only learner-owned enrollments.

## 8. Video state

A course video state should contain:
- curated video identity;
- approved transcript status;
- timestamp markers;
- allowed interaction launches;
- allowed tutoring Q&A scope.

If transcript is not approved:
- video may still be shown if allowed;
- "Ask about this moment" remains disabled.

## 9. Exact return

When a quiz/intervention/route is launched from a course state, preserve:

```text
origin enrollment
origin course state
origin video time
origin interaction state if relevant
```

Return to the same origin before applying the authored course transition.
