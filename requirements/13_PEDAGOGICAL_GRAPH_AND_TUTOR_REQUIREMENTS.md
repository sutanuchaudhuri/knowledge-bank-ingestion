# Pedagogical Graph and Anonymous Tutor

## Goal and scope

### Automatic-approval policy (2026-10-04 update)

The operator authorized automatic approval of existing PENDING metadata and
future machine-generated enrichment. Usable assertions retain the compatible
`REVIEWED` status, but `approval_method=automatic` explicitly distinguishes
them from human review. The UI must show automatic approval, confidence and
provenance; never imply measured mastery or calibrated difficulty.

Migration 008 promotes PENDING corpus tags, concept relations and teaching
metadata with immutable automatic-approval snapshots. Database triggers apply
the policy to future writes, including batch classification. Human corrections
and REJECTED records remain protected from automatic updates.

Learning-context requests automatically enrich missing skills, prerequisite
links and seven difficulty dimensions using validated structured model output.
Prerequisite cycles and unknown taxonomy references are rejected before writes.
Invalid generated JSON receives bounded correction feedback (at most three
model responses per attempt), including conflicts detected during the locked
atomic import against existing prerequisites. Catalog selections use structured
output enums; exhausted attempts retain the detailed validation cause.
Model/database errors are explicit, not empty successful contexts.

A resumable corpus worker processes all existing questions and watches for
newly ingested ones. Per-problem jobs record status, attempts and errors;
completed metadata is not regenerated unless an admin requests it. Graph
publication follows successful storage. Admins can review/reject, edit
attributes with an audit rationale, regenerate automatic teaching metadata,
and explicitly publish corrections. Regeneration preserves human overrides.
Recovery behavior and validation are specified in the
[automatic enrichment recovery plan](14_AUTOMATIC_ENRICHMENT_RECOVERY.md).

Earlier PENDING/review-gated descriptions below are historical rollout context,
superseded by this policy. Generated coaching itself remains provisional.

Evolve the corpus graph into a teaching graph without confusing Concept
(knowledge), Skill (an observable action), and Technique (a method).
The attached proposal is the design input. Its historical corpus counts are
not targets or guarantees; use the live graph overview for current coverage.

This delivery implements **P0 foundations and anonymous guided tutoring**.
P1 extraction, stored hint ladders, misconception models, and versioned
courses are planned below, not claimed as deployed or populated.
Postgres remains the system of record; Neo4j remains a reproducible projection.
Existing corpus relationships, retrieval, authentication, and learner records
are preserved. Presentation pages document the implemented workflow, live
rollout evidence, review limitations, and P1/P2 roadmap.

### Conversation persistence

The agent API and ADK web server persist conversation sessions, events and
state in the configured Postgres server's isolated `agent_sessions` schema.
Startup must verify database access and fail explicitly rather than silently
falling back to SQLite or memory. Corpus access still passes through REST;
conversation state is not measured mastery or reviewed pedagogical metadata.
Acceptance requires state and event retrieval through a new service instance,
user isolation and deletion of the integration test's session. Legacy SQLite
sessions are retained locally but are not automatically migrated.

### Current admin approval status

On 2026-10-04, after the initial pending rollout below, the operator explicitly
authorized bulk approval of **only the 27 starter assertions**. The authenticated
`/admin/pedagogy` UI saved 6 skills, 6 skill-concept links, 6 skill relations,
6 problem mappings, and 3 difficulty assessments as REVIEWED in Neon, with
27 immutable before/after audit events and the operator's rationale. Explicit
publication then reconciled AuraDB: **18 REVIEWED skill-related edges**,
**65 PENDING legacy concept-hierarchy edges**, and 3 REVIEWED assessments.
The 65 hierarchy assertions and pending corpus topic/method tags were not approved.

This is user-authorized bootstrap approval, not a claim of independent expert
verification or calibrated difficulty. Generated coaching remains PENDING.
The reviewed starter set now enables real prerequisite and lower-level
same-skill retrieval; for `AMC10_2007B_Q20`, the reviewed context has two skill
mappings, three prerequisite skills, and recommends `AMC10_2005B_Q18` using
shared-skill required levels 3 versus 2. Overall difficulty is not inferred.

## Admin review and publication requirements

