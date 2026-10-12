# 42. Micro-course student navigation experience (stepper + enrollment runtime)

## Comprehensive student experience — target contract v2

> **Normative precedence.** The existing stepper remains the navigation shell, but the
> complete student experience also hosts interactions, videos, timestamp-grounded Q&A,
> fixed remediation, scoped AI and tutoring-route practice. The secure v2 contract below
> supersedes any legacy payload later in this file that exposes hidden correctness data.

### 42.A Contract version

Every learner/public course payload includes:

```json
{"contract_version":2}
```

Web and mobile use the same generated/shared types.

### 42.B Secure activity payload

Before answer:

```json
{
  "activity_id":"uuid",
  "activity_type":"MCQ",
  "prompt":"...",
  "options":["..."],
  "ordinal":0,
  "purpose":"COMPREHENSION",
  "required":false,
  "response_contract":{"kind":"CHOICE_INDEX"}
}
```

Never include pre-answer:
- correct index/value;
- hidden scoring predicate;
- answer-bearing explanation.

Server response after submission:

```json
{
  "activity_id":"uuid",
  "is_correct":true,
  "feedback":"approved explanation",
  "next_action":"STAY|CONTINUE|START_INTERVENTION"
}
```

### 42.C Desktop student wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ MathBank   Markov Chains                    v3          4/9        Profile    │
├───────────────────┬──────────────────────────────────────────────────────────┤
│ STEPS             │ Transition Matrices                                      │
│ ✓ 1 Prereq        │ Focus: turn a state graph into a stochastic matrix       │
│ ✓ 2 State model   │                                                          │
│ ✓ 3 Video         │ ┌────────────────────┐  ┌─────────────────────────────┐ │
│ ● 4 Matrix        │ │ Approved video     │  │ Interactive explorer        │ │
│ ○ 5 Practice      │ │ 02:11 / 05:42      │  │ [state graph] [matrix]      │ │
│ 🔒6 Transfer      │ │ [Ask @ this time]  │  │ [Check]                     │ │
│                   │ └────────────────────┘  └─────────────────────────────┘ │
│                   │                                                          │
│                   │ Tutor / feedback                                         │
│                   │ “This row totals 1.2…” [Try again] [Why?]              │
│                   │                                                          │
│                   │ [Start competition practice problem]                     │
├───────────────────┴──────────────────────────────────────────────────────────┤
│ [Back]                    ↩ Live position                  [Continue]         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 42.D Tablet portrait wireframe (768–991 px)

```text
┌───────────────────────────────────────────────────┐
│ Markov Chains                             4 / 9   │
├───────────────────────────────────────────────────┤
│ ✓ Prereq   ✓ State   ✓ Video   ● Matrix   ○ Next │
│             ← horizontally scrollable →           │
├───────────────────────────────────────────────────┤
│ Transition Matrices                               │
│ Focus: ...                                        │
│                                                   │
│ ┌───────────────────────────────────────────────┐ │
│ │ video / diagram / primary asset               │ │
│ └───────────────────────────────────────────────┘ │
│ ┌───────────────────────────────────────────────┐ │
│ │ interaction                                   │ │
│ └───────────────────────────────────────────────┘ │
│ Feedback / tutor                                 │
├───────────────────────────────────────────────────┤
│ [Back]                               [Continue]   │
└───────────────────────────────────────────────────┘
```

### 42.E Phone wireframe (<768 px)

```text
┌───────────────────────────────┐
│ ‹ Courses     Markov     4/9  │
├───────────────────────────────┤
│ ✓  ✓  ✓  ●  ○  🔒  🔒       │
│         Matrix                │
├───────────────────────────────┤
│ Transition Matrices           │
│ Focus: ...                    │
│                               │
│ [video / image]               │
│ [Ask about this moment]       │
│                               │
│ [interaction full width]      │
│                               │
│ Feedback                      │
│ [Try again] [Hint]            │
│                               │
│ [Start practice problem]      │
├───────────────────────────────┤
│ [Back]            [Continue]  │
└───────────────────────────────┘
```

Touch targets ≥44 px; no horizontal page overflow; semantic icon + text, never color only.

### 42.F Interaction entry

Student receives:

```json
{
  "interaction_instance_id":"uuid",
  "template_key":"TRANSITION_MATRIX_EDITOR_V1",
  "template_version":1,
  "public_config":{},
  "learning_objective":"...",
  "runtime":{
    "start_endpoint":"...",
    "event_endpoint":"...",
    "submit_endpoint":"...",
    "reset_endpoint":"..."
  }
}
```

No `server_evaluation_config`.

