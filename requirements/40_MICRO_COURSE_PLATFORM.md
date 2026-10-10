# 40. Deterministic micro-course platform

## Comprehensive-system orchestration contract

> **Normative precedence.** A micro-course is MathBank's orchestration layer. It composes
> already-approved route releases, interactions, SceneSpecs, videos/transcripts, activities,
> learning items, Q&A contexts and interventions into one immutable learner journey. It
> does not duplicate the internals of those subsystems.

### 40.A One state can compose multiple approved content types

A `CourseState` may contain ordered bindings to:

```text
visual.asset
pedagogy.video_asset + approved transcript segments
visual.interaction_instance
activity.definition
pedagogy.learning_item
published tutoring-route release
state_qa_context
intervention_script
```

Each subsystem remains authoritative for its own runtime.

### 40.B State composition model

```text
MicroCourseRelease
   |
   +-- Module
   |    |
   |    +-- CourseState
   |          |
   |          +-- semantic Concept/Technique/Skill/Misconception bindings
   |          +-- VideoAsset / approved segments
   |          +-- InteractionInstance / SceneSpec
   |          +-- Activity / LearningItem
   |          +-- TutoringRouteRelease
   |          +-- Q&A context
   |          +-- Intervention
   |
   +-- deterministic CourseState transitions
```

### 40.C Secure assessment payload

The target student contract does **not** expose answer keys before submission.

Public/enrollment activity payload:

```json
{
  "activity_id": "uuid",
  "activity_type": "MCQ",
  "prompt": "string",
  "options": ["A","B","C","D"],
  "purpose": "COMPREHENSION",
  "required": false,
  "response_contract": {"kind":"CHOICE_INDEX"}
}
```

Server-only:
- correct index/value;
- hidden predicate;
- scoring rule;
- answer-bearing explanation before attempt.

Submission response may return approved explanation/feedback after server evaluation.

### 40.D Interaction instance is a runtime, not a picture

For enrolled students, every interaction uses the deterministic interaction service:

```text
start
→ semantic event(s)
→ deterministic evaluation
→ partial/correct/error signature
→ object-specific feedback
→ evidence update
→ retry/probe/intervention
→ completion
```

The student renderer must never independently decide canonical correctness or
misconception confidence.

### 40.E Tutoring route attachment

Add the FK-backed state-route binding described in doc 39.

State runtime:
1. starts/resumes the existing route attempt;
2. stores pointer to active nested route attempt;
3. freezes course state while route subflow is active;
4. returns to the same state;
5. applies authored course transition after the route result.

### 40.F Video → Q&A → interaction → return

```text
VIDEO state
  |
  | pause at t
  v
approved TranscriptSegment
  |
  +--> approved Q&A answer
  +--> approved InteractionInstance
  +--> approved diagnostic/intervention
  |
  v
exact resume at t
```

No approved transcript segment => no timestamp-grounded question answering.

### 40.G Student-state screen composition wireframe

