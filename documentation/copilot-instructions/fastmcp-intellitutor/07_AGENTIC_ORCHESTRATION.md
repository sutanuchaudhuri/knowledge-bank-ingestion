# 07 — Agentic Orchestration

## 1. The agent should open applications, not micromanage every click

The main advantage of FastMCP Apps for IntelliTutor is that the model can decide which
learning surface to open, while the learner performs detailed interaction inside that app.

Example:

```text
User:
"Teach me Markov chains, but start with a quick diagnostic."

Model:
1. resolves/creates enrollment through approved service
2. calls model-visible `open_course`
3. Prefab app opens on PRE diagnostic
4. learner answers inside the app
5. app-only backend tools grade and transition
6. model does not need to be re-called after every click
```

## 2. Recommended model-visible tool set

Keep this small and semantically meaningful:

```text
open_student_home
open_course
open_problem_tutor
open_progress
search_published_learning
open_admin_course
open_admin_review
```

Avoid hundreds of model-visible CRUD tools.

## 3. Agent decides "which experience"; services decide "what is valid"

The model may decide:

```text
The user asked to practice Vieta
-> open the Vieta course or route chooser.
```

It may not decide:

```text
They should skip state 4 because it looks easy.
They have misconception X because answer 1 was wrong.
Reveal hint level 4.
Mark Skill S mastered.
```

Those are domain-service decisions.

## 4. Agentic router example

Illustrative application logic:

```python
def choose_learning_entry(intent, context):
    if intent.kind == "resume_course":
        return ("open_course", {"enrollment_id": context.enrollment_id})

    if intent.kind == "solve_problem":
        return ("open_problem_tutor", {"problem_id": intent.problem_id})

    if intent.kind == "see_progress":
        return ("open_progress", {})

    if intent.kind == "learn_topic":
        course = catalog_service.find_best_published_course(intent.topic)
        return ("open_course", {"course_id": course.id})

    return ("search_published_learning", {"query": intent.raw_query})
```

The LLM may perform intent classification, but returned IDs must be server-validated.

## 5. Context handoff

Every entry UI should provide a concise model-readable summary when subsequent reasoning
may be useful.

Example course tool summary:

```text
Opened Markov Chains v3 for learner-owned enrollment.
Current state: Transition Matrices (4/9).
Required action: complete matrix interaction.
Available optional actions: contextual question, practice problem.
```

Do not include:
- hidden answers;
- future route steps;
- other learners;
- raw misconception thresholds.

## 6. Scoped tutor backend

Suggested backend:

```text
ask_current_context(
    enrollment_id,
    state_id,
    question,
    video_time_ms?,
    active_interaction_id?,
    active_route_attempt_id?
)
```

Server resolves:
1. actor/enrollment;
2. pinned release;
3. exact current state;
4. transcript segment if video position supplied;
5. current route step if active;
6. current approved Q&A/theory;
7. allowed misconception candidates;
8. published search representations if policy allows.

Then the tutoring model receives only that envelope.

## 7. Agent response types

Use a typed result:

```json
{
  "answer": "The row describes all mutually exclusive next states from A...",
  "grounding_ids": [
    "course_state:uuid",
    "interaction:MARKOV-MATRIX-01"
  ],
  "requested_action": "NONE",
  "intervention_id": null,
  "confidence": 0.93
}
```

Allowed action enum:

```text
NONE
START_INTERVENTION
OPEN_INTERACTION
OPEN_ROUTE
REPEAT_VIDEO_SEGMENT
SEEK_VIDEO_MARKER
ESCALATE_OUT_OF_SCOPE
```

Validate every referenced action/ID against current published state.

## 8. Agentic course recommendation

User:

```text
"I keep missing polynomial problems. What should I study?"
```

Suggested orchestration:

```text
get own progress summary
+ inspect published canonical prerequisite graph
+ inspect own recent error signatures
+ find published courses/routes
-> return 1–3 approved choices
-> open selected course/app
```

Do not dynamically synthesize a new canonical course unless the user is in an authoring flow.

## 9. Multi-app composition

FastMCPApp is designed for composition safety.

Recommended providers:

```python
mcp = FastMCP(
    "IntelliTutor",
    providers=[
        student_app,
        tutoring_app,
        progress_app,
        admin_app,
    ],
)
```

Names must be unique.

Use direct function references in `CallTool` to survive namespace mounting.

## 10. Security

Model-visible/app-visible metadata is not an authorization boundary.

Every backend tool repeats:
- actor check;
- role check;
- resource ownership/scope check;
- release/status check;
- requested action validation.

## 11. Failure mode

If the host does not support MCP Apps:
- return text summary;
- offer safe text actions;
- never fail the tutoring experience solely because rich UI is unavailable.