### 42.G Practice-route subflow

```text
Course State
   |
   | Start practice
   v
Route Tutor
   |
   | complete / return
   v
Same Course State
   |
   v
server-authored next transition
```

Course runtime exposes only learner-safe route metadata needed to start/resume. Future
hints/expected responses remain server-gated.

### 42.H Timestamp Q&A

Client sends:
- state ID;
- current video time;
- question;
- optional active interaction/route context.

Server:
- resolves approved transcript segment;
- answers from approved scope;
- may launch only approved interaction/intervention;
- preserves exact video time;
- returns `OUT_OF_APPROVED_SCOPE` instead of using unscoped knowledge.

### 42.I Scoped AI panel

Use one semantic `ASK` action, not a separate general chatbot.

Grounding order:
1. approved transcript segment;
2. state Q&A;
3. active interaction context;
4. active route step approved content;
5. published state/route retrieval representations;
6. bound canonical node descriptions.

Response shows grounding labels.

### 42.J Server-authoritative gating

`can_continue` may depend on:
- authored transition;
- required learning item;
- required route completion;
- required interaction completion;
- required intervention completion.

Optional activity attempts do not silently become mastery.

### 42.K Subflow return stack

Authoritative runtime supports:

```text
COURSE_STATE
  -> VIDEO_QA
  -> INTERACTION
  -> INTERVENTION
  -> TUTORING_ROUTE
```

Each subflow preserves origin IDs/time. UI back-navigation does not mutate course progress.

### 42.L Offline behavior

Offline:
- read cached course/runtime;
- manipulate safe public interaction state locally;
- queue quiz/interaction event with `client_event_id`;
- show `Saved offline`;
- do **not** claim authoritative grading/evidence confirmation;
- reconcile on reconnect.

`advance` and required route progression stay online/server-authoritative in v1.

### 42.M Correlation

All mutating calls carry:
- `X-Request-Id`;
- `client_event_id` when replay/idempotency matters.

This connects course, route, interaction, AI, feedback and analytics without changing the
simple stepper UX.


## Requirement inventory

| ID | Requirement | Acceptance |
|---|---|---|
| MCN-1 | Stable, content-agnostic JSON contract | The published-course and enrollment-runtime response shapes in §3 are the contract between `mathbank-rest` and the student reader. Course content (titles, quiz questions, video URLs, step counts) varies per course; field names/nesting do not. A shape change is a breaking change requiring a version bump and an update to this document. |
| MCN-2 | Two reading modes share one renderer | Anonymous/preview (public `GET` + local-only client state) and enrolled (student-JWT-authenticated enroll/advance/activity-response endpoints, server-persisted) both render through the same `StepContent`/`QuizActivity` components; only the data source and whether `onRecordActivity` posts to the server differ. |
| MCN-3 | One step visible at a time | The content panel renders exactly one state at a time, selected by the stepper, never the full state list — a student never scrolls past unrelated completed/locked material to reach a specific step. |
| MCN-4 | Stepper locks to server-pinned progress | For an `IN_PROGRESS` enrollment, steps beyond `enrollment.current_state.ordinal` are `disabled` in the UI; advancing past them is only possible through `POST .../advance`, which itself re-validates the approved-transition graph server-side (`advance_enrollment`). Anonymous/completed browsing is unlocked. |
| MCN-5 | Review without losing live position | Clicking an already-reached (`done`) step shows its static public content locally (`localIndex`) without calling `/advance` or mutating server state; a "back to where you left off" action restores the live edge. |
| MCN-6 | Responsive vertical/horizontal layout | `.mb-course-workspace` is a sticky vertical rail at ≥992px and a horizontal scrollable row at <992px (§5), verified overflow-free at 1440px and 390px. |
| MCN-7 | Recorded, ungraded quiz attempts | Every `activity.definition`-backed quiz question (§3.5) is answerable inline (MCQ buttons / numeric input) and, when enrolled, persists an `ACTIVITY_RESPONSE` event regardless of which step is current; attempts never gate `can_continue` (that remains reserved for required `pedagogy.learning_item`s). |

## 1. Purpose and stability contract

This document specifies the **structure** of the published micro-course student
experience: the step navigator, the one-step-at-a-time content panel, and the
enrollment runtime that drives them. The JSON shapes below are the contract
between `mathbank-rest` (`micro_course_service.py`,
`routers/micro_courses.py`) and the student reader
(`mathbank-web/app/learn/courses/[code]/`).