Desktop:

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Markov Chains                 v3 · 18 min                 Progress 4 / 9     │
├───────────────────┬──────────────────────────────────────────────────────────┤
│ COURSE STEPPER    │ STATE: Transition Matrices                              │
│ ✓ Prereq          │ Focus: build P from a state graph                       │
│ ✓ State model     │                                                          │
│ ✓ Video           │ ┌───────────────────┐  ┌──────────────────────────────┐ │
│ ● Matrix          │ │ approved video /  │  │ interactive matrix editor    │ │
│ ○ Practice        │ │ diagram / scene   │  │ + graph linked feedback      │ │
│ ○ Transfer        │ └───────────────────┘  └──────────────────────────────┘ │
│                   │                                                          │
│                   │ [Ask about this step] [Hint] [Start practice problem]   │
│                   │                                                          │
│                   │ Feedback / explanation panel                             │
├───────────────────┴──────────────────────────────────────────────────────────┤
│ [Back]                                      [Continue when requirements met]│
└──────────────────────────────────────────────────────────────────────────────┘
```

Course state should feel like one coherent lesson, even when it composes several systems.

### 40.H Unified release hash

Release content hash includes:
- identity/metadata;
- modules/states/order;
- transitions;
- semantic bindings;
- asset IDs + hashes;
- video/transcript approved versions where required;
- interaction instance + exact template version + instance hash;
- bound SceneSpec version;
- activity/learning-item identities/versions;
- tutoring-route release IDs;
- intervention/Q&A identities/hashes.

Exclude volatile timestamps/runtime analytics.

### 40.I One publication preflight

Return a structured report:

```text
IDENTITY
CANONICAL_BINDINGS
STATE_MACHINE
MEDIA
TRANSCRIPTS
INTERACTIONS
SCENE_SPECS
ASSESSMENTS
TUTORING_ROUTES
INTERVENTIONS
ASSETS
STUDENT_PAYLOAD_SECURITY
ACCESSIBILITY
SEARCH_READINESS
GRAPH_READINESS
```

Publication transaction:
lock → validate → require approved review → supersede prior published release →
publish → outbox → commit.

Graph/search execute later and report independent status.

### 40.J Structural graph only

Project:

```text
CourseState -[:TEACHES|REQUIRES]-> Concept|Technique
CourseState -[:REQUIRES|ASSESSES]-> Skill
CourseState -[:ADDRESSES|WATCHES_FOR]-> Misconception
CourseState -[:USES_INTERACTION]-> InteractionInstance
CourseState -[:USES_TUTORING_ROUTE]-> RouteRelease
CourseState -[:USES_VIDEO_SEGMENT]-> VideoSegment
CourseState -[:USES_LEARNING_ITEM]-> LearningItem
CourseState -[:CAN_TRIGGER]-> Intervention
```

Never project learner answers, mastery, route progress or misconception confidence.

### 40.K Comprehensive acceptance fixture

`MC-GEO-POWER-POINT` (or another reviewed fixture) must prove:

```text
canonical targets
+ approved transcript
+ video timestamp Q&A
+ approved interaction + SceneSpec
+ pre/intermediate/post checks
+ fixed misconception remediation
+ published tutoring route
+ release publication
+ structural graph parity
+ search representation
+ learner enrollment
+ interaction evidence
+ route subflow
+ exact resume
+ completion
+ analytics rollup
+ no learner-specific Neo4j data
```


## Decision and rollout

Requested 2026-10-09 UTC from the attached Copilot implementation pack
(`COPILOT_MICRO_COURSE_IMPLEMENTATION/COPILOT_MICRO_COURSE_IMPLEMENTATION.md`,
2,219 lines / §0-§43, plus a 1,434-line narrative design log and a
`NEXT_MIGRATION_SKELETON.sql` checklist — not executable DDL). The preceding
session reported migration 032 applied to the live database and its release
immutability guard tested; this session did not independently reconnect to
that database. The pack extends the existing architecture rather than
introducing a parallel platform: `Concept` stays `knowledge.concept`,
`"Strategy"` means the existing `knowledge.technique` (no new taxonomy),
`Skill` stays `knowledge.skill`; `pedagogy.learning_item` is reused for fixed
quizzes, `activity.definition` for static interactive checks, and
`visual.asset`/`visual.widget_spec` for images/diagrams/slides. PostgreSQL is
canonical; Neo4j is an asynchronously rebuildable projection scoped by
`projection_kind='micro_course'` that never wipes unrelated graph content.
A sibling pack ([41_INTERACTION_TEMPLATE_LIBRARY.md](41_INTERACTION_TEMPLATE_LIBRARY.md))
builds the richer interactive-widget/evidence layer on top of
`pedagogy.micro_course_state` and depends on this schema existing first.

## Complete requirement inventory

| ID | Requirement | Acceptance |
|---|---|---|
| MCR-1 | Canonical misconception library | `knowledge.misconception`: `canonical_code` UNIQUE, `name`, `description`, `symptom`, `why_wrong`, `correct_model`, `recognition_pattern jsonb`, `severity`/`level smallint`, `source`, `review_status` (`PENDING_REVIEW`\|`APPROVED`\|`REJECTED`). No FK out; distinct from the existing learner-specific `pedagogy.gap_diagnosis`/`knowledge_gap`. |
| MCR-2 | Micro-course identity and targets | `pedagogy.micro_course` (`canonical_code` UNIQUE, `title`, `description`, object-valued `metadata jsonb`, `estimated_minutes`, `difficulty_level`). Once any release is PUBLISHED/SUPERSEDED/RETIRED, identity and metadata are immutable. `pedagogy.micro_course_target` maps a course to exactly one of `concept_id`/`technique_id`/`skill_id` per row (CHECK enforces exclusivity matching `target_type`), `role` (`PRIMARY`\|`SECONDARY`\|`PREREQUISITE`). Publication requires at least one `PRIMARY` target. |
| MCR-3 | Immutable versioned releases | `pedagogy.micro_course_release`: `version` + `UNIQUE(micro_course_id, version)`, `parent_release_id` lineage, `status` DRAFT→REVIEWED→APPROVED→PUBLISHED→SUPERSEDED/RETIRED, `UNIQUE INDEX ... WHERE status='PUBLISHED'` (exactly one published release per course). Editing published content is impossible: REST mutation of published content returns `409`; a guard trigger (mirroring `authoring.presentation_plan`'s proven pattern) blocks INSERT/UPDATE/DELETE on any child of a PUBLISHED/SUPERSEDED/RETIRED release except the PUBLISHED→SUPERSEDED/RETIRED transition itself. New edits always start a new DRAFT release via `parent_release_id`. |
| MCR-4 | Modules and states | `pedagogy.micro_course_module` (ordinal-unique per release) and `pedagogy.micro_course_state` (`state_type` one of ORIENTATION/EXPLANATION/SLIDE/VIDEO/READING/VISUAL/EXAMPLE/CHECKPOINT/QUIZ/DIAGNOSTIC/REMEDIATION/PRACTICE/SUMMARY/TRANSFER; `required`/`skippable`; `agent_policy jsonb`). Unique `state_key` and `ordinal` per release. |
| MCR-5 | FK-backed semantic state bindings | `micro_course_state_concept` / `_technique` / `_skill` / `_misconception`, each `(state_id, target_id, role)` PK — no free-text taxonomy. Technique roles include TEACHES/REQUIRES/RECOGNIZES/APPLIES/REVIEWS; misconception roles WATCH_FOR/ADDRESSES/DIAGNOSES. |
| MCR-6 | Reused asset/quiz/activity attachment | `micro_course_state_asset` → `visual.asset` (presentation metadata plus private `object-store:<key>` URI, SHA-256 content hash and `object_size_bytes`); bytes remain in the existing private object store, never public/presigned URLs. Admin upload is size/MIME bounded and approved only through the protected authoring surface. Student delivery requires a published-course attachment, `VALID` status and integrity checks; private keys are not returned to browser JSON. Asset metadata/content identity is immutable while used by a final release. `micro_course_state_learning_item` → `pedagogy.learning_item` (purpose ENTRY_CHECK/COMPREHENSION/RECOGNITION/MISCONCEPTION_DIAGNOSTIC/EXECUTION/EXIT_CHECK/TRANSFER); `micro_course_state_activity` → `activity.definition`, which MUST use `source_type IN (INSTRUCTOR_CREATED, PRECOMPILED)` and `persistence_mode='STATIC'` — never `LIVE_AGENT_CREATED`. No second quiz bank, no second generic binary store. |
| MCR-7 | Curated YouTube ingestion workflow | Admin pastes a URL → server normalizes provider+ID, fetches metadata, registers `visual.asset` + `pedagogy.video_asset` (`transcript_status` MISSING by default, `review_status` PENDING_REVIEW), does **not** publish, and opens transcript import. No learner route can discover/search videos. The existence of a video URL or a provider's public chapter list is never treated as a transcript. |
| MCR-8 | Transcript import and human-reviewed segmentation | `pedagogy.video_transcript` (`source_type` PROVIDER_CAPTIONS/HUMAN/MODEL_TRANSCRIPTION/IMPORTED_FILE; DRAFT→REVIEWED→APPROVED→SUPERSEDED) and `pedagogy.video_transcript_segment` (`start_ms`/`end_ms`/`transcript_text`, `review_status`). A Transcript Annotator UI (video + timeline + timestamped transcript + segment editor + concept/technique/skill/misconception binding panel) supports seek/split/merge/retime/edit/annotate/approve. `video_segment_concept/technique/skill/misconception` are FK-backed binding tables (technique roles EXPLAINS/USES/REQUIRES/RECOGNITION_CUE/EXAMPLE_OF; misconception roles MISCONCEPTION_TRIGGER/ADDRESSES/REMEDIATES). |
| MCR-9 | Timestamp-grounded Q&A gating | A learner may only ask "what does this part mean?" against a transcript segment where `video_transcript.status='APPROVED'` AND `video_transcript_segment.review_status='APPROVED'`; resolved via `start_ms <= :time_ms < end_ms`. Until approved, the state's effective `student_questioning_enabled` is false and the tutor must never substitute authored notes for what the speaker actually said. |
| MCR-10 | Approved Q&A context | `pedagogy.state_qa_context`: `context_type` (EXPLANATION/DEFINITION/FAQ/DERIVATION/EXAMPLE/COUNTEREXAMPLE/NOTATION/MISCONCEPTION_RESPONSE), `approved_content`, optional concept/technique/skill/misconception FK, `review_status`. The model may rephrase `approved_content` but never invent new canonical curriculum facts. |
| MCR-11 | Deterministic transitions | `pedagogy.micro_course_transition`: `transition_type` (NEXT/CORRECT/INCORRECT/RETRY/MISCONCEPTION/PREREQUISITE_GAP/USER_CONTINUE/USER_BACK/USER_QUESTION_RESOLVED/INTERVENTION_COMPLETE), `condition_type` (ALWAYS/LEARNING_ITEM_RESULT/ACTIVITY_RESULT/MISCONCEPTION_CODE/SKILL_STATUS/INTERVENTION_RESULT) + `condition_payload jsonb`. Authored at design time; the runtime agent never returns an arbitrary next state. |
| MCR-12 | Fixed misconception interventions | `pedagogy.intervention_script` (targets a misconception/skill/technique, has an `entry_state_id`) and `pedagogy.intervention_step` (ordinal `ASK`/`EXPLAIN`/`SHOW_ASSET`/`LEARNING_ITEM`/`ACTIVITY`/`WAIT_FOR_RESPONSE`/`RETURN`). On `RETURN`, the runtime restores the exact originating `state_id`, `video_asset_id` and `video_time_ms` — never auto-advances. The agent cannot add a step. |
| MCR-13 | Append-only review history | `pedagogy.micro_course_review` (`status` APPROVED/NEEDS_REVISION/REJECTED) is insert-only; history is never overwritten. |
| MCR-14 | Learner enrollment and runtime pointer | `learner.micro_course_enrollment` pins an exact `release_id` for the life of the enrollment — a later release never changes an active enrollment. `learner.micro_course_state_event` is append-only. `tutor.micro_course_runtime` (`current_state_id`, `current_video_asset_id`, `current_video_time_ms`, `active_intervention_id`, `state_version`) is a **separate** pointer table and must not overload the existing step-solving `tutor.runtime_state`. |
| MCR-15 | Bounded runtime agent envelope | The agent receives only: course/state identity+objective, the resolved approved video segment, approved Q&A context, allowed concept/technique/skill/misconception IDs, allowed intervention IDs, and an explicit policy flags object (`may_rephrase`, `may_explain_current_content`, `may_create_quiz:false`, `may_search_web:false`, `may_recommend_media:false`, `may_generate_diagram:false`, `may_add_course_state:false`). Output is a typed contract (`answer`, `grounding_ids`, `suspected_misconception_id`, `requested_action` ∈ {NONE, START_INTERVENTION, REPEAT_SEGMENT, SEEK_TO_MARKER, RETURN_TO_STATE, ESCALATE_UNSUPPORTED}, `confidence`); the server validates every referenced ID before acting. Unsupported questions return `OUT_OF_APPROVED_SCOPE`, never a fabricated answer. |
| MCR-16 | Publication transaction | Inside one Postgres transaction: lock release → validate → require an APPROVED review → supersede the prior PUBLISHED release → mark PUBLISHED → set `published_at` → insert a `pipeline.outbox_event` (`MICRO_COURSE_PUBLISHED`). Neo4j projection happens later/asynchronously, never inside this transaction. |
| MCR-17 | Publication validator | Publish MUST fail on: no PRIMARY target; unresolved required canonical mapping; no states; duplicate ordinals; no entry state; a required state unreachable; no terminal path; an unbounded required cycle; invalid cross-release edge; a required video/transcript/segment not approved; a required `visual.asset` not VALID; an invalid required quiz/activity; an intervention lacking a RETURN/resume path; a misconception branch referencing an unapproved misconception; or an `agent_policy` that allows a forbidden dynamic-generation capability. |
| MCR-18 | Neo4j projection (additive, scoped) | New labels `MicroCourse, MicroCourseRelease, CourseModule, CourseState, TeachingAsset, VideoAsset, VideoSegment, Misconception, Intervention` (canonical_id = the Postgres UUID; `projection_kind="micro_course"`). Edges include `MicroCourse-[:TARGETS]->Concept/Technique/Skill`, `-[:HAS_RELEASE]->`, `-[:HAS_MODULE]->`/`-[:HAS_STATE]->`, `CourseState-[:NEXT\|BRANCHES_TO]->CourseState`, `-[:TEACHES\|REQUIRES]->Concept/Technique`, `-[:REQUIRES\|ASSESSES]->Skill`, `-[:ADDRESSES\|WATCHES_FOR]->Misconception`, `-[:USES_ASSET]->TeachingAsset`, `VideoAsset-[:HAS_SEGMENT]->VideoSegment-[:EXPLAINS]->Concept/Technique`, `-[:REQUIRES]->Skill`, `-[:MENTIONS_MISCONCEPTION]->Misconception`, `CourseState-[:USES_LEARNING_ITEM]->LearningItem`, `Intervention-[:REMEDIATES]->Misconception`, `CourseState-[:CAN_TRIGGER]->Intervention`. Only `PUBLISHED` release content, with approved video/transcript/segments/misconceptions/bindings, is projected — DRAFT never reaches the learner graph. Never projected: transcript body text, Q&A body text, correct answers, learner responses/mastery, private storage keys. |
| MCR-19 | Idempotent, non-destructive projector | `mathbank-graph/etl/project_micro_courses.py`: query PUBLISHED releases → create a `pipeline.graph_projection` row → MERGE micro-course nodes → MERGE edges to existing canonical Concept/Technique/Skill by `canonical_id` (fail if a required canonical node is missing) → prune only `projection_kind='micro_course'`-owned stale nodes/edges → complete the row → run parity verification. Never `MATCH (n) DETACH DELETE n` on the shared graph; never delete unrelated content. |
| MCR-20 | Graph verify/diff | A verify step fails on: a DRAFT release appearing; a rejected/stale video appearing; a missing canonical target; a duplicate canonical ID; an unexpected cross-release edge; or a stale micro-course node remaining. `micro-courses graph diff <release-id>` reports missing/stale nodes and edges. |
| MCR-21 | Admin/CLI parity | `micro-courses {list,show,releases,create,release create,state add,state bind-concept/technique,video add/metadata/transcript-import,segment list/split/merge/bind-concept/technique/misconception,state attach-learning-item,validate,review,publish,graph request/status/project/verify/diff,graph rebuild --all-published}`. UI and CLI must share the same service layer. |
| MCR-22 | Acceptance fixture | `MC-GEO-POWER-POINT` ("Power of a Point"): 1 existing Technique target, 1 existing Concept target, prerequisite Skills, 1 approved Misconception, 1 mocked YouTube video (no live provider call in CI), 4 approved transcript segments with semantic annotations, ≥5 states, a recognition quiz, a misconception diagnostic, a fixed two-question intervention, a summary state, deterministic transitions. Full flow: create → map canonical targets → add states → add mock video → import transcript → annotate segments → attach quiz → create intervention → validate → approve → publish → projection request → Neo4j project → verify → enroll learner → pause video mid-segment → ask question → fixed intervention → resume at the exact `video_time_ms` → complete course. |
| MCR-23 | Hard prohibitions | Never: replace `authoring.presentation_plan`; create a second Concept/Technique/Skill/quiz taxonomy; duplicate generic binary storage; put transcript bodies, correct answers, or learner mastery in Neo4j; synchronize Neo4j inside a Postgres transaction; auto-publish AI-authored content; let the runtime search YouTube, pick arbitrary web resources, generate a quiz/slide/image/diagram, invent an intervention, or add a course state; create canonical nodes from arbitrary strings; edit old migration files; mutate PUBLISHED release content; wipe the shared Neo4j graph during rebuild. |
| MCR-24 | Approved interaction-template binding | `pedagogy.micro_course_state_interaction` binds an ordered state slot to a statically configured `visual.interaction_instance`; attachment and publication require `review_status='APPROVED'` and the exact `visual.interaction_template_version.status='PUBLISHED'`. The release content hash includes course identity/metadata, binding order, instance configuration, exact template version and asset metadata. Bindings, course identity, attached asset identity and bound interaction configuration are immutable after publication. Public lesson JSON includes only approved instances and published template versions; the web renderer dispatches by the published template key and never evaluates admin-authored expression strings as code. |

## Open design items to resolve before migration authoring

- Four `video_segment_*` and four `micro_course_state_*` binding tables, plus
  `pedagogy.video_timeline_marker`, are specified in the source as prose/pseudo-DDL
  rather than literal `CREATE TABLE` SQL; exact column types (`uuid`/`text`/
  `smallint`/`numeric(p,s)` for importance/confidence) must be fixed at
  migration-authoring time, consistent with sibling tables already in this doc.
- The source migration skeleton's "27 items" is a work-breakdown, not a literal
  table count; the actual distinct new-table count is **29** (see MCR-1 through
  MCR-14 above), plus one `ALTER TABLE visual.asset` and one
  `pipeline.projection_request` CHECK-vocabulary extension.
- Migration numbering is explicitly provisional in the source ("do not assume
  027 is still free") — the implementer must re-check
  `mathbank-db/sql/` for the current highest migration immediately before
  authoring, not trust any number written here.
- The narrative design log's `student_questioning_enabled`,
  `CURATED_TRANSCRIPT_PENDING_IMPORT`, and `Ask_At_Timestamp` terms do not
  appear as literal columns/enums in the formal contract; MCR-9 implements the
  same effective gate procedurally via `transcript_status`/`review_status`
  filters, which this doc treats as authoritative over the narrative's naming.
- The narrative log's proposed `misconception_evidence_rule` /
  `learner.misconception_evidence` evidence-accumulation machinery is **not**
  part of this pack's 27-item skeleton; it is implemented instead by the
  sibling interaction-template-library pack
  ([41_INTERACTION_TEMPLATE_LIBRARY.md](41_INTERACTION_TEMPLATE_LIBRARY.md)),
  which this doc's MCR-5 `WATCH_FOR`/`ADDRESSES` state-level bindings remain
  the simpler, video/state-scoped baseline for.

## Implementation status

Migration 032 and the schema inventory are present. The previous session
reported that the migration was applied live and verified by publishing a
release and confirming a later child insert was rejected. This session adds
the initial shared PostgreSQL service layer for course/target/release/module/
state/binding/transition authoring, graph validation, review, deterministic
content hashing and transactional publication outbox events. Authenticated
admin REST and same-origin admin web authoring expose course creation, draft
release/state/semantic mapping/transition authoring, validation, approval and
publication. A student-facing catalog and published-course reader expose only
published releases and approved learning content.

Migration 034 adds object metadata, approved template-instance bindings and
immutability guards; it was applied transactionally after confirming the 032/033
tables were present. The live rollback-only service test covers course metadata,
private asset attachment/serving metadata, release publication and rejects
post-publication asset/course identity edits. Admin UI can attach an already
approved interaction or upload an allowlisted private asset to a draft state.
The published student reader exposes only approved instances with PUBLISHED
template versions and serves attached private bytes through a hash/size-checked
course-scoped REST endpoint. Its web renderer provides declarative Markov
state-graph/recurrence/matrix, Vieta roots/coefficient and Jensen x² curve/chord
explorers; the graph and plot use accessible SVG and do not execute stored
expressions.

`mathbank-rest/scripts/seed_reference_courses.py` seeds three real, published
courses — `MC-MARKOV-STREAKS`, `MC-VIETA-FORMULAS`, `MC-JENSEN-INEQUALITY` —
through this exact service layer (create/release/state/attach/validate/review/
publish), replacing the Playwright-only `MC-REFERENCE` fixture. It also
authors real (non-placeholder) JSON Schemas and an accessibility policy for
the five interaction-template versions these courses use and publishes them
through `interaction_validators.validate_interaction_template_version`, the
same validator the REST/CLI publish path uses. The script is idempotent:
already-published courses/instances/template versions are left untouched
(and are immutable by the 033/034 triggers regardless). `/learn/courses`
lists all three; each links to a live lesson exercising the real renderer,
not a mock.

`mathbank-rest/scripts/seed_reference_course_extras.py` then creates a
version-2 DRAFT release per course (parent-linked to v1), carries the
existing approved interaction forward, and adds a curated YouTube video state
(embedded, not just linked — see [42](42_MICRO_COURSE_STUDENT_NAVIGATION.md)
§3.3) plus PRE/INTERMEDIATE/POST quiz states sourced from the
`INTERACTION_TEMPLATE_LIBRARY_COPILOT/reference_zips/*_microcourse_v1`
packages, as `activity.definition` rows (`source_type='INSTRUCTOR_CREATED'`,
`persistence_mode='STATIC'`) — not `pedagogy.learning_item`, which is keyed
to the textbook/corpus transformation pipeline and not meant for freeform
quiz authoring. The video/quiz states are `required=False`/`skippable=True`,
so publication never requires the approved-timestamped-transcript workflow
these source packages explicitly mark `PENDING_IMPORT`.

The enrollment runtime (`start_enrollment`/`get_enrollment_runtime`/
`advance_enrollment`/`submit_activity_response`) is now wired to REST
(`POST /{code}/enroll`, `GET/POST /enrollments/{id}`, `.../advance`,
`.../activity-responses`) and to the student web reader: a logged-in student
can press "Start lesson," is pinned to a single `IN_PROGRESS` enrollment with
real server-tracked position, and every quiz attempt is persisted
(`learner.micro_course_state_event`, `event_type='ACTIVITY_RESPONSE'`),
independent of which step is current. A pre-existing bug in
`get_enrollment_runtime` (an `AmbiguousColumn` SQL error from a `USING`-join
chain, never previously exercised by any REST endpoint or test) was fixed
alongside this wiring. See
[42_MICRO_COURSE_STUDENT_NAVIGATION.md](42_MICRO_COURSE_STUDENT_NAVIGATION.md)
for the full JSON contract and stepper state machine.

Remaining requirements include YouTube transcript import/annotation,
timestamp-grounded student Q&A, grading `required` `learning_item`s inline
through the enrolled reader, asynchronous Neo4j projector/rebuild/verifier,
CLI parity, Web/Manim SceneSpec renderers, and the full
`MC-GEO-POWER-POINT` acceptance flow. Do not claim graph parity or
timestamp-grounded video Q&A completion.

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
