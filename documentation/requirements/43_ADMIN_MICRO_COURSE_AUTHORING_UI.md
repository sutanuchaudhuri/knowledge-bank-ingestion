# 43. Admin micro-course authoring & publish UI (implemented — see §0 for status)

## Comprehensive admin control-plane contract

> **Normative precedence.** The admin workspace is the human control plane for the entire
> learning system: course structure, canonical graph mappings, videos/transcripts,
> interactions/SceneSpecs, assessments, tutoring routes, fixed misconception interventions,
> publication, graph/search readiness, analytics and auditability.

### 43.A Top-level information architecture

```text
/admin/micro-courses
  ├── catalog
  └── /{course}
      ├── overview
      ├── content
      ├── media
      ├── quizzes
      ├── widgets
      ├── routes
      ├── versions
      ├── activity
      ├── graph
      └── json
```

### 43.B Catalog wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Micro-courses                                             [+ New course]     │
│ Search [_____________]  Status [All▼]  Target [All▼]                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ Course                    Target          Status      Ver  Steps Enrollments │
│ Markov Chains             Markov Chains   ●Published  v3    9       124      │
│ Vieta                     Vieta           ◐Draft      v2    7        88      │
│ Jensen                    Jensen          ●Published  v1    6        47      │
├──────────────────────────────────────────────────────────────────────────────┤
│ ‹ Prev                     1  2  3                               Next ›      │
└──────────────────────────────────────────────────────────────────────────────┘
```

Row click opens workspace; creation is never inline.

### 43.C Course workspace shell wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ Micro-courses   Markov Chains   [Published v3] [Draft v4]                 │
│ [View as student] [New draft] [Validate] [Publish…]                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ Overview | Content | Media | Quizzes | Widgets | Routes | Versions |        │
│ Activity | Graph | JSON                                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│ TAB CONTENT                                                   │ INSIGHTS      │
│                                                               │ Related nodes │
│                                                               │ Misconceptions│
│                                                               │ Similar course│
│                                                               │ Graph health   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 43.D Content builder wireframe

```text
┌──────────────────────┬──────────────────────────────────┬────────────────────┐
│ COURSE OUTLINE       │ STATE EDITOR                     │ SEMANTIC INSPECTOR │
│ Module 1             │ State: MATRIX                    │ TEACHES            │
│  ✓ Orientation      │ [title________________________]  │ • Markov matrix    │
│  ✓ Video            │ [objective____________________]  │ REQUIRES           │
│  ● Matrix explorer  │ Type [VISUAL▼] Required [x]     │ • conditional prob │
│  ○ Practice route   │                                  │ WATCH FOR          │
│  ○ Transfer         │ Assets                           │ • MC-M05           │
│                     │ [video] [diagram]                │                    │
│ [+ State]           │ Interactions                     │ GRAPH              │
│                     │ [TRANSITION_MATRIX_EDITOR v1]    │ SQL preview        │
│                     │ Routes                           │ Neo4j projected    │
│                     │ [AMC12B-2025-Q20 route]          │ Diff: 0 missing    │
│                     │ Activities / Learning items      │                    │
├──────────────────────┴──────────────────────────────────┴────────────────────┤
│ Transitions: MATRIX --CORRECT--> PRACTICE | --RETRY--> MATRIX              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 43.E Media/transcript wireframe

```text
┌──────────────────────────┬───────────────────────────────────────────────────┐
│ MEDIA LIST               │ VIDEO + TRANSCRIPT ANNOTATOR                     │
│ ● Markov intro           │ ┌───────────────────────────────────────────────┐ │
│ ○ Absorbing chains       │ │ YouTube / uploaded video                     │ │
│ + Add YouTube            │ └───────────────────────────────────────────────┘ │
│                          │ 00:00──────●────────────03:12──────05:40         │
│ Transcript: REVIEW       │                                                   │
│                          │ [02:11–02:42] "A transition row..."              │
│                          │ Concepts [Markov Matrix]                          │
│                          │ Techniques [State Graph]                          │
│                          │ Misconceptions [MC-M05]                           │
│                          │ Can launch [Matrix Explorer▼]                     │
│                          │ Intervention [Row-sum repair▼]                    │
│                          │ [Split] [Merge] [Approve segment]                 │
└──────────────────────────┴───────────────────────────────────────────────────┘
```

