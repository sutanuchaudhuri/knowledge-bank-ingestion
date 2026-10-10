# 39. Precompiled tutoring routes and instructional reasoning graph

## Comprehensive-system integration contract

> **Normative precedence.** This section defines how precompiled tutoring routes participate
> in the complete MathBank platform. Historical implementation/status notes later in this
> file remain evidence of what happened at a point in time. If a historical note conflicts
> with the target architecture here, this section controls future implementation.

### 39.A Role in the complete system

Precompiled tutoring routes are the **problem-solving execution layer**. They own reviewed,
solution-specific reasoning programs: route releases, atomic steps, claims, requirements,
hints, theory links, misconceptions, diagnostics and route-local teaching assets.

They are not:
- a second micro-course engine;
- a second interaction runtime;
- a learner mastery graph;
- a replacement for canonical Concept/Technique/Skill nodes.

```text
Source Problem + Stored Solution
            |
            v
     Offline Route Compiler
            |
            v
 Immutable RouteRelease
   |      |       |
   |      |       +--> reviewed hints / theory / claims / diagnostics
   |      +----------> approved InteractionInstance / SceneSpec bindings
   +-----------------> canonical Concept / Technique / Skill requirements
            |
            v
      learner.route_attempt
            |
            +--> current route step
            +--> current approved hint level
            +--> semantic interaction events
            +--> deterministic diagnostic evidence
```

### 39.B Explicit micro-course → tutoring-route bridge

A micro-course `PRACTICE`, `EXAMPLE`, `CHECKPOINT`, or `TRANSFER` state may bind a specific
published tutoring-route release.

Add an FK-backed binding table following repository naming conventions, for example:

```text
pedagogy.micro_course_state_route
---------------------------------
state_route_id
state_id
route_release_id
ordinal
role                PRIMARY_PRACTICE | WORKED_EXAMPLE | TRANSFER | OPTIONAL
required
completion_policy   EXPLAINED | ANSWERED | ASSESSED | OPTIONAL
created_at
```

**Important:** implementation must inspect the actual tutoring-route migration and bind to
the real route-release PK/table name; do not guess it from this document.

Rules:
1. publishable course states may bind only `PUBLISHED` route releases;
2. retirement blocks new route starts, not already-pinned attempts;
3. route content is never copied into course tables;
4. route attempt and course enrollment pin independent immutable releases;
5. course progression resumes only through an authored course transition after route return.

Graph:

```text
CourseState -[:USES_TUTORING_ROUTE]-> RouteRelease
RouteRelease -[:FOR_PROBLEM]-> Problem
```

No hint/explanation/answer body enters Neo4j.

### 39.C Route step ↔ interaction/animation bridge

A route step may bind an approved reusable interaction and/or SceneSpec:

```text
route_step_interaction
----------------------
route_step_id
interaction_instance_id
ordinal
role       EXPLAIN | EXPLORE | DIAGNOSE | REMEDIATE
required
```

Requirements:
- exact interaction-template version is `PUBLISHED`;
- instance is `APPROVED`;
- SceneSpec is approved;
- IDs/versions participate in route content hash;
- bindings freeze with publication;
- learner events use the same interaction runtime as micro-courses;
- route compiler may propose a binding but cannot create/publish arbitrary controls,
  icons, templates, evidence rules or animations at runtime.

Graph:

```text
RouteStep -[:USES_INTERACTION]-> InteractionInstance
RouteStep -[:USES_SCENE]-> SceneSpec
InteractionInstance -[:CAN_REVEAL]-> Misconception
SceneSpec -[:EXPLAINS]-> Concept|Technique
```

### 39.D One deterministic misconception/evidence model

Canonical misconception:
`knowledge.misconception`

Private learner evidence:
PostgreSQL only.

Evidence can come from:
- route diagnostic answers;
- route interaction events;
- course activities;
- course interaction events;
- transfer checks.

Allowed shared graph:

```text
RouteStep -[:CAN_TRIGGER]-> Misconception
InteractionInstance -[:CAN_REVEAL]-> Misconception
Misconception -[:DIAGNOSED_BY]-> LearningItem
Misconception -[:REMEDIATED_BY]-> Intervention
```

Forbidden shared graph:

```text
Student -[:HAS_MISCONCEPTION]-> Misconception
Student -[:FAILED]-> Skill
```

### 39.E Runtime policy

Published authored structure first; LLM interpretation second.

The route tutor may:
- interpret free-form learner work;
- classify among predeclared misconception candidates;
- rephrase approved hints/instructions/theory;
- answer unexpected questions grounded in the current approved route/course context.

It may not:
- mutate the route DAG;
- invent a canonical prerequisite;
- create a new interaction/animation;
- mark mastery because a hint was displayed;
- jump to an arbitrary course state;
- expose future route hints/expected responses.

### 39.F Nested runtime and exact return

When route practice is launched from a course:

```text
CourseState
   |
   | Start problem
   v
RouteAttempt (pinned release)
   |
   +--> RouteStep 1
   +--> RouteStep 2
   +--> ...
   |
   v
Route Completed / Return
   |
   v
same CourseState
   |
   v
authored NEXT / CORRECT / RETRY / TRANSFER transition
```

