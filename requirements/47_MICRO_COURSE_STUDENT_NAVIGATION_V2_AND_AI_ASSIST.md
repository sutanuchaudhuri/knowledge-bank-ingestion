# 47. Micro-course student navigation v2: per-item decomposition, single-active-item, and scoped AI assist (planning only)

> **Explicit scope note.** Planning and design only — **no code has been changed**. This document
> refines and partially supersedes [doc 42](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/42_MICRO_COURSE_STUDENT_NAVIGATION.md)'s
> already-*implemented* stepper (which decomposes a course into **states**, one visible at a time)
> by addressing a layer doc 42 did not: decomposing **inside** a state, where multiple videos,
> interactions, pre-checks and quizzes can all live together today. Doc 42 remains correct and
> implemented at the state level; this document is additive to it, not a rewrite.

## 0. Status and scope

| | |
|---|---|
| Status | **Planning only.** Not implemented. |
| Trigger | Admin ask: within a micro-course state/menu item, pre-quiz and intermediate-quiz items must show as distinct sub-items in the menu; only one quiz (or interaction) should be active/visible at a time even when a state has multiple videos/interactions; a "Give up"/"Help me?" micro-chat should assist with the *current* item specifically; other AI-encouraging interaction patterns. |
| Grounding | Live reading of [learn/courses/[code]/page.jsx](</Volumes/External/Developer/knowledge-bank-ingestion/mathbank-web/app/learn/courses/[code]/page.jsx>), the per-state child tables in [032_micro_course_platform.sql](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-db/sql/032_micro_course_platform.sql)/[034_micro_course_template_bindings.sql](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-db/sql/034_micro_course_template_bindings.sql), and the already-written (not implemented) AI-scoping design in doc 42 §42.H/42.I and [doc 44 §10](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/44_MICRO_COURSE_MOBILE_AI_ANALYTICS_PLATFORM.md). |

## 1. What exists today (verified, not assumed)

### 1.1 A state can already hold multiple items of every kind — and the schema already orders each kind independently

Every per-state child table already has its own `ordinal` (verified by reading the actual
`CREATE TABLE` statements):

| Child kind | Table | Ordinal scope |
|---|---|---|
| Video/image/audio/link | `pedagogy.micro_course_state_asset` | `UNIQUE (state_id, ordinal)` — own sequence |
| Interactive widget | `pedagogy.micro_course_state_interaction` | `UNIQUE (state_id, ordinal)` — own sequence |
| Gating quiz ("pre-quiz"/"exit check"/etc.) | `pedagogy.micro_course_state_learning_item` | `UNIQUE (state_id, ordinal)` — own sequence, plus a real `purpose` enum (`ENTRY_CHECK`/`EXIT_CHECK`/.../`TRANSFER`) |
| Preview quiz | `pedagogy.micro_course_state_activity` | `UNIQUE (state_id, ordinal)` — own sequence |

So a state can genuinely contain, e.g., `[video#0, learning_item(ENTRY_CHECK)#0, interaction#0,
video#1, activity#0]` — but **there is no cross-kind ordering**. Each kind's `ordinal` is only
unique *within that kind*, so there is no data today that says "the entry-check quiz comes after
video#0 but before interaction#0." This is the structural reason the current renderer can't
interleave them correctly even if it wanted to.

### 1.2 The student reader renders every item of every kind simultaneously, grouped by kind, not by authored sequence

Read directly from `StepContent` in `page.jsx`: the render order is a **fixed bucket order** —
all `assets` (§line ~159), then all `interactions` (§line ~204), then a collapsed transcript
`<details>`, then all `learning_items` (§line ~222), then all `activities` (§line ~234), then all
`qa_contexts` (§line ~238) — always all of them, always in that bucket order, never one-at-a-time
and never honoring the admin's actual intended position (e.g. "the quiz goes *between* the two
videos"). This is the direct cause of the complaint: multiple videos/interactions/quizzes all pile
up on one scrolling page per state.

### 1.3 `learning_items` render as inert, non-interactive text today — a functional gap, not just a layout one

