# 46. Micro-course quiz/activity admin authoring API gaps (planning only)

> **Explicit scope note.** Planning and design only — **no code, schema, or endpoint has been
> changed** while producing this document. Every finding is grounded in the real schema
> ([020_live_fluid_platform.sql](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-db/sql/020_live_fluid_platform.sql),
> [032_micro_course_platform.sql](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-db/sql/032_micro_course_platform.sql)),
> the real service layer ([micro_course_service.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/micro_course_service.py)),
> the real router ([micro_courses.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/routers/micro_courses.py)),
> and the admin UI's own documented gap note in
> [QuizzesTab.jsx](</Volumes/External/Developer/knowledge-bank-ingestion/mathbank-web/app/admin/(protected)/micro-courses/[code]/QuizzesTab.jsx>)
> and [doc 43 §3.2.4/§7.1](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/43_ADMIN_MICRO_COURSE_AUTHORING_UI.md).

## 0. Status and scope

| | |
|---|---|
| Status | **Planning only.** Not implemented. |
| Trigger | Admin ask: "add quiz"/"add quizzes," "updateQuiz," "map quiz to source or skill," "deactivate quiz," and other quiz-related admin functionality for micro-courses. |
| Relationship to other docs | Extends [doc 45](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md)'s CRUD-gap methodology, applied specifically to quiz content; closes the exact gap [doc 43 §3.2.4](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/43_ADMIN_MICRO_COURSE_AUTHORING_UI.md) already flagged as "not yet available" when the Quizzes tab was built. |

## 1. What exists today (verified, not assumed)

### 1.1 Two parallel quiz mechanisms, with very different authoring origins

| Mechanism | Table | How content gets in today | Bound to a course state via | `purpose` values |
|---|---|---|---|---|
| **Learning item** | `pedagogy.learning_item` | Textbook/corpus import pipeline only (`book_code`, `source_transformation_id`, `source_problem_id` — see [010_textbook_import.sql](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-db/sql/010_textbook_import.sql)) | `pedagogy.micro_course_state_learning_item` | `CHECK IN ('ENTRY_CHECK','COMPREHENSION','RECOGNITION','MISCONCEPTION_DIAGNOSTIC','EXECUTION','EXIT_CHECK','TRANSFER')` — a real enum |
| **Activity** | `activity.definition` | No ingestion pipeline — meant to be authored directly (`source_type` includes `'INSTRUCTOR_CREATED'`) | `pedagogy.micro_course_state_activity` | plain `text`, **no CHECK constraint at all** — any string is accepted |

The admin ask ("add a quiz," "update a quiz") is about the **activity** mechanism — it is the one
designed to be instructor-authored, not the textbook-import one. This document scopes the new
CRUD surface to `activity.definition` / `pedagogy.micro_course_state_activity` only, and does not
propose adding ad hoc learning-item authoring (that remains a textbook-import concern, unchanged).

### 1.2 The service-layer functions already exist and are fully validated — only the REST endpoint is missing

[`attach_activity(conn, state_id, activity_id, ordinal, purpose, required=True)`](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/micro_course_service.py)
already:
- confirms the target release is still editable (`_editable_release`, i.e. DRAFT — can't silently
  change a published release);
- confirms the activity exists;
- **enforces `source_type IN ('PRECOMPILED','INSTRUCTOR_CREATED')`** (rejects, e.g., a
  `LIVE_AGENT_CREATED` ephemeral activity from being bound into durable course content);
- **enforces `persistence_mode = 'STATIC'`** (rejects `SESSION`/`EPHEMERAL` activities).

This is good, production-quality validation — written, in place, covered by none of it being
reachable from outside the Python process. `grep -rn "attach_activity" routers/` returns
**zero matches**: there is no `@router.post(...)` anywhere that calls this function. The same is
true of its sibling `attach_learning_item` (used only internally by seed scripts).

### 1.3 There is no endpoint to create or edit the quiz content itself

Nothing creates a new `activity.definition` row through REST. The only way a quiz question
(`prompt`, `options`, `correctness_policy`) gets created today is
`scripts/seed_reference_course_extras.py` (or an equivalent one-off script) issuing a raw insert —
confirmed by the comment already written into `QuizzesTab.jsx` by this session's own admin-UI
work. Likewise there is no endpoint to update an existing activity's `prompt`/`options`/
`correctness_policy`/`estimated_seconds` once created.