| ID | Requirement | Acceptance |
|---|---|---|
| PED-17 | Admin inspection covers all five P0 metadata tables. | Filter by type/status, paginate, inspect objectives, problem statements, dimensions, nullable fields, source and confidence; optionally load corpus solutions for review. |
| PED-18 | Decisions are explicitly authorized and audited in Postgres. | Approve, reject, or return to pending; mandatory 10-2,000-character rationale; immutable before/after snapshots, timestamp and shared-admin credential identity. No fabricated individual reviewer name. |
| PED-19 | Bulk decisions are transactional and bounded. | Select assertions on the current queue page (API maximum 100), or approve remaining pending assertions from the versioned starter manifest. Skills precede dependent mappings; any stale snapshot, missing dependency, duplicate key or reviewed DAG cycle rolls back every decision and audit event. If the starter import is incomplete, its bulk action is disabled with an explicit warning; unrelated metadata remains reviewable. |
| PED-20 | Review and publication are separate operations. | Saving never automatically changes Neo4j. Explicit publish checks the displayed source fingerprint, validates cycles and atomically reconciles owned pedagogical metadata. Source changes require reloading. |
| PED-21 | Admin surfaces are authenticated. | Protected page and same-origin proxy require admin login; REST requires its admin API key. The browser never receives that key. Mutations reject cross-origin requests. |
| PED-22 | Publication state is visible and honest. | Show last recorded publication and whether source metadata changed. Warn that rejected assertions can remain active in the previous graph until publish; clear local graph caches on success without stale in-flight reads repopulating them. |

Migration 007 adds `knowledge.pedagogy_review_event` and
`knowledge.pedagogy_publication`. Additional authenticated REST endpoints live
under `/v1/admin/pedagogy`: GET `queue`; POST `review`, `bulk-review`,
`approve-starter`, `history`, and `publish`. Queue status and pagination are
bounded; review mutations include a snapshot revision, publication includes
the source fingerprint. Failures return 401/403, 404, 409, 422, or 503 as
appropriate rather than success-shaped responses.

Neo4j and the Postgres publication record cannot share a database transaction.
If the graph commits but recording fails, report failure and explicitly retry
publication; never claim an unrecorded cross-database commit was atomic.
The publication fingerprint covers source tables, not external graph edits.
External projection tools must be coordinated with the admin publisher.

## Implemented P0 requirements

| ID | Requirement | Acceptance |
|---|---|---|
| PED-01 | Skills have stable identifiers, unique slugs, names, measurable objectives, and optional levels 1-5. | A skill is not auto-created merely by renaming a concept. |
| PED-02 | Skills belong to concepts through PART_OF; prerequisite and hierarchy edges have explicit semantics. | PREREQUISITE_OF goes from prior skill to dependent skill; PART_OF goes from child to parent. |
| PED-03 | Problem-skill edges distinguish REQUIRES, PRACTICES, and TESTS. | Edges retain role, required_level, importance, confidence, source, and review_status. |
| PED-04 | Difficulty is multidimensional and nullable. | conceptual_depth, technical_load, algebraic_load, insight_required are 1-5; number_of_steps, prerequisite_depth, estimated_contest_level retain provenance. Missing dimensions are not guessed from contest/year. |
| PED-05 | Metadata has explicit provenance and review gates. | PENDING, REVIEWED, REJECTED remain distinguishable. Only reviewed skills/edges/dimensions guide prerequisite and easier-practice assertions. |
| PED-06 | Metadata authoring is validated and idempotent. | Import checks natural-key references, ranges, duplicate keys, self-links, and cycles in prerequisite/hierarchy DAGs; failures roll back the transaction. Validation/dry run performs no writes. |
| PED-07 | Projection is additive and explicitly enabled. | Ordinary corpus projection still works before migration. Pedagogical projection requires the migration and reports a missing schema rather than swallowing an exception. Repeated projection does not create duplicates. |
| PED-08 | Existing classification edge provenance survives projection. | TESTS, USES_TECHNIQUE, and CONCEPT_RELATION retain assertion source/review status/confidence or strength. Legacy generic relationships are not indiscriminately reinterpreted. |
| PED-09 | Learning context excludes answers and solutions. | The public context contains statement, reviewed skills/prerequisites, difficulty, taxonomy labels, diagnostic options, and explicit coverage warnings, never official_answer or solution bodies. |
| PED-10 | Diagnosis precedes hints. | Ask for an attempt and distinguish concept recognition, strategy selection, execution, calculation, and connecting steps. A self-reported diagnosis is not a measured mastery fact. |
| PED-11 | Help is progressive and bounded. | One requested hint at a time, levels 1-3, with a micro-lesson and a return-to-original prompt. No automatic full-solution retrieval during guided tutoring. |
| PED-12 | Generated coaching is visibly provisional. | Generated advice is PENDING/unreviewed and not stored as a reviewed hint ladder. Model/schema/network failures are explicit errors, not empty success responses. |
| PED-13 | Lower-level same-skill practice is evidence-based. | Match reviewed skills, relationship type, role, and lower required_level. This is narrower evidence, not a claim that the whole problem is easier. Empty coverage is stated, not replaced with invented examples. |
| PED-14 | The workflow is anonymous and ephemeral. | Browsing/diagnosis/hints never writes learner attempts, mastery, or permanent profiles. Future personalization remains authenticated and separately consented. |
| PED-15 | Web and ADK use the same versioned REST contracts. | The browser uses same-origin proxies; ADK tools call REST, not databases. Existing free chat and streaming tool activity remain available. |
| PED-16 | Graph inspection exposes teaching metadata. | New Skill/typed relationship views show review gates and selected-node/edge metadata without exposing solution/answer text. |