Persist:
- origin course enrollment ID;
- origin course state ID;
- optional origin video time;
- route attempt ID;
- return policy.

The route cannot choose the next course state.

### 39.G Route tutor screen wireframe

Desktop:

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Course: Markov Chains        Step 5 of 8      Practice problem        [?]   │
├───────────────────┬──────────────────────────────────────┬───────────────────┤
│ COURSE STEPPER    │ PROBLEM / WORK AREA                  │ TUTOR CONTEXT     │
│ ✓ Intro           │                                      │ Goal              │
│ ✓ Video           │  Problem statement                   │ ───────────────   │
│ ✓ Explorer        │  ┌───────────────────────────────┐   │ Current concept   │
│ ● Practice        │  │ diagram / formula / scratch   │   │ Technique         │
│ ○ Transfer        │  │ interaction widget            │   │ Misconceptions    │
│                   │  └───────────────────────────────┘   │ allowed here      │
│                   │                                      │                   │
│                   │  Your response: [______________]     │ [Hint 1] [Ask]    │
│                   │  [Check] [Show approved explorer]    │                   │
├───────────────────┴──────────────────────────────────────┴───────────────────┤
│ Route: Approach A · Step 2/4     [Return to course]      [Continue if valid]│
└──────────────────────────────────────────────────────────────────────────────┘
```

Phone:

```text
┌─────────────────────────────┐
│ ‹ Course     Practice 2/4   │
│ Markov absorbing walk       │
├─────────────────────────────┤
│ Problem statement           │
│                             │
│ [diagram / interaction]     │
│                             │
│ Your response               │
│ [_______________________]   │
│ [Check]                     │
├─────────────────────────────┤
│ Tutor                       │
│ Goal: ...                   │
│ [Hint] [Ask]                │
├─────────────────────────────┤
│ [Return]          [Continue]│
└─────────────────────────────┘
```

Rules:
- future route steps/expected answers are not prefetched into learner JSON;
- current hint/interaction only;
- course stepper position is preserved while route subflow is active;
- route completion does not imply course mastery unless authored assessment says so.

### 39.H Search, graph, outbox and publication

At route publication:
- canonical Postgres transaction succeeds first;
- outbox event records publication;
- structural route graph refresh happens asynchronously;
- route search representations/embeddings happen asynchronously;
- each derived subsystem records independent status.

Recommended search entity kinds:

```text
TUTORING_ROUTE_RELEASE
TUTORING_ROUTE_STEP
THEORY_ITEM
CLAIM
```

Do not embed hidden answer keys or private learner evidence.

### 39.I Comprehensive route acceptance test

Must pass:

```text
publish route
→ attach to draft course state
→ publish course
→ graph projection
→ enroll learner
→ enter practice state
→ create pinned route attempt
→ request H1
→ manipulate approved route-step interaction
→ emit deterministic error signature
→ evidence update
→ diagnostic/remediation if threshold crossed
→ complete route
→ return to exact course state
→ authored course transition
→ verify structural graph only
→ verify learner evidence only in PostgreSQL
```


## Decision and rollout

Requested 2026-10-08 UTC from the attached 1,005-line architecture proposal.
The proposal is requirements input, not evidence of implemented tables.
PostgreSQL owns canonical mathematical and teaching content; Neo4j owns a
rebuildable metadata-only projection. Expensive decomposition belongs offline,
not in ordinary hints. The initial ingestion was **20 solutions**;
the user subsequently approved **all 18,749 stored solutions** and bulk approval
of existing/new generated routes after structural and source checks.
Generated material initially enters DRAFT; generation,
structural validation and source retrieval never constitute expert review.
Existing textbook steps, human edits and learner attempts must survive.

## Complete requirement inventory

| ID | Requirement | Acceptance |
|---|---|---|
| PCR-1 | Solution-owned step identity | Multiple routes may each start at ordinal 1; no mixing solutions by problem ordinal. |
| PCR-2 | Immutable versioned route releases | Solution/problem identity, content hash, source hash, approach, difficulty/conceptual/algebraic/insight loads, preferred flag, quality, generator/reviewer/time provenance; DRAFT → REVIEWED → PUBLISHED → RETIRED. Published content cannot change. |
| PCR-3 | Attempt pinning | Learner attempt/session pins release ID; improving authoring never swaps its DAG. Retirement blocks new selections, not continuation of pinned attempts. |
| PCR-4 | Separate step instruction | Goal, recognition cue, reasoning, why, prerequisite recap, previous/next connections, common errors, student prompt, expected response, short/full explanations, version/hash/review. |
| PCR-5 | Explicit step prerequisites | Exactly one canonical Concept/Subconcept/Skill/Technique/Theory target, REQUIRED/HELPFUL/RECOGNITION/EXECUTION/JUSTIFICATION role, level, importance, blocking, source/confidence/review. USED and REQUIRED are distinct. |
| PCR-6 | Canonical misconceptions | Stable code, symptom, why wrong, correct model, severity/level, recognition patterns, source/review; step likelihood/evidence/correction links. Learner-specific hypotheses remain private. |
| PCR-7 | Canonical theory library | Definitions/theorems/lemmas/properties/technique explanations/intuition/microexamples, summary/full text/LaTeX, cues/examples/counterexamples, difficulty/version/hash/review. |
| PCR-8 | Purpose-tagged learning items | Prerequisite checks, misconception diagnostics, technique recognition, isolated execution, guided practice, transfer, mastery checks; technique/misconception/theory links. Keep existing LearningItem contracts. |
| PCR-9 | Published hint library | H1 orientation, H2 recognition, H3 setup, H4 near-complete, H5 current-step reveal; release/step/level/variant/misconception/content hash identity. Goal ≥95% approved stored hints; dynamic fallback <5%, measured not assumed. |
| PCR-10 | Claims/subgoals | Problem-local canonical mathematical claims; step PRODUCES/USES_CLAIM; alternative routes may reach the same reviewed claim. No unsafe method switch based on name similarity. |
| PCR-11 | Tutoring graph | Release/step/claim/misconception/theory metadata; REQUIRES, PRODUCES, USES_CLAIM, CAN_TRIGGER, REMEDIATED_BY, DIAGNOSED_BY, EXPLAINS, PRACTICES, TESTS_MISCONCEPTION, ALTERNATIVE_FOR, USES_APPROACH. |
| PCR-12 | Technique graph | Technique PREREQUISITE_OF Technique and BUILDS_ON Concept; canonical recognition cues and anti-cues, confused-with/error graph. |
| PCR-13 | No private/shared graph conflation | No learner answers/mastery, raw solution text, explanation prose, hint text or answer keys in Neo4j. PostgreSQL joins learner evidence at runtime. |
| PCR-14 | Deterministic diagnosis/recovery | Compare reviewed requirements with learner evidence; select stored probe/recap/hint. Never fabricate mastery or diagnoses from inactivity. |
| PCR-15 | Route personalization/transfer | Rank published approaches by techniques, prerequisite depth, loads, steps, novelty, visual/proof dependence and private learner profile. Optional SkillProfile is selection metadata, not a learner graph. |
| PCR-16 | Offline compiler and validation | Problem+solution → atomic steps → semantic annotations → assets → source/order/cycle/ID/prerequisite/leakage checks → review → publish → graph → embeddings. |
| PCR-17 | Runtime roles | LLM interprets free-form work, selects/rephrases approved assets and handles unexpected follow-ups; does not normally invent decomposition, prerequisite facts or core hints. |
| PCR-18 | Published-first REST and agent | guidance-plan and coach resolve reviewed published releases first. Dynamic planning is explicitly identified fallback, never represented as published material. |
| PCR-19 | Web/admin access | Graph relationship views and correct labels/directions; private admin full draft inspection/review; student receives current-step assets only. |
| PCR-20 | Resumable operational ingestion | Existing source rows selected deterministically; per-solution jobs/source hashes, bounded concurrency/cost, errors surfaced, retries explicit, report persisted; no replacement of human work. |
| PCR-21 | Synchronization evidence | Separate SQL generation, publication, graph projection and embeddings statuses; live counts and failures reported. A queued refresh is not proof of parity. |

## Compatibility design

The original `pedagogy.solution_step` is tightly coupled to textbook book/package
identities and mutable imported content. New generic releases use independent
`pedagogy.route_step` snapshot IDs and release-local ordinals rather than inventing
a textbook/package for every contest solution. Legacy textbook runtime remains
compatible. The legacy problem-ordinal uniqueness is retained until all its readers
are solution-scoped; lifting it prematurely would mix routes in the old runtime.
This is a deliberate compatibility boundary, not completion of legacy migration.

New immutable assets belong to release snapshots. Theory/misconception/claim
references are reviewed as part of the release; a draft never silently promotes
an existing canonical object. Published-first Tutor sessions pin the release and
step index in ADK state; they do not claim graded mastery. Existing authenticated
SQL solve attempts remain on their original runtime until an explicit migration.

## Initial implementation and operations

This section must record actual migration, pilot, review and graph outcomes.
No generated pilot release may be published without explicit review.
Full-corpus compilation is now authorized and running; generalized legacy-attempt migration, automatic
misconception grading, embeddings and learner-personalized route switching
require separate acceptance; the inventory above keeps them visible.

## Implemented lifecycle and access

Source revision `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7` plus the route
compiler/runtime/projector, REST, ADK and web worktree changes. PostgreSQL schema
metadata was freshly observed **2026-10-08 01:57:54 UTC** on the user-approved
REST-configured Neon target: 21 non-system schemas, 143 tables, 4 views, 1,403
columns and 170 routine signatures. All 129 project-declared tables and their
column-name sets are present; the other 14 tables are ADK/provider-owned.
See [exact per-table catalog](reference/postgres/README.md).

The additive migration is
[026_tutoring_routes.sql](../mathbank-db/sql/026_tutoring_routes.sql), distinct
from the packaged REST geometry migration also numbered 026. Existing 18,749
solutions and 7,814 legacy textbook steps are preserved. Review status of a
teaching route does not alter `core.solution.verification_status`.

```mermaid
sequenceDiagram
    actor Operator
    participant Compiler
    participant SQL as PostgreSQL
    participant Model
    actor Reviewer
    participant Graph as Neo4j
    participant Tutor
    Operator->>Compiler: Approved full corpus and frozen bulk approval policy
    Compiler->>SQL: Freeze solution IDs and source hashes
    Compiler->>Model: Source excerpts, canonical IDs, typed asset keys
    Model-->>Compiler: Draft atomic program
    Compiler->>Compiler: Bind exact excerpts; validate IDs, DAG and H1-H4
    Compiler->>SQL: Atomic DRAFT snapshot and H5 current-step explanation
    opt Operator explicitly authorizes bulk approval
        Compiler->>SQL: Revalidate canonical source, taxonomy and semantic hash
        Compiler->>SQL: Mark REVIEWED with operator bulk approval identity
    end
    Reviewer->>SQL: Admin preview, edit draft, inspect mathematics
    Reviewer->>SQL: Hash-guarded review attestation
    Reviewer->>SQL: Separate publication
    Operator->>Graph: Refresh published metadata only
    Graph-->>SQL: Record reconciled projection outcome
    Tutor->>SQL: Published-first roadmap and owned release pin
    Tutor->>SQL: First idle expiry requests current H1
    SQL-->>Tutor: Stored simpler insight, same checkpoint
    Tutor->>SQL: Second expiry requests H5 and next checkpoint
    SQL-->>Tutor: Current explanation, next prompt, no mastery credit