**Content changes; structure does not.** Course titles, step counts, quiz
questions, and video URLs vary per course and will keep changing as new
courses are authored. The *shape* below — field names, nesting, and the
state-machine rules in §4 — is the stable contract. Treat any change to this
shape as a breaking change requiring a version bump and a corresponding
update here, mirroring how [40_MICRO_COURSE_PLATFORM.md](40_MICRO_COURSE_PLATFORM.md)
treats published release content as immutable.

## 2. Two reading modes

| Mode | Trigger | Data source | Persistence |
|---|---|---|---|
| **Anonymous / preview** | No student session, or a logged-in student who has not pressed "Start lesson" | `GET /v1/micro-courses/{canonical_code}` (public, content-hash verified) | None. Stepping through steps is local React state only (`localIndex`); quiz answers grade locally against `correctness_policy` and are never sent to the server. |
| **Enrolled** | Logged-in student presses "Start lesson" (or returns with an existing `IN_PROGRESS` enrollment) | `POST /v1/micro-courses/{canonical_code}/enroll`, `GET/POST /v1/micro-courses/enrollments/{enrollment_id}` (student JWT required) | Real: `learner.micro_course_enrollment`, `tutor.micro_course_runtime`, `learner.micro_course_state_event`. One in-progress enrollment per (student, course); re-enrolling resumes it. |

Both modes render through the same `StepContent` component — the enrolled
mode just uses the server's `current_state` object instead of a static entry
from `course.states`, and wires `onRecordActivity` so `QuizActivity` posts
attempts instead of only grading in the browser.

## 3. JSON shapes

### 3.1 Published course (anonymous read) — `GET /v1/micro-courses/{canonical_code}`

```jsonc
{
  "canonical_code": "MC-MARKOV-STREAKS",
  "title": "string",
  "description": "string | null",
  "version": 2,                         // integer, the PUBLISHED release version
  "estimated_minutes": 8,
  "learning_objectives": ["string", "..."],
  "primary_targets": [
    { "target_type": "CONCEPT" | "TECHNIQUE" | "SKILL", "name": "string", "slug": "string" }
  ],
  "modules": [ /* optional grouping; the stepper itself is flat and ignores this */ ],
  "transitions": [
    { "from_state_id": "uuid", "to_state_id": "uuid", "transition_type": "NEXT" | "...",
      "condition_type": "ALWAYS" | "...", "condition_payload": {}, "priority": 0 }
  ],
  "states": [ /* ordered by `ordinal`; this ordering IS the stepper order */
    {
      "state_id": "uuid",
      "state_key": "string",            // stable slug, e.g. "PRE_CHECK"
      "ordinal": 0,                     // 0-based; stepper step number = ordinal + 1
      "state_type": "DIAGNOSTIC" | "VIDEO" | "VISUAL" | "CHECKPOINT" | "QUIZ" | "...",
      "title": "string",
      "objective": "string | null",      // rendered as the "Focus" callout
      "student_instruction": "string | null",
      "required": true,
      "skippable": false,
      "assets": [ /* see 3.3 */ ],
      "interactions": [ /* see 3.4 */ ],
      "activities": [ /* see 3.5 */ ],
      "learning_items": [ /* textbook-pipeline MCQs; display-only in this reader */ ],
      "transcript_segments": [],
      "qa_contexts": []
    }
  ]
}
```

### 3.2 Enrollment runtime — `start_enrollment` / `get_enrollment_runtime` / `advance_enrollment`

Returned by `POST .../enroll`, `GET .../enrollments/{id}`, and
`POST .../enrollments/{id}/advance`:

```jsonc
{
  "enrollment_id": "uuid",
  "enrollment_status": "IN_PROGRESS" | "COMPLETED",
  "started_at": "ISO-8601", "completed_at": "ISO-8601 | null",
  "canonical_code": "string", "course_title": "string", "course_description": "string | null",
  "estimated_minutes": 8,
  "release_id": "uuid", "version": 2,
  "state_version": 3,                 // optimistic-concurrency token; echo it back on /advance
  "step_count": 5,                    // total states in the release
  "step_number": 2,                   // 1-based position of current_state among them
  "can_continue": true,               // an ALWAYS/NEXT|USER_CONTINUE transition exists
  "can_go_back": false,               // an ALWAYS/USER_BACK transition exists
  "can_finish": false,                // current_state has no outgoing transitions
  "current_state": {
    "state_id": "uuid", "state_key": "string", "ordinal": 1, "state_type": "VIDEO",
    "title": "string", "objective": "string | null", "student_instruction": "string | null",
    "required": false, "module_id": "uuid | null", "module_title": "string | null",
    "assets": [ /* see 3.3, plus asset_id/private_object like the public shape */ ],
    "interactions": [ /* see 3.4, identical shape to the public read */ ],
    "activities": [ /* see 3.5, each may carry "answered_correctly": true|false */ ],
    "learning_items": [], "transcript_segments": [], "qa_contexts": []
  }
}
```