## Learning workflow

1. Select a canonical problem from the corpus or enter its code in `/learn`.
2. Fetch answer-free learning context and show whether it is reviewed or
   unenriched. A lack of metadata is a coverage gap, not a graph outage.
3. Ask a diagnostic question; the learner chooses the kind of difficulty and
   provides their current attempt.
4. Request a micro-lesson and first hint. Label generated content clearly.
5. Invite the learner to try again before explicitly requesting the next
   level. Stop escalation at level 3; do not silently disclose the solution.
6. Show reviewed prerequisite skills and lower-level same-skill practice
   where available. Return to the original problem.
7. Full solutions remain an intentional, separate corpus-browsing action.

## API contract

All public endpoints are under `/v1/tutor`; anonymous requests are read-only
with respect to corpus, graph, and learner state.

| Method | Path | Behavior |
|---|---|---|
| GET | `/learning-context/{problem_code}` | Statement, skills, prerequisites, dimensions, diagnosis choices, provenance/coverage warnings. |
| GET | `/prerequisites/{skill_slug}` | Bounded reviewed prerequisite traversal, with explicit max_depth and truncation/coverage semantics. |
| GET | `/practice/{problem_code}` | Bounded lower-level same-skill candidates, matching reviewed relationship type and role; no lower-overall-difficulty guarantee. |
| POST | `/coach` | problem_code, diagnosis, student_attempt, hint_level 1-3; validated diagnostic question, micro_lesson, hint, return_prompt, provenance, warnings. |

Unknown problems/skills return 404; malformed or out-of-range input is
rejected; database/model failures return actionable non-success status.
The web proxies preserve upstream statuses and do not convert errors into
empty lists. Streaming activity exposes tool names/status, not private
model reasoning or raw tool payloads.

## Metadata collection and rollout

- An expert authors or reviews skills, prerequisites, and problem mappings.
  LLM-suggested material enters PENDING, never implicitly REVIEWED.
- Sources should identify a rubric, solution revision, expert review, or
  pipeline version. Confidence is not an approval flag.
- Apply the additive SQL migration explicitly to the intended database.
- Validate the metadata manifest without writes; run the transactional import
  only after resolving references and reviewing its scope.
- Project the pedagogical layer explicitly into the matching graph.
- Inspect node/edge counts, sources, and review coverage in the web graph.
- Before enrichment, `/learn` still supports diagnosis and provisional
  statement-grounded coaching, but reports missing reviewed skills and does
  not claim prerequisites/easier practice are known.
- Do not automatically run migrations/imports against shared Neon/AuraDB.

Exact rollout commands and manifest formats are documented in the
[database README](../mathbank-db/README.md) and
[graph README](../mathbank-graph/README.md).

### Initial live rollout and review limits (superseded by admin approval above)

The user-authorized migration and metadata writes were applied to the same
Neon/AuraDB pair used by the app, after sanitized target-identity checks.
Migration 006 created five tables. The
[reproducible starter manifest](../mathbank-db/data/pedagogy/counting-foundations.v1.json)
contains 6 skills, 6 skill-concept links, 6 skill relations, 6 problem mappings,
and 3 assessments. All are PENDING; none were promoted to expert review.
The scope is three counting problems, not the entire 5,960-problem corpus.

AuraDB contains the 18 new skill-related relationships plus 65 explicit
existing concept-hierarchy projections: 83 owned pedagogical edges, all
PENDING. The three assessments are attached to their Problem nodes with
namespaced provenance. The overall graph totals are 20,942 nodes and 35,529
relationships. Core problem/solution counts stayed 5,960/13,168.