```

### What is persisted, cached and displayed

| Surface | Source and persistence | Visibility |
|---|---|---|
| Compiler cohort/status | `pedagogy.route_compiler_run`, `route_compiler_job`; frozen before first paid call | Operator SQL/report, safe error classes and structural validation diagnostics |
| Mathematical move | `pedagogy.route_step`, release-owned index and exact bound source excerpt | Admin only; graph receives IDs/index/dependencies, never result text |
| Instruction | `solution_step_instruction`, all twelve fields plus hash/version | Admin full preview; learner receives current goal/prompt, not expected response |
| Hint/reveal | `route_step_hint`, durable immutable H1-H5 | Current step only through owned attempt; H5 reveals that step, not a future step |
| Requirements/assets | `solution_step_requirement`, `route_asset`, `route_asset_link` | Private teaching content in SQL; reviewed metadata-only graph |
| Learner progress | `learner.route_attempt`: student/release/current index/version/explained positions | JWT ownership; no learner responses or mastery stored by assistance |
| Agent route | ADK session safe release/attempt metadata; token stays invocation-temp | Student chat shows stored hints/questions, not compiler/review diagnostics |
| Browser clock | Active elapsed time and explicit pause are local UI state | Hidden/composing/recording/uploading pauses are preserved |
| Graph | Explicit rebuild from PUBLISHED releases, distinct `tutoring_routes` ownership | Public graph metadata views; zero draft assets |

The route hint library is persisted content, not a model-response cache.
Legacy `pedagogy.step_hint` caching remains a different mechanism.
Published guidance chooses preferred flag, quality, difficulty and release
version deterministically; this is not personalized mastery-based selection.
`coach` uses approved opening H1-H3 when a published route exists. Owned attempt
assistance and the signed-in Tutor use the pinned current step. Anonymous users
may read the opening roadmap but must sign in for durable checkpoint progression.
H5 advancement means tutor-explained, not successful assessment.

### REST examples and review UI

Use Swagger at `http://localhost:8000/docs`; the full registered source snapshot
is [openapi.json](reference/openapi.json). Authentication placeholders below are
illustrative; never store tokens in URLs.