`can_continue` / `can_finish` gate the "Continue"/"Finish lesson" button;
`can_go_back` gates "Back". They do **not** depend on `activities` (those are
always ungraded/optional); they depend only on `required` `learning_items`
being answered and an approved transition existing.

### 3.3 Asset entry (video/image/audio/external link)

```jsonc
{
  "asset_id": "uuid",               // present on enrollment runtime + public read
  "private_object": false,          // true => stream via /assets/{asset_id}/content
  "asset_kind": "VIDEO" | "IMAGE" | "AUDIO" | "DOCUMENT",
  "title": "string | null",
  "source_url": "string | null",    // external URL (e.g. YouTube) when not private
  "mime_type": "string",
  "object_size_bytes": "number | null",
  "presentation_role": "PRIMARY" | "SUPPORT" | "EXAMPLE" | "REFERENCE" | "OPTIONAL",
  "video_url": "string | null",     // set only if an APPROVED pedagogy.video_asset exists
  "duration_ms": "number | null"
}
```

The reader resolves a renderable `href` as
`private_object ? "/api/.../assets/{id}/content" : (video_url || source_url)`,
then tries, in order: private image/video/audio tag, a recognized YouTube
embed (`youTubeEmbedUrl()` — handles `watch?v=`, `youtu.be/`, `/embed/`, and
carries a `?t=`/`?start=` chapter timestamp into the embed URL), else a
plain "Open approved resource" link-out.

### 3.4 Interaction entry (visual exploration, e.g. Markov/Vieta/Jensen)

```jsonc
{
  "interaction_instance_id": "uuid",
  "canonical_code": "string",
  "title": "string",
  "template_key": "STATE_GRAPH_EXPLORER_V1" | "TRANSITION_MATRIX_EDITOR_V1" | "...",
  "template_version": 1,
  "instance_config": { /* template-specific, see 41_INTERACTION_TEMPLATE_LIBRARY.md */ },
  "initial_state": {},
  "learning_objective": "string",
  "success_criteria": { "type": "string", "...": "..." }
}
```

`InteractionTemplateRenderer.jsx` switches on `template_key` to pick a
declarative renderer; unknown keys fall back to an `EmptyState`-style notice,
never to code execution of `instance_config`.

### 3.5 Activity entry (legacy/current-v1 shape; target-v2 security contract is §42.B above)

```jsonc
{
  "activity_id": "uuid",
  "activity_type": "MCQ" | "NUMERIC",
  "prompt": "string",
  "options": ["string", "..."],        // [] for NUMERIC
  "correctness_policy": {
    "correct_index": 0,                 // MCQ
    "correct_value": 36,                // NUMERIC
    "explanation": "string"
  },
  "ordinal": 0,
  "purpose": "ENTRY_CHECK" | "COMPREHENSION" | "TRANSFER" | "...",
  "required": false,
  "answered_correctly": true            // enrollment runtime only; omitted if never answered
}
```

Submit with `POST /v1/micro-courses/enrollments/{enrollment_id}/activity-responses`:

```jsonc
// request
{ "activity_id": "uuid", "choice_index": 0 }   // MCQ
{ "activity_id": "uuid", "value": 36 }          // NUMERIC
// response
{ "activity_id": "uuid", "is_correct": true, "explanation": "string | null" }
```

Activities are recorded (`learner.micro_course_state_event`,
`event_type='ACTIVITY_RESPONSE'`) for every answer, in every state of the
student's enrolled release — not gated to the current step, since a learner
may answer a question on a step they already passed. They never affect
`can_continue`/mastery; that is reserved for `required` `learning_items`
(the textbook-pipeline-backed gradable item type), which this reader
displays but does not yet grade inline (see open items in §5).

## 4. Stepper UI state machine