`state.learning_items?.map(...)` (§line ~222) renders each one as a `<Callout>` with the question
text and a plain `<ul>` of choice strings — **no click handler, no submit, no grading at all**.
Contrast with `state.activities?.map(...)` which uses the fully interactive `QuizActivity`
component (buttons, local+server grading, answer never pre-highlighted). This means today's
"pre-quiz"/"intermediate quiz"/"exit check" items (the `learning_item` mechanism, which is also
the one that actually gates `can_continue`) are not actually answerable by a student in the
reader UI at all. This is likely the literal cause of the earlier-session complaint "quizzes not
seen" and must be fixed as part of any decomposition work, not treated as a separate issue.

### 1.4 There is no help/chat/"give up" affordance anywhere in the student reader today

`grep -n "Ask\|chat\|Help\|give up"` across `page.jsx` and `InteractionTemplateRenderer.jsx`
returns zero UI affordances. Doc 42 §42.H ("Timestamp Q&A") and §42.I ("Scoped AI panel") already
specify a design for this — grounding order (approved transcript segment → state Q&A → active
interaction context → active route step → published retrieval → bound canonical node
descriptions), a single semantic `ASK` action, and "never answer from unscoped general
knowledge" — but **none of it is built**; it is itself still a planning section. This document
narrows and operationalizes that existing plan around the specific ask here: scope the
assist/chat to the *current single active item*, not the whole state.

## 2. Proposed design — per-item decomposition and single-active-item gating

### 2.1 A new, additive, backward-compatible cross-kind sequence

```sql
ALTER TABLE pedagogy.micro_course_state_asset         ADD COLUMN IF NOT EXISTS sequence_position smallint;
ALTER TABLE pedagogy.micro_course_state_interaction   ADD COLUMN IF NOT EXISTS sequence_position smallint;
ALTER TABLE pedagogy.micro_course_state_learning_item ADD COLUMN IF NOT EXISTS sequence_position smallint;
ALTER TABLE pedagogy.micro_course_state_activity      ADD COLUMN IF NOT EXISTS sequence_position smallint;
```

Nullable and additive, so every already-published release keeps rendering exactly as it does
today (old behavior = "no `sequence_position` set anywhere in this state" → fall back to the
current grouped-by-kind rendering, so nothing regresses). When an admin authors a *new* state (or
a new draft version of an existing one), the authoring UI (doc 43's Content tab, extended)
assigns `sequence_position` across all kinds sharing one counter per state, and the student reader
switches that state to item-by-item mode. A per-state `GET` response gains one new derived field:

```json
"items": [
  {"item_kind": "asset", "item_id": "...", "sequence_position": 0},
  {"item_kind": "learning_item", "item_id": "...", "sequence_position": 1, "purpose": "ENTRY_CHECK"},
  {"item_kind": "interaction", "item_id": "...", "sequence_position": 2},
  {"item_kind": "asset", "item_id": "...", "sequence_position": 3},
  {"item_kind": "activity", "item_id": "...", "sequence_position": 4, "purpose": "TRANSFER"}
]
```
— a flattened, ordered view the reader iterates, instead of the four separate buckets it reads
today (`assets`/`interactions`/`learning_items`/`activities` stay in the payload unchanged, for
backward compatibility with anything else consuming them; `items` is additive).

### 2.2 Menu decomposition: state stays the primary rail entry, items become its expandable sub-rail

```text
STEPS
✓ 1 Prereq
✓ 2 State model
● 3 Matrix                    <- current state, expanded
    ✓ Intro video
    ● Pre-check quiz          <- current item within the state
    ○ Transition matrix (interactive)
    ○ Worked example video
    🔒 Transfer check
○ 4 Practice
🔒 5 Transfer
```

This is a direct, minimal extension of the existing `CourseStepper` component (doc 42's
implemented stepper already renders a flat list of states with the same done/current/locked dot
convention) — the same three-state iconography (✓/●/🔒) applies one level deeper, to items inside
the current state, rather than inventing a new visual language.

### 2.3 Single-active-item gating (the core new rule)

Only the content panel for the **current** `sequence_position` within the current state renders;
everything before it is reachable (click to review, read-only, matches doc 42 MCN-5's existing
"review without losing live position" rule) and everything after it is locked (🔒, matching MCN-4's
existing stepper-lock convention). A `can_continue`-style per-item gate applies exactly like it
already does at the state level:

- `required=true` asset/interaction: advances automatically once viewed/interacted with (asset
  "viewed" = video reached e.g. 90% watched or an external link opened; interaction "progressed" =
  at least one meaningful `CONTROL_SETTLED` event recorded — reusing this session's already-shipped
  interaction-event wiring, not inventing new telemetry).
- `required=true` learning_item/activity: advances only after a correct (or, depending on
  `purpose`, any) answer is recorded — reusing the exact same gating semantics doc 42 already
  specifies at the state level (`can_continue`), just applied one level down.
- `required=false` items of any kind: a visible "Skip" control advances without completion.

### 2.4 Fixing §1.3 as part of the same change

`learning_item` rendering becomes interactive, reusing the exact same `QuizActivity`-shaped
component `activity` already uses (choice buttons / numeric input, local+server grading, answer
never pre-highlighted) rather than the current static `<Callout>` + `<ul>`. This is a rendering
fix, not a new mechanism — `QuizActivity` today hard-assumes `activity.definition`'s field names
(`options`/`correctness_policy.correct_index`); it needs a small adapter for `learning_item`'s
differently-named fields (`choices`/`correct_answer`), not a second parallel component.

### 2.5 Responsive behavior

- **Desktop (≥992px):** the expandable sub-rail shown in §2.2 lives inside the existing left rail,
  directly under the current state entry; other (non-current) states stay collapsed to their
  single row.
- **Tablet (768–991px):** the existing horizontal-scrollable state row (doc 42 §42.D) gains a
  second horizontal-scrollable row directly beneath it, showing only the current state's items —
  never both the state list and a fully expanded item tree stacked vertically, to avoid doc 44's
  tablet-tier requirement (MCX-1) regressing into a cramped phone-style layout.
- **Phone (<768px):** the existing compact dot row (doc 42 §42.E) gains a one-line sub-label under
  it showing only "Item 2 of 5 · Pre-check quiz" (current item name + position), with left/right
  chevrons to step through items — no expanded tree on this tier, consistent with doc 42's
  existing "no horizontal page overflow" phone rule.

## 3. Proposed design — "Give up" / "Help me?" micro-chat, scoped to the current item

### 3.1 Trigger and placement

A single, consistently-placed ghost button/icon next to the current item's content (not a
floating global chat widget) — wording **"Help me?"** by default (softer and less failure-coded
than "Give up"; this document recommends "Help me?" as the primary label and treats "Give up" as
an available synonym/registered intent, not the UI's own wording, per the writing-rule in the
modern-ui-design skill against discouraging language). Opens an inline micro-chat panel anchored
to that item, not a new page/route.