### 43.F Widgets/interaction authoring wireframe

```text
┌──────────────────────┬──────────────────────────────────┬────────────────────┐
│ TEMPLATE LIBRARY     │ INSTANCE PREVIEW                 │ RULES / BINDINGS   │
│ Search [________]    │                                  │ Template v1        │
│ [State Graph]        │ [live learner interaction]       │ TEACHES ...        │
│ [Matrix Editor]      │                                  │ CAN_REVEAL ...     │
│ [Function Graph]     │ Event inspector                  │ Feedback policy    │
│ [Vieta Explorer]     │ SET_ROW → ROW_SUM_INVALID       │ Evidence rules     │
│ [Muirhead]           │ → +0.35 → TRY_AGAIN             │ Diagnostic         │
│                      │                                  │ Intervention       │
│ controls/icons/anim  │ [Reduced motion] [Mobile view]  │ SceneSpec          │
└──────────────────────┴──────────────────────────────────┴────────────────────┘
```

Course authors configure published template schemas; platform authors control new template,
control/icon/evaluator/animation definitions.

### 43.G Routes tab wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Practice Routes                                                             │
│ Search problem/competition/topic [____________________] [Filters▼]          │
├──────────────────────────────────────────────────────────────────────────────┤
│ Problem                 Approach        Steps  Quality  Status     Action    │
│ AMC12B 2025 #20         First-step       4      0.94    Published  [Attach] │
│ AIME 2003 II #13        Recurrence       3      0.91    Published  [Attach] │
├──────────────────────────────────────────────────────────────────────────────┤
│ Selected route preview                                                       │
│ Step 1 → Step 2 → Step 3     H1 H2 H3 H4 H5   Concepts / claims / assets  │
│ Attach to state [Practice▼] Role [PRIMARY_PRACTICE▼] Required [x]          │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 43.H Publish cockpit wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Publish Draft v4                                                            │
├─────────────────────────────┬───────────┬────────────────────────────────────┤
│ Identity                    │ PASS      │                                    │
│ Canonical mappings          │ PASS      │                                    │
│ State machine               │ PASS      │                                    │
│ Videos/transcripts          │ PASS      │ 12/12 required segments approved  │
│ Interactions/templates      │ PASS      │ 4 instances, exact versions       │
│ SceneSpecs/accessibility    │ PASS      │                                    │
│ Assessments                 │ PASS      │ no student answer leakage         │
│ Tutoring routes             │ PASS      │ 2 published releases              │
│ Assets                      │ PASS      │ hashes verified                    │
│ Search readiness            │ READY     │ derived after publish             │
│ Neo4j readiness             │ READY     │ derived after publish             │
├─────────────────────────────┴───────────┴────────────────────────────────────┤
│ [Review details]             [Approve]                  [Publish]            │
└──────────────────────────────────────────────────────────────────────────────┘
```

After publish show independent:
`GRAPH_PENDING/OK/FAILED`, `SEARCH_PENDING/OK/FAILED`.

### 43.I Activity/analytics wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Activity                                                                     │
│ Enrolled 124 | Completed 82 | Completion 66% | Median 14m | AI $1.24       │
├───────────────────────────────┬──────────────────────────────────────────────┤
│ Step funnel                   │ Misconception / interaction signals          │
│ 1 █████████████ 124           │ MC-M05 suspected: 18 / confirmed: 6         │
│ 2 ████████████  118           │ VIETA-M01 ...                               │
│ 3 ██████████    101           │ aggregated only; threshold/privacy guard     │
│ 4 ███████        76           │                                              │
├───────────────────────────────┼──────────────────────────────────────────────┤
│ Quiz accuracy                 │ Route usage                                  │
│ Q1 84%  Q2 61%               │ starts 42 / complete 35 / avg hints 1.6     │
├───────────────────────────────┴──────────────────────────────────────────────┤
│ Feedback reports / recent activity / AI usage                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

Student-specific drill-down requires explicit authorization and is not represented in
shared Neo4j.

### 43.J Graph tab

Must show:
- authored Postgres structural graph;
- projected Neo4j graph;
- missing/stale diff;
- projection run ID/watermark;
- no learner-specific edges.

### 43.K AI authoring

AI proposals are drafts only and always show:
- provider/model;
- source IDs/citations;
- request ID;
- estimated/actual cost;
- accept/reject/edit actions.

Never auto-create canonical taxonomy nodes or auto-publish.

### 43.L Version diff

Diff every learner-visible dependency:
- states/order/transitions;
- semantic mappings;
- media/transcript version;
- interactions/template versions;
- SceneSpecs;
- activities/learning items;
- route releases;
- interventions/Q&A;
- safe student API payload.

The admin should be able to answer: **what will a learner see/do differently?**


## 0. Status and scope of this document

**Implemented** (this session, continuing from the planning-only version of this
document). The catalog/workspace split, all 8 tabs, deactivate/reactivate, release
diff, activity aggregation, the widget library, and admin preview-mode (AMC-14) are
built and tested end-to-end (live backend curl checks, `pytest`, `npm run build`, and
Playwright — see the implementation notes below each subsection and §6's inventory).
Deferred items are explicitly called out inline as "not yet available" callouts in the
UI itself (AI transcription, AI-drafted content, the cited web-lookup insights panel) —
nothing is fabricated to look implemented when it is not.

This document does not change
[40_MICRO_COURSE_PLATFORM.md](40_MICRO_COURSE_PLATFORM.md)'s data model or
publication/immutability rules — it is a presentation-and-workflow layer on
top of the existing `micro_course_service.py` service layer, plus a short list
of small, explicitly-flagged backend additions it depends on (§7, now mostly
shipped — see per-item notes).

## 1. Why: problems with the current admin screen

`mathbank-web/app/admin/(protected)/micro-courses/page.jsx` (today, ~680
lines) is a single long page: a "Create a course" form, a course catalog
list, and then — inline, stacked, for whichever course is selected — add
module, add state, course outline, attach interaction, upload asset, define
transition, and review/publish, all in one continuous scroll. Concretely,
admins cannot currently:

1. See a compact, scannable list of courses (status, version, target, last
   updated) before drilling in — the catalog and the editor are not
   separated.
2. View the exact JSON an admin or student API call would return for a
   course (useful for debugging and for verifying the contract in
   [42_MICRO_COURSE_STUDENT_NAVIGATION.md](42_MICRO_COURSE_STUDENT_NAVIGATION.md)).
3. Deactivate a published course (remove it from the student catalog without
   deleting or retiring its historical releases).
4. Start a new draft version of a published course from the UI with any
   sense of *what changed* relative to the live version (no diff view).
5. See usage/activity for a course: enrollment counts, completion rate,
   per-step drop-off, quiz-attempt accuracy — none of this is surfaced
   anywhere in the admin UI today, and (see §7.2) the backend does not yet
   aggregate it either.
6. Browse the interaction-template/control/icon/animation catalog (today:
   20 templates, 11 controls, 25 icons, 29 animations seeded via
   `interaction_catalog.py`) as a library with previews — an admin must
   already know a template's `interaction_instance_id` to attach it.
7. Add a YouTube video and get help transcribing it, or get AI assistance
   drafting objectives/instructions/quiz questions, grounded in the existing
   knowledge graph (concepts, techniques, misconceptions, student mastery
   stats) and optionally the open web, with cited sources.
8. Reliably find every status/tag/target as a `Pill` — several are still
   plain text today.

## 2. Design principles

These extend (not replace) `.github/skills/modern-ui-design`'s existing
rules; nothing here should hard-code colors, add a second navigation shell,
or bypass the shared service layer.

1. **List → detail, not one page.** A compact course catalog drills into a
   per-course *workspace* with tabbed sections. No tab renders more than one
   screen's worth of primary content without scrolling only within that tab.
2. **One source of truth.** Every admin screen reads/writes through the same
   `micro_course_service.py` functions (and the small additions in §7) the
   REST API and CLI already share — this document adds screens, not a
   second business-logic path.
3. **Immutability stays visible, not hidden.** A published release is never
   silently "editable" — the UI always shows *which* release (draft vs.
   published vs. superseded) is in view, and "modify" always means "create
   (or continue) a draft version," never an in-place edit of published rows.
4. **AI is a suggestion, never a silent write.** Every AI- or graph-derived
   suggestion (transcript, drafted paragraph, quiz question, related
   concept) is inserted as an editable, clearly-labeled draft with its
   source shown (knowledge graph query, Wikipedia/web citation, or model
   name) and requires an explicit admin action to accept. This mirrors the
   existing paid-AI-generation consent pattern in
   [35_CORPUS_REPAIR_AND_AUTHORING.md](35_CORPUS_REPAIR_AND_AUTHORING.md)
   (CRA-6): a checkbox/button authorizes one bounded provider call, the
   draft keeps its AI-origin provenance, and nothing is auto-approved.
5. **Tags and targets are always pills.** Concepts, techniques, skills,
   misconceptions, template families, review/publication status, and video
   transcript status are never shown as plain text or raw enum strings.
6. **Preview is the real reader.** "View as student" renders the actual
   `mathbank-web/app/learn/courses/[code]/` stepper component against the
   draft/published release being edited — never a separate mock-up — so
   what the admin sees is what will ship.

## 3. Information architecture and navigation map

```
/admin/micro-courses                          Catalog (list)
/admin/micro-courses/{canonical_code}         Workspace (redirects to .../overview)
  ├── /overview                               Metadata, targets, objectives
  ├── /content                                Modules/states/transitions builder
  ├── /media                                  YouTube video + transcript workflow
  ├── /quizzes                                Quiz + interaction authoring
  ├── /widgets                                Interaction-template/control library (read-only browse)
  ├── /versions                               Release history, diff, promote-to-draft
  ├── /activity                               Enrollment/completion/quiz analytics
  └── /json                                   Raw JSON viewer (admin + student contract shapes)