The stepper (`CourseStepper`) is a flat, ordinal-ordered list derived from
`course.states` (never from `enrollment.current_state` alone, so review mode
can show any step's static content). Each step has exactly one status:

| Status | Rule | Visual | Clickable? |
|---|---|---|---|
| `done` | `step.ordinal < reachableOrdinal` | green check-circle dot | Yes — shows that step's static content from `course.states` (read-only review; no Continue/Back shown) |
| `current` | `step.ordinal === activeOrdinal` | filled primary dot | Already active |
| `locked` | `step.ordinal > reachableOrdinal` | muted, `disabled` | No |

`reachableOrdinal` is:
- `enrollment.current_state.ordinal` when `enrollment.enrollment_status === "IN_PROGRESS"` (server-pinned — a locked step literally cannot be reached without the server approving a transition);
- the last step's ordinal (i.e. everything unlocked) when anonymous, or when the enrollment is `COMPLETED`.

`activeOrdinal` is the step currently rendered in the content panel —
`localIndex`, a client-only integer. It is **not** always equal to
`reachableOrdinal`: a student may click a `done` step to review it, which
only moves `localIndex`, not the server's `current_state`. A
"↩ Back to where you left off" action resets `localIndex` to
`enrollment.current_state.ordinal`.

Only when `localIndex === enrollment.current_state.ordinal` (i.e. the student
is looking at the live edge of their progress) do the Back/Continue/Finish
buttons appear, calling `POST .../advance` with
`{ expected_state_version, action: "CONTINUE" | "BACK" }`. A version
mismatch (someone else/another tab already advanced) surfaces as "course
changed; refresh" rather than silently overwriting state — this is the same
optimistic-concurrency guard `advance_enrollment` already enforces
server-side.

## 5. Responsive layout

- **≥ 992px** (`min-width` Bootstrap `lg`, matching the breakpoint every
  other master-detail layout in this app uses): `.mb-course-workspace` is a
  `240px | 1fr` grid. The stepper (`.mb-course-stepper`) is a sticky
  vertical rail; every step shows its dot, title, and type label.
- **< 992px**: the grid collapses to one column; the stepper becomes a
  horizontal, scrollable row (`flex-direction: row; overflow-x: auto`).
  Only the *current* step's label is shown (others collapse to a bare
  numbered/checked dot) to keep the row compact and overflow-free at
  390px — verified by Playwright at both 1440px and 390px with
  `document.documentElement.scrollWidth <= window.innerWidth`.
- The content panel below/beside the stepper always renders exactly one
  step — never the full state list — so the page does not require scrolling
  through unrelated, already-completed, or not-yet-reached material to find
  a specific step's quiz or video.

## 6. Open items (do not claim done)

- `can_continue` does not yet gate on `required` `learning_items` responses
  being graded through the UI (the backend check exists; this reader does
  not yet call `POST .../responses` for `pedagogy.learning_item`-backed
  content because none of the three reference courses use that item type —
  see §3.5).
- Reviewing a `done` step shows its public content, not a reconstruction of
  exactly what the student saw/answered at the time (e.g. a previously
  chosen MCQ option index is not redisplayed, only whether it was correct).
- There is no instructor-facing view of recorded `ACTIVITY_RESPONSE`/
  `QUIZ_RESPONSE` events yet (analytics/export remains future work).
- Timestamp-grounded student Q&A against transcript segments remains
  unimplemented, per [40_MICRO_COURSE_PLATFORM.md](40_MICRO_COURSE_PLATFORM.md).

## Cross-document implementation sequence

All six documents must be implemented as one dependency-ordered program:

```text
Phase 0  Inventory current DB migrations, services, projectors, routes, UI and tests.
Phase 1  Resolve canonical schema/contract gaps and secure student payload v2.
Phase 2  Complete interaction catalogs + deterministic runtime + evidence engine.
Phase 3  Complete SceneSpec Web/Manim/mobile renderers and accessibility behavior.
Phase 4  Complete micro-course media/transcript/Q&A/intervention authoring.
Phase 5  Add micro-course ↔ tutoring-route bindings and nested route runtime.
Phase 6  Complete student web/tablet/phone layouts and shared API client.
Phase 7  Complete admin catalog/workspace/media/widgets/routes/publish/graph screens.
Phase 8  Complete structural Neo4j projectors + verify/diff for all projection kinds.
Phase 9  Complete search/embedding publication for approved course/route content.
Phase 10 Wire audit, AI usage, outbox consumers, analytics rollups and retention.
Phase 11 Build mobile client/offline replay/push features.
Phase 12 Run comprehensive cross-system golden fixtures and security/privacy checks.
```

### Global hard prohibitions

Never:
- create a parallel Concept/Technique/Skill taxonomy;
- mutate published content in place;
- expose hidden answers/evaluation policy in learner JSON;
- treat one wrong answer as a confirmed misconception;
- project learner-specific misconception/mastery data into shared Neo4j;
- run destructive shared-graph rebuilds;
- let runtime LLMs invent course states/routes/interactions/remediations;
- duplicate service logic separately in UI/CLI/mobile;
- claim graph/search parity from a queued job;
- use a separate fake preview renderer;
- lose exact return state/time when launching a subflow.