### 3.2 Grounding (reuses doc 42 §42.I's already-specified hierarchy, narrowed to "current item only")

For the current item's `item_kind`, resolve grounding in this fixed order, never falling through
to unscoped general knowledge (doc 42/44's existing hard rule, preserved unchanged here):

1. **learning_item/activity**: the item's own `question_text`/`prompt`, `purpose`, and (after the
   student has answered — never before, to avoid doc 43 §7.1's existing answer-exposure issue
   getting worse) the `explanation` field.
2. **interaction**: the interaction's `learning_objective` and the student's own recent
   `interaction_event` history for that instance (what they've already tried).
3. **asset (video)**: the nearest approved transcript segment to the video's last-watched
   timestamp (doc 42 §42.H, already specified, just reused per-item instead of per-state).
4. Then, only after exhausting 1–3: the state's `state_qa_context` rows and the course's bound
   canonical concept/technique/skill descriptions (doc 42 §42.I's existing steps 2–6).

Backend reuse, not new infrastructure: the existing `/v1/tutor/coach`, `/v1/tutor/micro-check`,
and `/v1/tutor/guidance-plan` endpoints in
[pedagogy.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/routers/pedagogy.py)
already implement exactly this kind of grounded-response pattern for the main corpus tutor; this
document proposes a thin micro-course-scoped variant of the same pattern (new endpoint, same
underlying grounding/response-shape conventions), not a new AI subsystem.

### 3.3 "Give up" semantics specifically

When the student's intent is "give up" rather than "help me understand," the response differs:
- for a `required` gating item, "give up" reveals the correct answer/explanation immediately (an
  explicit student-initiated reveal, which is a materially different, already-informed-consent
  situation from doc 43 §7.1's *passive* pre-answer exposure problem — this document does not
  change or depend on that fix) and marks the attempt accordingly (e.g. `gave_up: true` on the
  recorded event) so analytics (doc 44 §4) can distinguish "got it right," "got it wrong," and
  "gave up" as three outcomes, not two.
- for a non-gating/optional item, "give up" simply skips it (same as §2.3's existing Skip
  control) — "give up" and "skip" converge for anything that was never going to block progress.

### 3.4 Other AI-encouraging interactions (documented, bounded by doc 44 MCX-17's existing non-manipulation rule)

- A single, low-frequency, dismissible nudge after **two consecutive wrong attempts** on the same
  gating item (not a popup — an inline `Callout tone="hint"` directly under the item, e.g. "Want a
  hint?" opening the same micro-chat already described in §3.1 — one mechanism, two entry points).
- A "what does this unlock" one-line preview when hovering a locked 🔒 item in the sub-rail (named
  content, not a generic lock icon with no information) — orients the student without revealing
  answers, addressing the earlier-session complaint about wanting to know "where the questions
  will be asked."
- Explicitly **not** proposed: streaks, points, badges, or any scoring layer — doc 44 MCX-17
  already rules this out for the whole platform, and this document does not reopen that decision.

## 4. Telemetry and traceability implications (documented, reusing existing mechanisms only)

- Each micro-chat open/response should enqueue one `audit.action_log` row and reuse the existing
  AI-usage-event mechanism from doc 44 §12 (once implemented) — no new logging mechanism, same
  correlation-id pattern already specified there.
- "Gave up" vs. "answered correctly" vs. "answered incorrectly" becomes a third recordable outcome
  on the existing `ACTIVITY_RESPONSE`/learning-item-response event shapes (one new enum value, not
  a new table).

## 5. Explicit non-goals

- **Not** changing doc 42's state-level stepper, locking, or review semantics — those are
  implemented and correct; this document only adds a layer underneath them.
- **Not** implementing the AI grounding/retrieval mechanism itself — §3.2 narrows doc 42 §42.I's
  existing (also unimplemented) design, it does not replace the work of building it.
- **Not** re-opening doc 43 §7.1's pre-answer `correctness_policy` exposure issue — §3.3's
  explicit, student-initiated "give up" reveal is a different situation and does not depend on, or
  substitute for, fixing that passive exposure gap.
- **Not** adding gamification/scoring — see §3.4.
- **Not** implementing anything in this pass — see §0.

## 6. Requirement inventory (MCN2-*)

| ID | Requirement | Acceptance evidence |
|---|---|---|
| MCN2-1 | Cross-kind item sequencing within a state | New `sequence_position` populated for a state makes the reader render items one at a time in authored order, interleaved across asset/interaction/learning_item/activity kinds |
| MCN2-2 | Backward compatibility for already-published releases | A release authored before this change (no `sequence_position` set) renders exactly as it does today — grouped by kind, all at once — with zero regression |
| MCN2-3 | Menu decomposes the current state into its items | The stepper's sub-rail (desktop) / second row (tablet) / item label+chevrons (phone) shows every item of the current state with done/current/locked status |
| MCN2-4 | Only the current item's content is interactable | Items after the current `sequence_position` are not rendered/interactable (locked); items before it are reachable read-only (review), matching the existing state-level MCN-4/MCN-5 rules one level down |
| MCN2-5 | `learning_item`s are actually interactive | A `learning_item` renders with the same answerable UI as `activity` (choice buttons/numeric input), not a static list |
| MCN2-6 | Scoped "Help me?" / "Give up" assist on the current item | Opens an inline panel grounded per §3.2's fixed order for the current item only; never answers from unscoped general knowledge |
| MCN2-7 | "Give up" is a distinguishable, recorded outcome | A gave-up attempt is recorded as a third outcome (distinct from correct/incorrect) on the existing response event, visible in doc 44's analytics rollups once built |
| MCN2-8 | No manipulative engagement mechanics | The nudge pattern in §3.4 stays dismissible, content-specific, and free of points/streaks/badges |

## Cross-document relationship

- Extends (does not replace) [doc 42](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/42_MICRO_COURSE_STUDENT_NAVIGATION.md),
  whose state-level stepper remains implemented and unchanged.
- Narrows and reuses the AI-grounding design already specified in doc 42 §42.H/§42.I and
  [doc 44 §10](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/44_MICRO_COURSE_MOBILE_AI_ANALYTICS_PLATFORM.md) —
  does not introduce a second, competing AI-scoping design.
- Independent of [doc 46](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md)'s
  admin-authoring endpoints, though the two naturally combine: doc 46 lets an admin author/attach
  a quiz; this document governs how that quiz is sequenced and gated for the student. No ordering
  dependency either direction.