/admin/micro-courses/new                      Creation wizard (replaces the inline "Create a course" form)
```

Each sub-route is a tab (`NavTabs`/`SectionTabs`, longest-matching-prefix
active, exactly like `mathbank-web/app/_components/NavTabs.jsx` already does
for other admin areas) under one `PageHeader`, not a separate page reload's
worth of chrome. Breadcrumbs: `Admin > Micro-courses > {course title}`
(the current tab is not a breadcrumb level — it's the tab bar).

### 3.1 Catalog — `/admin/micro-courses`

- `PageHeader` title "Micro-courses", one primary action: **"New course"**
  (opens `/admin/micro-courses/new`, not an inline form).
- Filter row: status (`Draft`/`Published`/`Superseded`/`Retired`/
  `Deactivated` — pills, multi-select), target type, text search over
  title/canonical_code.
- Compact table (or card list on narrow screens), one row per course:

  | Column | Content |
  |---|---|
  | Title | Course title + canonical_code in small/secondary text |
  | Target | Primary target `Pill` (concept/technique/skill name) |
  | Status | Status `Pill` (tone mirrors release/deactivation state) |
  | Version | `Pill` "v{N}" (+ "draft pending" pill if a DRAFT release also exists) |
  | Steps | icon-pill count (reuses the existing `list-check` icon convention) |
  | Enrollments | count, link to that course's `/activity` tab (0 is shown plainly, not hidden) |
  | Updated | relative date, computed client-side after mount (no server-rendered date, matching UI-15's no-hydration-drift rule) |

- Row click → course workspace `/overview`. Pagination via the existing
  `Pager` component at 25 rows, matching every other admin list.

### 3.2 Course workspace shell

`PageHeader`:
- Icon `diagram-3`, title = course title, subtitle = canonical_code.
- Pills: current published version (`success` tone) and, if present, a
  separate "Draft vN+1 in progress" pill (`warning` tone) — both can be true
  at once and must both be visible, since that is exactly the ambiguous
  state admins most need to see at a glance.
- Actions (icon buttons, each with `aria-label`/`title`, at most one
  rendered as a filled/primary button at a time):
  - **View as student** (`eye`) — opens the real reader at
    `/learn/courses/{canonical_code}` in preview mode (see §4.6).
  - **View JSON** (`braces`/`code`) — jumps to the `/json` tab.
  - **New draft version** (`file-earmark-plus`) — only enabled when the
    latest release is `PUBLISHED` and no `DRAFT` release already exists;
    see §4.1.
  - **Deactivate** / **Reactivate** (`slash-circle` / `arrow-counterclockwise`)
    — only enabled when a release is `PUBLISHED`; see §4.2.
  - **Delete draft** (`trash`, danger tone, confirmation required) — only
    enabled when the *selected* release is `DRAFT` and has never been
    published (protects against deleting the only record of a published
    course's history).

#### 3.2.1 Overview tab

- Metadata form: title, description, estimated minutes, difficulty level —
  editable only while the selected release's course-level identity is not
  yet locked by a PUBLISHED/SUPERSEDED/RETIRED release (mirrors MCR-2's
  existing immutability trigger; the UI must detect and explain this with a
  `Callout`, not just fail silently on save).
- Targets: primary/secondary/prerequisite `Pill` list with add/remove;
  "add target" opens a graph-backed search (existing
  `GET /v1/admin/micro-courses/targets`) with results shown as pills
  annotated by type.
- Learning objectives: an ordered, editable list (string or structured
  `{text}` entries, matching the existing `learning_objectives jsonb` field
  and the shape documented in doc 42 §3.1).
- Right rail: **Insights panel** (see §5) is available here because
  objective/description drafting is exactly where graph/AI grounding helps
  most.

#### 3.2.2 Content tab

- Replaces today's flat "add module / add state / course outline" stack
  with a visual, reorderable builder:
  - A left-hand **outline list** (states in ordinal order, grouped by module
    if any), each row showing state type `Pill`, required/optional `Pill`,
    and a drag handle for reordering (persists as `ordinal` updates).
  - Clicking a state opens its editor in the main pane: key/title/type/
    objective/instruction/required/skippable, plus *its* attached assets,
    interactions, and activities as sub-sections (not a separate page) —
    this is the one place state-level content is edited, so an admin is
    never hunting across tabs for "what does this one step contain."
  - "+ Add state" opens a small drawer (type picker with icon per
    `STATE_TYPE_LABELS`, matching the exact vocabulary the student reader
    already uses) rather than growing the page.
  - Transitions are edited as a compact table beneath the outline
    (from/to state pills, transition type, condition type), not a separate
    form far down the page.
- Right rail: Insights panel (same component as Overview).

#### 3.2.3 Media tab

- Lists every video/image/audio asset attached to any state in the selected
  release, grouped by state.
- **"+ YouTube video"** primary action opens a drawer:
  1. Paste a URL → fetch title/channel/duration (oEmbed or equivalent) →
     show an embedded preview exactly as the student reader would render it
     (reusing the `youTubeEmbedUrl()` logic from doc 42 §3.3).
  2. Pick the target state and `presentation_role`.
  3. **"Help me transcribe"** (AI, explicit consent checkbox per CRA-6's
     pattern) triggers a transcription job against the existing
     `pedagogy.video_transcript`/`video_transcript_segment` tables; shows a
     job-status `Pill` (`PENDING`/`RUNNING`/`DONE`/`FAILED`).
  4. On completion, a **segment review editor**: a scrollable list of
     timestamped rows (start/end, speaker, text), each individually
     editable and individually approvable (`PENDING_REVIEW`/`APPROVED`/
     `REJECTED` pill per segment) — matching the existing
     `video_transcript_segment.review_status` column and the publication
     rule that only `APPROVED` segments are ever shown to students or used
     for required-video validation (doc 40 MCR-17/validate_release).
  5. A manual-only path (paste/author a transcript without AI) remains
     available — AI assistance is additive, never the only route.

#### 3.2.4 Quizzes tab

- Per-state list of attached `activity.definition` rows (the quiz-question
  mechanism established in doc 42 §3.5), grouped by `purpose` pill
  (`ENTRY_CHECK`/`COMPREHENSION`/`TRANSFER`/…).
- "+ Add question" drawer: prompt, type (`MCQ`/`NUMERIC` picker), options,
  correct answer, explanation — with an optional **"Draft with AI"** ghost
  button next to the prompt field (see §5) that proposes a question grounded
  in the state's bound concepts/techniques/misconceptions, shown as an
  editable draft the admin must accept.
- A compact **answer-exposure notice**: because of the open contract issue
  in §7.1, this tab must show a `Callout` reminding the admin that, until
  that fix ships, `correctness_policy` (including the correct answer) is
  visible in the public/enrollment JSON before a student answers — so
  authors should not treat "hidden until opened" UI affordances (like the
  student reader's disclosure) as an actual security boundary today.

#### 3.2.5 Widgets tab (interaction-template library)

- Read-only (for now) browsable grid of the interaction-template catalog:
  one card per `interaction_template` × its versions, showing template
  key, family, version, status `Pill` (`DRAFT`/`REVIEWED`/`PUBLISHED`/
  `DEPRECATED`), and a live mini-preview — reusing
  `InteractionTemplateRenderer.jsx` against a small bundled demo config per
  template family (not the admin's own course data), so admins can see what
  e.g. `FUNCTION_GRAPH_EXPLORER_V1` looks like before deciding to use it.
- Filter by family/status; a `DRAFT` template version is shown but clearly
  marked "not yet attachable — publish the template version first," since
  only `PUBLISHED` versions satisfy `attach_interaction`'s existing
  approved-instance check.
- From here, "Create instance for this course" deep-links into the Content
  tab's "+ Add state" / attach-interaction flow for the current course, pre-
  filtering to that template.
- Also surfaces the control/icon/animation catalogs (11 controls, 25 icons,
  29 animations) as secondary, collapsed sections — reference material for
  whoever later authors new template schemas (not day-to-day course
  authoring, but "what exists" should not require reading JSON seed files).

#### 3.2.6 Versions tab

- Table of every release for this course: version, status `Pill`, created/
  reviewed/approved/published dates, created_by/reviewed_by/approved_by.
- **Diff view**: pick any two releases → a read-only, field-level summary
  (states added/removed/reordered, interactions attached/detached per
  state, targets changed, metadata changed) — enough to answer "what would
  change if I publish this draft," not a full line-level content diff.
- **"Promote to new draft"** on a non-latest release clones it forward as a
  new `DRAFT` release (`create_release` with `parent_release_id`), landing
  on the Content tab for that new draft.
- Publish workflow becomes a small wizard (Validate → Review → Publish),
  each step showing the existing `validate_release`/`review_release`/
  `publish_release` results as a scrollable, dismissible list of
  pass/fail items rather than inline page text.

#### 3.2.7 Activity tab

- `StatCard` row: total enrollments, in-progress, completed, completion
  rate, median time-to-complete.
- Per-step funnel: a `Bar`-based distribution showing how many enrollments
  reached each state (drop-off is visible step-by-step, in stepper order —
  deliberately mirroring the student-facing stepper's own ordering so an
  admin can mentally map "students stop here" to the exact step they'd see
  in preview).
- Per-quiz-question accuracy: question prompt (truncated) + `Pill`
  "`{n} correct / {n} answered}`" per `activity_id`, sourced from
  `learner.micro_course_state_event` (`event_type='ACTIVITY_RESPONSE'`).
- Recent activity feed: last N `ENROLLED`/`STATE_CHANGED`/`COMPLETED`/
  `ACTIVITY_RESPONSE` events (anonymized to initials/avatar, consistent with
  existing student-list privacy conventions elsewhere in the admin UI).
- This tab explicitly depends on §7.2 (an aggregation path); it must not
  silently show zeros/empty — an empty state should say "no activity yet"
  only when that is actually true, and should say "activity aggregation not
  yet available" if the backing query/rollup isn't implemented.

#### 3.2.8 JSON tab

- Two side-by-side (stacked on narrow screens) read-only panes:
  1. **Admin shape** — exactly what `GET /v1/admin/micro-courses/{code}`
     returns for the selected release.
  2. **Student/public shape** — exactly what
     `GET /v1/micro-courses/{canonical_code}` (or, if a draft is selected
     and nothing is published yet, an explicit "not publicly visible yet"
     notice instead of fabricating a preview payload) returns, matching
     doc 42 §3.1 field-for-field.
- Syntax-highlighted, collapsible tree or raw `<pre>` with a copy button;
  no editing here — this tab is for verification/debugging, not authoring.

### 3.3 Creation wizard — `/admin/micro-courses/new`

Replaces the inline "Create a course" form with a short, 3-step wizard
(stepper pattern, reusing the same visual language as the student stepper
for consistency, not the same component):
1. **Identity** — canonical code, title, description.
2. **Target** — graph-backed search/pick for the primary target (and
   optional secondary/prerequisite targets), showing the Insights panel
   (§5) immediately so the admin sees related concepts/mastery stats before
   committing to a target.
3. **Starting point** — "blank course" or "clone an existing course's
   structure as a starting draft" (states/transitions copied, content left
   for the admin to edit — never auto-published).

On finish, lands on the new course's `/overview` tab.

## 4. Behavior details for the hardest flows

### 4.1 "Modify currently-immutable content" → new draft version

Published content is never edited in place (doc 40 MCR-3). The UI's only
affordance for "I want to change something" on a published course is **New
draft version**, which:
1. Calls `create_release(parent_release_id=<published release>)`.
2. Switches the workspace into "editing DRAFT v{N+1}" mode — a persistent
   banner across every tab: *"Editing draft v{N+1}. The published v{N}
   lesson is unaffected until you publish this draft."*
3. Every tab operates against the draft release only; the Activity tab
   stays pinned to showing the *published* release's analytics (a draft has
   no enrollments yet by definition) with a note explaining why.

### 4.2 Deactivate / Reactivate

A published course can be hidden from the student catalog without
retiring its release history (retiring/superseding is a release-level
concept already; deactivation is course-level and currently has no
schema support — flagged as new work in §7.3). While deactivated:
- The course does not appear in `list_published_courses`/the student
  catalog.
- A direct link to `/learn/courses/{code}` shows the same "course
  unavailable" empty state the reader already uses for not-found courses.
- The admin catalog shows it with a `Deactivated` pill and keeps all
  existing admin/JSON/activity access.

### 4.3 Preview parity

"View as student" must never be a second, simplified renderer. It opens the
real `/learn/courses/{canonical_code}` route, with an admin-only query
flag that (a) allows previewing a `DRAFT` release the admin owns even
though it is not publicly published, and (b) shows a persistent "Admin
preview — not visible to students" banner reusing the `Callout` component.

## 5. Insights panel (graph + mastery + web, with citations)

A collapsible right rail available on Overview/Content/Quizzes, built from
existing, already-deployed data sources — no new model/graph infrastructure
required, only new read-only queries/aggregations and a UI:

| Section | Source | Shown as |
|---|---|---|
| Related concepts/techniques | `knowledge.concept`/`knowledge.technique` graph neighborhood of the course's primary target (existing concept-neighbor queries, e.g. `GET /v1/concepts/{slug}/neighbors`) | `Pill` list, click to add as a secondary/prerequisite target |
| Student mastery on this target | Existing `GET /v1/admin/knowledge-gaps`, `GET /v1/admin/students/{id}/knowledge-gaps`, and the learner mastery/improvement-plan endpoints, aggregated across students | A compact distribution `Bar` ("N% of students show a gap here") — never a single student's private data without an explicit per-student drill-down action |
| Common misconceptions | `knowledge.misconception` rows linked to the target | `Pill` list with description on hover/expand — candidates for quiz distractors |
| Similar existing courses | `pedagogy.micro_course_target` sharing the same/neighboring target | Course title links, to avoid duplicate authoring |
| Wiki/web lookup | Explicit, admin-triggered search (not automatic) against a configured external source | Result snippets, each with a visible source link; **"Insert as draft paragraph"** inserts into the currently-focused editable field as plain, editable text — never auto-applied, and the inserted text itself does not have to retain a visible citation footnote in the student-facing field, but the panel interaction that produced it is logged as an authoring provenance event (new work, §7.4) |

Every item in this panel is inert data display plus an explicit "use this"
action; nothing in the panel ever writes to the course automatically.

## 6. Requirement inventory (AMC-*)

| ID | Requirement | Acceptance | Status |
|---|---|---|---|
| AMC-1 | Catalog/workspace separation | `/admin/micro-courses` is a compact, filterable, paginated list only; all authoring happens in a per-course workspace at `/admin/micro-courses/{code}`, never inline on the list page. | ✅ Shipped |
| AMC-2 | Tabbed workspace | The workspace renders Overview/Content/Media/Quizzes/Widgets/Versions/Activity/JSON as tabs under one `PageHeader`; no tab requires leaving the page to reach another tab's content. | ✅ Shipped |
| AMC-3 | JSON view parity | The JSON tab's two panes are byte-for-byte (modulo formatting) what the admin and student REST reads already return — it must never diverge from or duplicate doc 42's contract. | ✅ Shipped |
| AMC-4 | Deactivate/reactivate | A published course can be hidden from the student catalog and restored, independent of release-level status, without altering release history. | ✅ Shipped (migration 035) |
| AMC-5 | New-draft-version workflow | "Modify" a published course always creates (or resumes) exactly one DRAFT release via `create_release`; the UI makes which release is being edited unambiguous at all times (persistent banner + pill). | ✅ Shipped (Versions tab + workspace header pills) |
| AMC-6 | Version diff | Admins can compare any two releases of a course and see a field-level summary of what changed, before committing to publish. | ✅ Shipped |
| AMC-7 | Activity/analytics tab | Enrollment counts, completion rate, per-step drop-off, and per-question accuracy are shown, sourced from real `learner.*` event/enrollment data (live query or rollup — decision in §7.2), with an honest "not yet available" state instead of fabricated zeros. | ✅ Shipped as a live query (§7.2 kept as-is; no rollup consumer yet) |
| AMC-8 | Widget/template library | All seeded interaction templates (and their controls/icons/animations) are browsable with live previews and clear PUBLISHED/DRAFT attachability status, without needing to already know an `interaction_instance_id`. | ⚠️ Partially shipped — browsable list with status pills; live mini-previews deferred |
| AMC-9 | YouTube + AI transcription flow | Adding a YouTube video, requesting AI transcription (explicit consent), and reviewing/approving segments happens in one guided flow, reusing the existing `video_transcript`/`video_transcript_segment` approval model unchanged. | ⛔ Deferred — Media tab supports manual asset/YouTube upload; AI transcription explicitly flagged "coming soon" |
| AMC-10 | AI-partnered drafting | Objective/instruction/quiz-prompt fields offer an optional "Draft with AI" action that proposes editable, source-labeled content grounded in graph/mastery/misconception/wiki data; nothing is ever written without an explicit accept. | ⛔ Deferred — flagged "coming soon" in Quizzes tab |
| AMC-11 | Graph insights rail | Related concepts/techniques, aggregate student mastery gaps, common misconceptions, and similar existing courses are surfaced contextually during authoring, each with its data source labeled. | ⛔ Deferred |
| AMC-12 | Cited web lookup | An explicit, admin-triggered web/wiki search shows source-linked snippets and only inserts text into a field on explicit admin action. | ⛔ Deferred |
| AMC-13 | Pills everywhere | Every status, target, tag, template family, and review state in the admin micro-course UI renders as a `Pill`, never plain text — audited tab-by-tab before this doc is marked delivered. | ✅ Shipped across all 8 tabs |
| AMC-14 | Preview parity | "View as student" always renders the real student stepper route, including for an admin-owned unpublished draft, with a visible "admin preview" banner and no second renderer to maintain. | ✅ Shipped (`GET /{code}/preview`, `?preview=1` on the real reader route) |

## 7. Backend/data gaps this plan depends on (not implemented by this document)

1. **Legacy v1 quiz-answer exposure (migration gap; target v2 is defined in §43.I and doc 42 §42.B) (blocks trusting AMC-7/the Quizzes tab's premise
   that answers are "secret" until attempted).** `get_published_course` and
   `get_enrollment_runtime` currently return `correctness_policy` —
   including the correct index/value and explanation — in full, before any
   attempt. A future change should split this: the public/enrollment read
   returns `prompt`/`options`/`activity_type` only, and the
   `POST .../activity-responses` response returns the explanation/answer
   confirmation (which it already does). This is a contract change against
   [42_MICRO_COURSE_STUDENT_NAVIGATION.md](42_MICRO_COURSE_STUDENT_NAVIGATION.md)
   §3.5 and needs its own design/approval before implementation.
2. **Analytics aggregation.** No table or materialized view aggregates
   `learner.micro_course_enrollment`/`learner.micro_course_state_event`
   today; the Activity tab (§3.2.7) needs a decision between live
   aggregate queries (simpler, slower at scale) and a scheduled rollup
   table (more work, cheaper to read) before AMC-7 can be built.
3. **Course-level deactivation flag.** `pedagogy.micro_course` has no
   `is_active`/deactivation column or audit trail today; AMC-4 needs a
   small, additive migration plus a guard consistent with the existing
   published-identity-immutability trigger (deactivation should still be
   possible on a published, otherwise-immutable course — the exception
   needs to be modeled explicitly, not bolt onto the identity guard).
4. **Authoring-provenance logging for AI/graph-assisted inserts.** AMC-10/
   AMC-12 call for logging *that* an AI/graph/wiki suggestion was inserted
   and accepted (not necessarily keeping a visible citation in the
   student-facing text) — there is no such audit table yet; needs its own
   schema addition modeled after the existing AI-origin provenance pattern
   used in corpus authoring (doc 35).

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