Consequently, default reviewed teaching views are empty and `/learn` accurately
reports missing reviewed skill/difficulty evidence. Diagnosis and provisional
statement-grounded coaching work now; reviewed prerequisites and same-skill
recommendations become available only after human review and re-projection.
Inventory views expose pending assertions for review. Confidence values and
user self-diagnosis never constitute approval or mastery.

Verification includes:
- Offline manifest validation and read-only database FK/cycle dry run.
- Repeated live import preserving values and UUIDs; repeated graph projection
  preserving counts without duplicates.
- Real reviewed prerequisite/path and lower-level practice queries tested in
  a rolled-back graph fixture; production stays PENDING.
- Real SQL constraint failure rolling back the entire batch.
- Deliberately failed Neo4j replacement preserving the previous live graph.
- All nine teaching-view APIs, reviewed/inventory filtering, and provenance.
- Live same-origin context/coaching, validation/404 paths, and real model output.
- Browser attempt gating, hints 1-3, blocked fourth hint, return prompt,
  provisional labels, and no learner-write requests.
- Streamed ADK context-first diagnosis and one requested hint without
  full-solution retrieval. The web adds a deterministic PENDING notice from
  structured tool provenance, even if the model omits that label in its prose.

The live regression tests are opt-in and never persist reviewed fixtures.
Remote database rollout is complete; this does not claim production web
hosting, calibrated difficulty ratings, expert-verified hint accuracy, or
deployment of P1/P2 entities. Model-generated advice can be wrong: it is
explicitly provisional, not a verified teaching resource.

## P1: semantic solution steps and reproducible courses (planned)

### SolutionStep and hint ladders

Reuse the existing `core.solution_step` entity instead of adding a competing
step table. Extract semantic reasoning steps, not sentences. Preserve source
solution ID/revision, ordinal, explanation, verification, model/rubric version,
and expert review. Project Solution HAS_STEP SolutionStep; attach USES_SKILL
and USES_TECHNIQUE. Each step may have four explicit stored Hint levels:
directional, conceptual, strategic, nearly explicit. Fetch only the next
permitted hint, not the full ladder or final answer.

Acceptance: step ordinals are stable for a fixed revision; hint escalation is
deterministic; revisions never overwrite approved content; all generated
steps/hints remain PENDING until reviewed; no answer leak in student APIs.

### Misconception and ErrorPattern

Model common errors separately from learner mistakes. Link Problem
HAS_COMMON_ERROR Misconception and Misconception RELATED_TO Skill with
provenance and review status. Actual attempts may later support or refute
these hypotheses; do not assert a learner misconception based solely on an
LLM interpretation of a solution.

### Course, Module, Lesson

The existing product notion of Course as a competition grouping is not an
implemented pedagogical sequence. Extend it with a versioned, approved
curriculum: name, target_level, version, graph snapshot/version, status,
source, review record. Course HAS_MODULE Module, Module HAS_LESSON Lesson,
with edge ordinals; Lesson TEACHES Skill, EXPLAINS Concept, PRACTICE Problem.

Generate candidate order using prerequisite DAG topology, skill difficulty,
concept hierarchy, and reviewed problem-level evidence. Store approved
results reproducibly; do not present a temporary LLM list as a published
course. Reject cycles, missing prerequisites, duplicate ordinals, and
version drift. `build_learning_path` and `get_course_outline` remain planned
tools until the stored curriculum and APIs exist.

## P2: similarity, learner evidence, and evaluation (planned)

- Semantic/structural analogies and alternate methods must carry evidence;
  resemblance alone is not an easier-than claim.
- Authenticated Attempt/Mastery/ErrorEvent integration is separate from
  anonymous state; never request passwords or tokens in the coaching flow.
- Compare retrieval coverage, expert-rated hint usefulness, solution
  disclosure rate, prerequisite correctness, completion, and transfer to
  analogous problems. Use independent reviewed gold sets, not generated
  output as its own ground truth.

## Validation and release gates

1. Import unit tests cover bounds, provenance, unknown references, cycles,
   rollback, dry runs, and idempotency.
2. REST tests cover reviewed-only gating, prerequisite direction and depth,
   absent coverage, unknown IDs, errors, and answer-free payloads.
3. Coaching tests cover all five diagnosis kinds, progressive levels,
   structured-output validation, and explicit generated provenance.
4. Agent tests verify learning-context-first routing and one hint per request;
   legacy search/full-solution tools still work for explicit requests.
5. Web tests cover metadata and unenriched states, diagnosis selection,
   attempt collection, bounded hint escalation, problem switching, errors,
   and lack of learner-state writes.
6. Production build and existing relevant tests pass. Live data enrichment
   is a separate, explicitly approved rollout and must be reported honestly.