### 1.4 "Map quiz to skill" is ambiguous today because three different skill representations exist

| Column | Table | Type | Validated? |
|---|---|---|---|
| `activity.definition.target_skill` | `activity.definition` | plain `text` | ❌ no FK, free text |
| `pedagogy.learning_item.target_skill_node_id` | `pedagogy.learning_item` | `text` FK → `pedagogy.taxonomy_node` | ✅ FK-enforced, but a *different* taxonomy system (the legacy Canonical_Topic_ID tree) than... |
| `knowledge.skill.skill_id` | `knowledge.skill` | `uuid` | the one used by the governance workflow, `problem_skill`, and this session's micro-course canonical-target search |

A quiz authored for a micro-course should map to the **same canonical `knowledge.skill`** that
the course itself targets (so a quiz genuinely measures the course's own `PRIMARY`/`SECONDARY`
canonical target) — not the legacy `taxonomy_node` tree, and not an unvalidated free-text guess.
This document proposes adding a real FK, not reusing the existing free-text column as-is (see
§2.3).

### 1.5 "Map quiz to source" means the originating problem, and a lineage field already exists but is unstructured

`activity.definition.source_lineage jsonb NOT NULL DEFAULT '{}'::jsonb` exists today but is
free-form JSON with no documented shape and no endpoint to set it. `pedagogy.learning_item` has
the equivalent concept done properly: a real `source_problem_id uuid REFERENCES core.problem`.
This document proposes giving `activity.definition` the same structured option (see §2.4) rather
than leaving `source_lineage` as an undocumented jsonb bag.

### 1.6 "Deactivate a quiz" has no column to deactivate today, but has no historical-data entanglement either

`activity.definition` has no `status`/`is_active` column at all (unlike `knowledge.concept`/
`technique`, which at least have an unused one — see doc 45 §1.1). A new column is needed (§2.5).
The good news, confirmed by reading `submit_activity_response` directly: a micro-course quiz
attempt is recorded into `learner.micro_course_state_event` (`event_type='ACTIVITY_RESPONSE'`,
keyed by `enrollment_id`/`state_id`, with the `activity_id` only inside the jsonb `payload`) —
**not** a row in `activity.response`/`activity.instance` with an FK to `activity_id`. Deactivating
an `activity.definition` row therefore cannot orphan any historical response record; the
deactivate operation is low-risk from a referential-integrity standpoint.

## 2. Proposed new endpoints (not implemented)