```http
GET /v1/admin/tutoring-routes?limit=25&offset=0
X-Admin-Api-Key: <staff-key>

GET /v1/admin/tutoring-routes/<release-uuid>
X-Admin-Api-Key: <staff-key>
```

The preview includes the complete draft program, source statement/solution and
verification status. At `http://localhost:5173/admin/tutoring-routes`, staff can
inspect every instruction/hint/asset and edit the complete draft JSON. The
current release hash is required for edits; stale or non-DRAFT edits fail 409.
Review and publication are separate, explicit actions:

```http
POST /v1/admin/tutoring-routes/<release-uuid>/review
X-Admin-Api-Key: <staff-key>
Content-Type: application/json

{"reviewer":"Named reviewer","expected_hash":"<64-character-current-hash>","mathematical_review_confirmed":true}
```

```http
POST /v1/admin/tutoring-routes/<release-uuid>/publish
X-Admin-Api-Key: <staff-key>

POST /v1/admin/tutoring-routes/refresh-graph
X-Admin-Api-Key: <staff-key>
```

Publication does not imply graph freshness. The refresh records a separate
`pipeline.graph_projection` run and reconciles node/edge counts. Failed endpoint
identity lookup rolls back the graph replacement rather than silently omitting
edges. It never refreshes embeddings.

```http
POST /v1/tutor/route-attempts
Authorization: Bearer <learner-token>
Content-Type: application/json

{"problem_code":"PAPER_HMMT_2018_NOV_GUTS_Q08","route_release_id":"<published-release-uuid>"}
```

```http
POST /v1/tutor/route-attempts/<owned-attempt-uuid>/assist
Authorization: Bearer <learner-token>
Content-Type: application/json

{"expected_version":1,"hint_level":1,"advance":false}
```

After the first assistance, use the returned version:

