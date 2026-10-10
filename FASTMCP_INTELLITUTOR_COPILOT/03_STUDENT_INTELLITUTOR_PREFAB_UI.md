# 03 — Student IntelliTutor Prefab UI

## 1. Goal

The learner should experience one coherent tutor inside the conversation, even though the
screen is composed from:
- published course state;
- media;
- interaction template;
- fixed quiz/activity;
- scoped AI;
- tutoring route;
- progress data.

## 2. Main course wireframe

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Markov Chains                                      Step 4 / 9       │
│ ✓ Prereq  ✓ State  ✓ Video  ● Matrix  ○ Practice  ○ Transfer       │
├──────────────────────────────────────────────────────────────────────┤
│ Transition Matrices                                                  │
│ Focus: convert a state graph into a stochastic matrix                │
│                                                                      │
│ ┌──────────────────────┐  ┌───────────────────────────────────────┐ │
│ │ Video / explanation  │  │ Interactive matrix / state graph      │ │
│ │ [Ask at this moment] │  │ [ learner controls ]                  │ │
│ └──────────────────────┘  └───────────────────────────────────────┘ │
│                                                                      │
│ Feedback                                                             │
│ “Row A totals 1.2. These entries must describe every next state.”   │
│ [Try again] [Why?] [Hint]                                           │
│                                                                      │
│ [Start competition problem]                                         │
├──────────────────────────────────────────────────────────────────────┤
│ [Back]                                                [Continue]    │
└──────────────────────────────────────────────────────────────────────┘
```

## 3. Recommended Prefab primitives

Use verified Prefab patterns:
- `Column` / `Row` / `Grid` for layout;
- `Heading`, `Text`, `Small`, `Muted` for hierarchy;
- `Card`, `CardHeader`, `CardContent`;
- `Badge` for state/status;
- `Metric` for compact progress indicators;
- `DataTable` for problem/resource lists;
- `BarChart` / other charts for progress summaries;
- `Form`, `Input`, `Select`, `SelectOption`, `Textarea`, `Button`;
- `If`, `ForEach`;
- `Rx`, `STATE`;
- `SetState`, `ToggleState`, `ShowToast`;
- `CallTool` for authoritative actions.

Before using a Prefab component not already in project lock/tests, query the installed
component reference or FastMCP component search tooling rather than guessing names.

## 4. Student FastMCPApp

```python
from fastmcp import FastMCPApp
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Button, Card, CardContent, CardHeader,
    Column, Heading, Row, Separator, Text,
)
from prefab_ui.actions import SetState, ShowToast
from prefab_ui.actions.mcp import CallTool
from prefab_ui.rx import RESULT, STATE

student_app = FastMCPApp("intellitutor-student")
```

## 5. Course open flow

Model-visible:

```python
@student_app.ui()
def open_course(enrollment_id: str) -> PrefabApp:
    dto = course_runtime.materialize_student_state(enrollment_id)

    with Column(gap=4, css_class="p-6") as view:
        with Row(gap=2, align="center"):
            Heading(dto.course_title)
            Badge(f"{dto.current_ordinal}/{dto.total_states}")

        Text(dto.state_title)
        Text(dto.objective)

        # Render state-specific fixed Prefab fragments.
        render_media(dto)
        render_interaction(dto)
        render_quiz(dto)
        render_feedback(dto)

        with Row(gap=2):
            Button(
                "Back",
                on_click=CallTool(go_back, arguments={"enrollment_id": enrollment_id}),
            )
            Button(
                "Continue",
                disabled=not dto.can_continue,
                on_click=CallTool(
                    advance_course,
                    arguments={"enrollment_id": enrollment_id},
                    on_success=SetState("course", RESULT),
                    on_error=ShowToast("Cannot continue yet", variant="error"),
                ),
            )

    return PrefabApp(view=view, state={"course": dto.model_dump()})
```

This is illustrative application code. Adapt exact rendering helpers to installed Prefab
component capabilities.

## 6. Client-only behavior

Good client-state uses:

```text
show/hide transcript
selected local tab
expanded explanation
selected table row
local chart filter
temporary slider state prior to commit
```

Example:

```python
Button(
    "Show explanation",
    on_click=ToggleState("show_explanation"),
)

with If(STATE.show_explanation):
    Text(dto.approved_explanation)
```

No server call is needed if no canonical learner state changes.

## 7. Authoritative behavior

Must call backend:
- quiz submit;
- interaction commit;
- next course state;
- hint request;
- route start;
- tutoring question;
- progress refresh if server-side changes matter.

## 8. Mobile layout

Use a single-column fallback:

```text
Course / 4 of 9
[step badges horizontally]

Transition Matrices
[video]
[ask button]

[interaction full width]

[feedback]
[Hint] [Practice]

[Back] [Continue]
```

Do not depend on hover-only interactions.