Two tiers, split by ownership — because `activity.definition` is a shared table also used by the
live/fluid-session system (migration 020's original purpose), not something micro-courses own
exclusively:

### Tier A — the activity/quiz bank itself (content authoring, independent of any course)

```
POST   /v1/admin/activities                         Create a new INSTRUCTOR_CREATED, STATIC activity.definition
GET    /v1/admin/activities?q=&activity_type=&source_type=&status=&limit=&offset=   List/search (closes "no listing" gap)
GET    /v1/admin/activities/{activity_id}            Detail
PATCH  /v1/admin/activities/{activity_id}             Update prompt/options/correctness_policy/estimated_seconds
                                                       — 403/409 if source_type is not INSTRUCTOR_CREATED
                                                         (never allow editing a PRECOMPILED/corpus-derived activity
                                                         through this surface)
POST   /v1/admin/activities/{activity_id}/deactivate  New `status` column (§2.5); audit-logged
POST   /v1/admin/activities/{activity_id}/reactivate
PATCH  /v1/admin/activities/{activity_id}/skill-mapping    {"skill_id": "<knowledge.skill uuid>"}   (§2.3)
PATCH  /v1/admin/activities/{activity_id}/source-mapping   {"source_problem_id": "<core.problem uuid>"}  (§2.4)
```

### Tier B — binding a quiz into a specific micro-course state (wiring the existing service functions)

```
POST   /v1/admin/micro-courses/states/{state_id}/activities
       body: {"activity_id": "...", "ordinal": 0, "purpose": "ENTRY_CHECK", "required": true}
       → calls the already-built, already-validated attach_activity() directly. This is the
         single lowest-effort item in this whole document: the service function needs no new
         code, only a router handler + Pydantic model, mirroring the existing endpoints added
         this session for deactivate/reactivate.
DELETE /v1/admin/micro-courses/states/{state_id}/activities/{activity_id}   Detach (re-sequences remaining ordinals)
PATCH  /v1/admin/micro-courses/states/{state_id}/activities/{activity_id}   Change ordinal/purpose/required without detaching
```

### 2.1 Pydantic shape for "create a quiz" (Tier A `POST /v1/admin/activities`)

```python
class ActivityCreateRequest(BaseModel):
    activity_type: Literal["MCQ", "MULTISELECT", "NUMERIC", "SHORT_RESPONSE", "SUBPROBLEM",
                            "STEP_ORDERING", "ERROR_DIAGNOSIS", "CONFIDENCE_CHECK", "LIVE_POLL"]
    prompt: str = Field(min_length=1, max_length=4000)
    options: list[dict] = Field(default_factory=list)       # shape depends on activity_type
    correctness_policy: dict                                 # e.g. {"correct_index": 0} or {"correct_value": 3.5}
    estimated_seconds: int = Field(default=60, gt=0)
    skill_id: str | None = None        # knowledge.skill.skill_id — validated via §2.3's mapping
    source_problem_id: str | None = None  # core.problem.problem_id — validated via §2.4's mapping
```

`source_type` is **not** a client-settable field on this endpoint — the server always sets it to
`'INSTRUCTOR_CREATED'` and `persistence_mode` to `'STATIC'`, since this endpoint's entire purpose
is authoring exactly that kind of row (matches `attach_activity`'s existing validation, so nothing
created through this endpoint could ever fail to attach).

### 2.2 Literal-typed `purpose`, fixing the inconsistency noted in §1.1

Proposed: give `pedagogy.micro_course_state_activity.purpose` the same CHECK constraint as its
`micro_course_state_learning_item` sibling (`ENTRY_CHECK`/`COMPREHENSION`/.../`TRANSFER`), and type
the corresponding Pydantic field as the matching `Literal`, instead of free `text` on one side and
a real enum on the other for what is conceptually the same concept.

### 2.3 Skill mapping, concretely

```sql
ALTER TABLE activity.definition ADD COLUMN IF NOT EXISTS target_skill_id uuid REFERENCES knowledge.skill;
-- target_skill (free text) kept, unchanged, for any existing non-micro-course (live-session) callers;
-- new quizzes authored through Tier A always populate target_skill_id, never the free-text column.
```

`PATCH .../skill-mapping` validates `skill_id` against `knowledge.skill` (404 if unknown) — and,
per doc 45 §5.1, should ideally let the admin UI resolve it via a `q=` search
(`GET /v1/admin/taxonomy/skills?q=` from doc 45, or today's existing
`GET /v1/admin/micro-courses/targets?target_type=SKILL&q=`) rather than requiring a known UUID.

### 2.4 Source-problem mapping, concretely

```sql
ALTER TABLE activity.definition ADD COLUMN IF NOT EXISTS source_problem_id uuid REFERENCES core.problem;
```

`PATCH .../source-mapping` validates `source_problem_id` against `core.problem` (404 if unknown),
and the admin UI can resolve it via the existing, already-shipped
`GET /v1/problems?competition=&year_min=&...` search — no new lookup endpoint needed here, this
one already exists.

### 2.5 Deactivate, concretely

```sql
ALTER TABLE activity.definition ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE', 'INACTIVE'));
ALTER TABLE activity.definition ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;
ALTER TABLE activity.definition ADD COLUMN IF NOT EXISTS deactivated_by text;
```

Mirrors migration 035's `pedagogy.micro_course` pattern exactly, reuses the same
`record_audit_event()` helper with a new `entity_kind='ACTIVITY'`. A deactivated activity:
- is excluded from Tier A's default list (`status=ACTIVE` default filter, `status=ALL` to see it);
- **cannot be newly attached** to a course state (`attach_activity` gets one new check:
  `status='ACTIVE'`) — but a state that already has it bound keeps showing it (same "don't retroactively
  break already-published content" rule used for micro-course deactivation);
- should be blocked (409) from deactivation while it is still bound to a state belonging to a
  **published** release — same reasoning, and same error-message style, as doc 45 §5.4's proposed
  concept/technique guard and the existing micro-course identity-immutability trigger.

## 3. Admin UI implication (documented here, not built)

Once these endpoints exist, `QuizzesTab.jsx`'s current hard "not yet available" `Callout` (§1 of
this document) becomes a real "+ Add question" affordance exactly as already
scoped in [doc 43 §3.2.4](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/43_ADMIN_MICRO_COURSE_AUTHORING_UI.md#324-quizzes-tab):
prompt/type/options/correct-answer form, an inline skill-mapping/source-mapping picker backed by
the existing search endpoints, and a deactivate control per question — no redesign of that tab's
layout is implied, only wiring up the "Not yet available" notice's replacement.

## 4. Explicit non-goals

- **Not** proposing any change to the textbook-import `pedagogy.learning_item` authoring path —
  that stays script-driven, unchanged.
- **Not** proposing a generic "quiz bank" UI outside of micro-courses (e.g. for live sessions) —
  Tier A's CRUD is written generically enough to serve that need later, but this document scopes
  its own acceptance criteria to the micro-course quiz-authoring gap only.
- **Not** fixing the pre-existing, separately-tracked answer-exposure gap (`correctness_policy`
  visible before a student answers — doc 43 §7.1). That is explicitly out of scope here; this
  document only adds authoring/lifecycle endpoints, it does not change what is returned to a
  student at runtime.
- **Not** implementing anything in this pass — see §0.

## 5. Requirement inventory (QZA-*)

| ID | Requirement | Acceptance evidence |
|---|---|---|
| QZA-1 | Create a new instructor-authored quiz question | `POST /v1/admin/activities` creates a real `activity.definition` row with `source_type='INSTRUCTOR_CREATED'`, `persistence_mode='STATIC'` |
| QZA-2 | List/search the activity bank, including inactive items when asked | `GET /v1/admin/activities?status=ALL` returns both active and deactivated rows |
| QZA-3 | Update an instructor-authored quiz's content | `PATCH /v1/admin/activities/{id}` changes `prompt`/`options`/`correctness_policy`; rejected (409) for non-`INSTRUCTOR_CREATED` activities |
| QZA-4 | Bind/unbind/reorder a quiz within a course state via REST | `POST/DELETE/PATCH /v1/admin/micro-courses/states/{state_id}/activities[/{activity_id}]` exercise the existing `attach_activity` validation live |
| QZA-5 | Map a quiz to the canonical skill it measures | `PATCH .../skill-mapping` sets `activity.definition.target_skill_id`, validated against `knowledge.skill` |
| QZA-6 | Map a quiz to its originating problem | `PATCH .../source-mapping` sets `activity.definition.source_problem_id`, validated against `core.problem` |
| QZA-7 | Deactivate/reactivate a quiz, with audit trail and publish-immutability guard | Deactivated quiz disappears from default listing and can't be newly attached; reactivating restores it; one `audit.action_log` row per transition; deactivating a quiz bound to a published release's state is blocked (409) |
| QZA-8 | `purpose` is a real, consistent enum on both quiz-binding tables | `pedagogy.micro_course_state_activity.purpose` gains the same CHECK constraint already present on `micro_course_state_learning_item.purpose` |

## Cross-document relationship

- Extends [doc 45](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md)'s
  gap-analysis methodology and reuses its proposed `skill_id` lookup endpoint (§5.1 there).
- Closes the exact "not yet available" flag already written into
  [QuizzesTab.jsx](</Volumes/External/Developer/knowledge-bank-ingestion/mathbank-web/app/admin/(protected)/micro-courses/[code]/QuizzesTab.jsx>)
  and scoped in [doc 43 §3.2.4](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/43_ADMIN_MICRO_COURSE_AUTHORING_UI.md).
- Independent of [doc 47](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/47_MICRO_COURSE_STUDENT_NAVIGATION_V2_AND_AI_ASSIST.md)'s
  student-facing navigation changes — that document assumes quizzes exist and are rendered
  per-item; this document is about how an admin creates/manages them. No ordering dependency
  either direction, though both would naturally be picked up together if work resumes on the
  micro-course platform.
