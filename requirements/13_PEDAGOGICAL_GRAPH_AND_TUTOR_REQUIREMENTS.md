# Pedagogical Graph and Anonymous Tutor

## Goal and scope

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

### Verified live rollout and review limits (2026-10-04)

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