```json
{"expected_version":2,"hint_level":5,"advance":true}
```

The response contains `route_attempt_id`, pinned `route_release_id`, `version`,
`current_step`, active/finished `status`, current `goal`/`student_prompt`, `hint`,
`hint_level`, `tutor_explained_steps`, `mastery_recorded:false` and
`source:"published-hint-library"`. Future expected answers/explanations are not
returned. Foreign attempts return 404; stale versions or invalid transitions
return 409; missing auth returns 401. Source/structural authoring validation
returns 422, unavailable SQL/graph returns 503.

`POST /v1/tutor/guidance-plan` now defaults `allow_dynamic_fallback:false`.
Source-gated authored AIME/HMMT openings remain compatible; other missing
published routes return explicit unavailable status unless the caller requests
`allow_dynamic_fallback:true`. No generated pilot draft is thereby published.

### Operational commands and cost limits

From `mathbank-rest/`, using its configured environment:

```bash
.venv/bin/python -m mathbank_rest.route_compiler inspect
.venv/bin/python -m mathbank_rest.route_compiler migrate
.venv/bin/python -m mathbank_rest.route_compiler compile --limit 20 --report <private-report-path>
.venv/bin/python -m mathbank_rest.route_compiler approve-drafts --approve-by <operator-approval-identity>
.venv/bin/python -m mathbank_rest.route_compiler compile --all --workers 4 --approve-by <operator-approval-identity> --report <private-report-path>
.venv/bin/python -m mathbank_rest.route_compiler status --resume-run <run-uuid>
.venv/bin/python -m mathbank_rest.route_compiler compile --resume-run <run-uuid> --report <private-report-path>
.venv/bin/python -m mathbank_rest.route_projection
```

Migration/session leases use the same approved database's direct endpoint; no
environment file is rewritten. A full-run lease prevents overlapping compiler
calls. Resume retries only frozen unfinished jobs and preserves the run's
`auto_review_by` approval policy, never selects twenty extra
sources. Source hashes include solution ID, statement, stored solution and
verification status. Changed source content is eligible for a new release;
existing human textbook steps are never updated.

Each solution has at most one structural repair call per compiler attempt.
The compiler calls **OpenAI `gpt-4o-mini`** through the existing REST-configured
client: this is paid offline generation, not deterministic paragraph splitting.
It asks for atomic moves, teaching instructions, progressive hints and
release-local semantic assets from the canonical stored solution. PostgreSQL
persists the validated output so published route hints do not need another
decomposition call. Future changes to the configured model must be treated as
compiler provenance/versioning changes, not assumed to produce identical output.
Generation failures remain explicit; they are not converted to empty programs
or approved releases. Jobs are durably QUEUED before workers mark them RUNNING.
Failed jobs store safe error classes/validation diagnostics in `error_details`;
full-cohort progress includes previously successful jobs when resumed. The
private JSON progress report is replaced atomically after each completed job.
Source content is rechecked under row locks before persistence/review. Empty,
damaged, refused or context-limit sources fail explicitly rather than disappearing
from selection. Short and long sources are no longer silently excluded or truncated.
Workers are bounded to 1-8 (this run uses 4); provider retries are disabled,
with at most one structural repair. Authentication, permission and insufficient
quota errors stop further scheduling. Other failures are persisted for explicit
resume; there is no unbounded automatic retry loop.
The initial pilot exposed reversed asset links, undeclared claim references and
inexact generated quotes. The compiler now constrains claim/misconception key
types and binds validated source excerpt indices to literal stored text rather
than asking the model to recreate quotations. A real HMMT acceptance produced
four structurally valid steps/four assets before the exact frozen cohort was
resumed. This is structural/source-grounding evidence, not mathematical review.

### Approved full-corpus run (2026-10-08 UTC)

- The completed pilot selected 20 source solution IDs: **17 DRAFT releases,
  3 FAILED jobs**. The three failures were rejected, not silently accepted.
- User explicitly authorized marking existing and newly compiled routes
  REVIEWED after validation. All **17 existing DRAFTs were validated and
  changed to REVIEWED**, with zero approval failures. `reviewed_by` is
  `operator-bulk-approval:2026-10-08`; this records the operator's authorization,
  **not independent expert mathematical certification**. Canonical solution
  verification flags remain unchanged.
- Full run **`1ece0009-8ab9-441f-a1b0-712d0a7c37cc`** started at
  **2026-10-08 02:26:28 UTC** on the explicitly approved existing REST-configured
  database. Its frozen cohort contains **18,732 remaining sources** plus the
  17 already reviewed releases, covering all 18,749 existing solution identities.
- Includes **671 sources shorter than 100 characters** and **32 longer than
  8,000 characters**, previously excluded. The longest is 72,495 characters;
  inclusion is not a guarantee of successful mathematical decomposition.
- The user explicitly authorized continuing independently after this session.
  It runs with four bounded workers, durable SQL jobs and a private incremental
  progress report. The full corpus is **in progress**, not certified complete.
- REVIEWED is **not PUBLISHED**. This approval does not publish to students,
  refresh graph metadata or create embeddings. New routes become available to
  published-first Tutor readers only after separate publication.
