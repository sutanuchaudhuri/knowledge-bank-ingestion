# 02 — App and Tool Boundaries

## 1. Model-visible entry points

Expose a small, intentional set of entry points.

Suggested student model-visible tools:

```text
open_student_home()
open_course(course_id | canonical_code)
open_current_course(enrollment_id)
open_problem_tutor(problem_id | attempt_id)
open_progress()
find_learning_resources(query)        # safe search over published corpus
```

Suggested admin model-visible tools:

```text
open_course_authoring(course_id)
open_interaction_authoring(instance_id)
open_publication_review(release_id)
open_content_health_dashboard()
```

The model should not see every CRUD operation.

## 2. App-only backend tools

Examples:

```text
enroll_course
load_course_state
advance_course
submit_learning_item
submit_activity
record_video_position
ask_current_context
start_interaction
record_interaction_event
submit_interaction
request_hint
request_next_route_step
start_tutoring_route
return_from_route
refresh_progress
save_admin_draft
validate_release
approve_release
publish_release
```

Register these with `@app.tool()` unless a specific one genuinely needs model visibility.

## 3. Use function references with CallTool

FastMCP documents that `CallTool` may use a direct function reference. That is preferable
for composed IntelliTutor apps because FastMCP can resolve stable identifiers even when
the app/server is mounted under namespaces.

Preferred:

```python
CallTool(
    submit_quiz,
    arguments={...},
)
```

Avoid hardcoded string names in new code unless function references are impossible.

## 4. FastMCPApp skeleton

```python
from fastmcp import FastMCP, FastMCPApp

student_app = FastMCPApp("intellitutor-student")

@student_app.ui()
def open_course(enrollment_id: str):
    ...

@student_app.tool()
def submit_quiz(...):
    ...

@student_app.tool()
def advance_course(...):
    ...

mcp = FastMCP("IntelliTutor", providers=[student_app])
```

## 5. Backend DTOs

Use Pydantic models for every tool input and output.

Example:

```python
from pydantic import BaseModel, Field
from typing import Literal

class QuizSubmission(BaseModel):
    enrollment_id: str
    state_id: str
    activity_id: str
    selected_index: int = Field(ge=0)
    client_event_id: str

class QuizResult(BaseModel):
    outcome: Literal["CORRECT", "INCORRECT", "PARTIAL"]
    feedback: str
    next_action: Literal[
        "STAY",
        "CONTINUE",
        "START_INTERVENTION",
        "START_ROUTE",
    ]
    focus_object_ids: list[str] = []
```

`Form.from_model()` is appropriate when the form shape is stable and user-authored.

## 6. Tool result strategy

Prefab docs note that the LLM otherwise sees a generic rendered-UI marker. If the model
also needs to reason about the data, return a `ToolResult` containing:

```text
content            concise model-readable summary
structured_content Prefab UI
```

Use this especially for:
- progress dashboards;
- course-state summaries;
- authoring validation reports;
- publication preflight;
- analytics.

Do NOT put hidden answer keys in the textual summary.

## 7. Loading/error actions

Use standard action sequences:

```python
on_click=[
    SetState("saving", True),
    CallTool(
        backend_function,
        ...,
        on_success=[
            SetState("saving", False),
            SetState("result", RESULT),
            ShowToast("Saved", variant="success"),
        ],
        on_error=[
            SetState("saving", False),
            ShowToast("Unable to save", variant="error"),
        ],
    ),
]
```

Every mutation UI needs:
- pending state;
- disabled duplicate submission;
- idempotency key on server;
- meaningful error state.

## 8. Authorization matrix

| Operation | Student | Instructor | Admin |
|---|---:|---:|---:|
| Open published course | yes | yes | yes |
| Submit own quiz | yes | no-as-student-context | no-as-student-context |
| Request own hint | yes | no | no |
| Inspect aggregate progress | no | yes, scoped | yes |
| View learner-specific evidence | no | authorized only | authorized |
| Edit draft course | no | yes | yes |
| Approve/publish | no | role-based | yes |
| Create template primitive | no | no/limited | platform admin |

Server authorization owns this; tool visibility does not.