- Initial live progress check: **9 newly compiled REVIEWED releases, zero
  failures, 18,723 remaining**, in addition to 17 reviewed pilot releases
  (**26 total REVIEWED, zero DRAFT/PUBLISHED** at that observation). The three
  originally failed pilot solutions were successfully regenerated in the full
  run. These are dated initial observations, not final corpus totals.
- Status: `.venv/bin/python -m mathbank_rest.route_compiler status --resume-run 1ece0009-8ab9-441f-a1b0-712d0a7c37cc`.
  After interruption/failure, resume with the same UUID and `--workers 4`;
  the stored approval policy is inherited. Do not start a second overlapping run.
- New validation: **19 targeted unit/API tests passed**; **7 route lifecycle/API
  tests passed** with live rollback-only storage checks. Changed-source Ruff
  checks passed. Existing 7,814 textbook steps are untouched.
- Mermaid preview opened successfully; automated validator access required
  Mermaid sign-in, so tool-based syntax validation remains unavailable.

### Service activation and integrity follow-up

**Current policy: mandatory enrichment with an optional different-model
critic.** The atomic-only run below was stopped when the user clarified that
claims, misconceptions, theory and diagnostic quiz assets are mandatory.
Compiler `tutoring-route-compiler-v2-mandatory-enrichment` performs
decomposition and bounded per-step enrichment, then fenced atomic persistence;
mandatory enrichment is not proof certification. An independent critic model
is **optional**, toggled per machine/run via `make`'s `ROUTE_CRITIC`
(default off) and `ROUTE_CRITIC_MODEL` (default `llama3.2:3b`); when enabled
it scores seven criteria per step with up to two feedback-guided repairs and
requires PASS/all scores >=3/4/no issues, otherwise the generator model
(`qwen2.5:7b` by default) is accepted on its own. Review/publish no longer
require critic evals for any release. Every persisted step/job/run record
stores `generation_started_at` (UTC) and the generator model name;
`critic_model` is an explicit JSON `null` unless the critic was enabled for
that run (migration 029 documents this in column comments on the authorized
remote target). New enriched versions replace no historical reviewed
snapshots in place.

The [Make pipeline](../Makefile) supports multiple macOS/Linux machines against
the same configured PostgreSQL with migration
[028](../mathbank-db/sql/028_route_distributed_queue.sql), a unique work queue,
SKIP LOCKED claims, expiring renewable leases and ownership fencing. There is
no global run lock in this pipeline. Resources are calculated before inference
and logs are per machine on an operator-selected external drive.
See [README commands and limitations](../README.md#local-ollama-tutoring-ingestion-one-or-multiple-machines).
This is source-derived implementation evidence, not a claim that the replacement
full corpus has completed or that the running REST service has been reloaded.

Pipeline validation observed 2026-10-09 UTC: migration 028 applied to the
authorized remote target; **59 targeted tests passed**, including actual
two-connection claims, expired-lease recovery/stale-owner fencing and rollback
provenance/review tests (predating the critic becoming optional; all still
pass with the critic disabled). Missing `llama3.2:3b` installed successfully.
Actual default-model resource preflight rejected this busy Mac's 5.64 GiB
available RAM before inference. No new full run or paid fallback was started;
end-to-end live generator (optionally plus critic) acceptance still requires
a resource-qualified machine. The v2 queue is empty for operator launch. The
old atomic run is PARTIAL, 18,590 QUEUED/two interrupted jobs/no full-run
releases; backups are unchanged. `make routes-progress` reports a
generator/critic-model summary grouped by job status.

**Re-enabled single-OpenAI-model path (2026-10-09 UTC), then fixed its real
failure mode.** The user asked for a cost estimate, then explicitly asked to
re-enable the previously CLI-blocked `compile` command and run it. The
*original* single-shot schema (one `gpt-4o-mini` call producing decomposition
and all claim/misconception/theory/quiz assets together) failed **9 of the
first 13** real paid attempts with cross-reference errors (invalid asset
links, claims used before being produced, incomplete learning items) —
the same failure class seen earlier with Ollama's initial rich-asset attempt.
The run was stopped immediately at the user's request.

**Fix:** unified the OpenAI path onto the same proven architecture as Ollama.
`generate()` now requires an explicit provider (no more implicit "None means
OpenAI"); a new [`route_openai.py`](../mathbank-rest/src/mathbank_rest/route_openai.py)
`OpenAIChatProvider` implements the same `.complete()`/`.config()` interface
as `OllamaProvider`. Every provider now does atomic decomposition first, then
calls [`route_enrichment.enrich()`](../mathbank-rest/src/mathbank_rest/route_enrichment.py),
which constructs claim/misconception/theory/quiz asset keys and links
**deterministically in Python** rather than asking the model to get
cross-references right. A real 20-solution batch then succeeded **20/20**
(0 repairs), at $0.00243/solution (~$46 estimated for the full remaining
corpus), versus the single-shot path's 0% success rate. 59 tests still pass.

**Diagram requirement added before the full run.** Per explicit request, the
`Instruction` schema gained `has_diagram`, `diagram_description` (what the
figure depicts, to be stated before any explanation) and
`diagram_instructions` (concrete enough to render: labeled points/shapes/
angles/measurements/relative positions), with a validator requiring both
fields nonblank exactly when `has_diagram` is true, and blank otherwise.
Verified on a real diagram-bearing solution (`PAPER_HMMT_2016_FEB_GUTS_Q12`):
the model correctly described a rectangle's vertices/edges before any
explanation and left non-diagram steps blank.

**Full remaining-corpus run started**, authorized by the user: run
`4f163e6c-940d-41e1-b7d6-15e29c5056f0`, 18,728 solutions, 4 `gpt-4o-mini`
workers, DRAFT-only (no `--approve-by`). Every persisted step/job/run record
includes `generation_started_at` and the generator `model` name;
`critic_model` is an explicit JSON `null` (no critic was enabled for this
OpenAI run). Monitor with `--resume-run 4f163e6c-940d-41e1-b7d6-15e29c5056f0`
on the `status` command, or tail
`/Volumes/External/Developer/databases/logs/openai-mandatory-enrichment-routes/progress-full.json`.

**Raised the worker ceiling from 8 to 32** after measuring this account's
actual OpenAI rate limits via real response headers (30,000 requests/min,
150,000,000 tokens/min for `gpt-4o-mini`) — far above anything 8 workers
could reach; the prior cap was an arbitrary local sanity bound, not a rate
limit. The run was stopped cleanly (advisory lock verified released) and
resumed with the same frozen run/cohort at 16 workers.

**Taxonomy coverage gap found and the run stopped again.** With 159 real
persisted steps, **97% had zero taxonomy requirements** and only 10 of 500
available `pedagogy.taxonomy_node` rows had ever been used. Root cause: the
entire existing taxonomy (`GEO.*`, 245 concepts/subconcepts + 202 geometry
skills + 54 geometry techniques) covers geometry only, while the corpus is
mostly HMMT/SMT/AIME/CHMMC/CMM algebra, number theory and combinatorics with
zero matching taxonomy — the model was correctly leaving requirements empty
rather than inventing IDs, not malfunctioning. The run was stopped again
(135 DRAFT routes preserved) pending a decision on how to author the missing
domains; this is unresolved and the run has not resumed.

**Caching and end-of-run graph refresh added while taxonomy content is
decided.** A new `TaxonomyCache` (`route_compiler.py`) backs the canonical
shortlist with a 10-minute TTL instead of one query per job, so a long
multi-hour run can pick up newly authored taxonomy nodes without a restart;
existing plain-list callers (tests, direct `generate()` use) are unaffected
via duck typing. `compile_pilot` now calls
[`route_projection.project()`](../../mathbank-rest/src/mathbank_rest/route_projection.py)
when its invocation naturally exhausts its cohort (not on an external
process kill), recording the outcome in the run report. Projection reads
only **PUBLISHED** releases, so a DRAFT-only run legitimately reports zero
projected nodes/edges until routes are reviewed and published — this is
expected, not a bug. 61 tests pass, including live-cache TTL-refresh and
plain-list/cache duck-typing coverage.


**Historical atomic-only ingestion: local Ollama, remote PostgreSQL, started
2026-10-09 00:18:12 UTC.** User requested replacing paid generation with local
inference. The detailed requested plain-text plan is
[requirements.txt](../requirements.txt). New run
`3275ee2d-860a-47ee-ae30-2d36a6ccc119` freezes 18,592 remaining sources.
Existing 156 reviewed routes are retained; a successful local acceptance
added one four-step reviewed route. The OpenAI run stays stopped.

`qwen2.5:7b` Q4_K_M is the strongest installed selected model; two parallel
generation workers/eight inference threads operate on the 16 GiB M4 using an
isolated loopback server on port 11435. Model allocation observed 5.52 GB and
17-19% system memory free; arbitrary extra inference workers were not added.
Context/output budgets are 16,384/4,096. Source/repair input is conservatively
bounded by UTF-8 bytes plus chat overhead to prevent silent context truncation.
Oversized sources fail explicitly for a later larger-context strategy.

[Migration 027](../mathbank-db/sql/027_route_generation_provenance.sql) adds
frozen run `generation_config`, job `generation_metadata` and step
`generation_metadata`. Each new step stores provider/model/digest/runtime,
options, token/duration metrics, repair count, source/program hashes, validation
result, timestamp, ordinal and canonical taxonomy snapshot. Normalized technique/
skill/concept IDs and requirement roles remain in `solution_step_requirement`.
Existing unknown model provenance is not fabricated. Reviewed metadata is
immutable along with its step. Staff preview source exposes provenance separately
from mathematical program JSON; deployment requires the updated REST code.

Initial rich-asset local outputs were rejected. The historical local atomic profile
uses schema-enumerated canonical taxonomy IDs and emits steps/instructions/
hints/requirements, with claim/misconception/quiz/library assets left
empty. The user rejected that incomplete scope; assets are now mandatory.
This historical run was not complete rich-library
generation or proof certification. The shared structural/source validators and
operator-authorized review gates were not relaxed. Real acceptance persisted
four steps with verified Ollama provenance; 29 targeted tests passed, including
live rollback-only provenance persistence/immutability and no-paid-fallback tests.

All local server/ingestion logs and progress live under
`/Volumes/External/Developer/databases/logs/ollama-routes/`. Ollama transport
failure stops scheduling; it never calls OpenAI. This run is now stopped
and incomplete. Publication/graph/embeddings and local-backup refresh
remain separate operations. Older stop/resume entries below are historical.

**Previous paid-run state: STOPPED AGAIN at explicit user request, 2026-10-08
23:58:01 UTC.** The resumed compiler process was terminated and its absence
verified. The run is PARTIAL: 139 successful full-run releases plus 17 pilot
releases (**156 REVIEWED total**), 18,585 QUEUED sources and eight unsuccessful
jobs (four validation rejections, four interrupted calls). No automatic restart
or retry is scheduled; further paid ingestion requires fresh authorization.
The local backup remains the earlier 146-release snapshot, unchanged.

**Resumption authorized 2026-10-08 23:54 UTC:** after verifying the local
database/object-file backup, the user explicitly requested resuming paid
generation into remote PostgreSQL. Resume the same frozen run
`1ece0009-8ab9-441f-a1b0-712d0a7c37cc` with four workers and its unchanged
operator bulk-review policy. The starting state is 129 successful full-run
releases, 32 unsuccessful jobs and 18,571 queued sources (18,603 to attempt).
Previously successful releases are not regenerated. Local SQL and asset backups
remain point-in-time copies and are not updated by remote ingestion.
Student publication, graph refresh and embeddings remain separate.
The stop entry below documents the prior interruption, not a prohibition on
this newly authorized resumption.

**Previous interruption: STOPPED by user request at
2026-10-08 02:50:06 UTC** to avoid further token consumption. The independent
compiler process was terminated and its absence verified; no automatic restart
or retry is scheduled. Run `1ece0009-8ab9-441f-a1b0-712d0a7c37cc` is persisted
as PARTIAL. It produced **129 REVIEWED releases**, plus the 17 pilot releases
(**146 REVIEWED total**). There are **18,571 untouched QUEUED sources** and
**32 unsuccessful jobs**: 27 validation rejections, one provider timeout and
four interrupted in-flight jobs. Completed routes remain intact and unpublished.
Already submitted provider requests may still incur charges; termination
prevents this worker from scheduling any further calls. Resumption requires
new explicit user authorization. Earlier RUNNING observations below are history.

After explicit user approval, REST and Tutor-agent services were restarted
using their verified owned process IDs and existing startup targets. REST now
exposes all nine route-admin/owned-attempt paths: **218 mounted OpenAPI paths**.
The running OpenAPI and checked-in snapshot are identical after sorted JSON
normalization (SHA-256
`f03202c00801f3d5dab2d82439da7284a21446f213015a45e56ca9801760e621`).
The admin route rejects unauthenticated requests with 401; the web teaching
routes page redirects anonymous viewers to admin login. Authenticated admin
page interaction remains unverified, rather than bypassing that login.
The agent responds at `/list-apps` with `mathbank_tutor`.

A subsequent read-only integrity pass revalidated **49 stored releases**:
typed instructions/assets, dependency order, taxonomy identities, literal
source evidence, current source hashes and SQL-round-trip content hashes.
At that observation the database held **189 new route steps and 945 H1-H5
hint rows**; **7,814 legacy textbook steps remained unchanged**.
These counts increase as the independently running compiler progresses.

The next persisted run observation had **33 new REVIEWED releases, 3 failed
jobs and 18,696 remaining sources**. Failures were two learning-item outputs
missing required question/answer/purpose and one incompatible asset link.
They were rejected after bounded generation/repair, not approved. The corpus
continues processing; retry those frozen failed IDs through the same run after
the current process stops, rather than creating a competing ingestion.

Live graph refresh **`14624a9d-d4e1-4ffa-9805-e724820ba725`** completed and
reconciled **0 published releases, 0 nodes and 0 edges** for this owned route
layer. This is expected: operator bulk REVIEWED approval does not constitute
student publication. No DRAFT/REVIEWED-only assets were leaked into the graph.
This observation does not certify populated-route endpoint/edge parity;
that requires separate publication and another refresh. Existing corpus graph
content is outside this projector's ownership.

### Verified implementation and remaining scope

- 57 targeted REST tests passed, including four live rollback-only checks of
  review/publication, immutable child rows/reparenting, draft edits/hash guards,
  owned current-step assistance, retirement pinning and graph prose exclusion.
- 26 agent tests passed, including actual ADK callbacks and stored-route timed
  assistance; 10 focused web tests and the production build passed.
- Generic released-route identity, review UI, owned hints, metadata graph
  projector and published-first readers are implemented. Actual pilot/graph
  counts are recorded separately below after reconciliation.
- Shared canonical misconception/theory/claim catalogs, equivalent-claim
  alternative-route switching, reviewed technique prerequisite authoring,
  learner-specific diagnosis/selection, graded route answers, embedding
  publication and legacy attempt migration remain pending.
- The >=95% stored-hint target is an unmeasured production acceptance goal.
  DRAFT-only pilot content cannot establish it or appear in the student graph.
- Source/widget/video attachments and a visual split/merge editor remain the
  separate requirement36 completion work; draft JSON supports coherent edits
  and reordering with complete DAG validation, not arbitrary runtime patching.

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
