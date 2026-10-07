# Neo4j graph schema reference

## Evidence

- Evidence mode: source-derived only.
- Source revision: `3e915d015aa34268996724a3014c850f5892596e`, with uncommitted worktree changes included.
- Sources: `mathbank-graph/etl/project_from_postgres.py`, `mathbank-graph/etl/project_textbook_steps.py`, graph-related migrations and readers, `mathbank-web/lib/graphConfig.js`, `mathbank-web/lib/graphMetadata.mjs`; migrations 021/022 and their REST writers were checked to confirm their learner-evidence/artifact data is not projected.
- No live Neo4j target was queried; counts in older READMEs remain dated audits, not current proof.

### Topic-first incremental boundary

Source revision `c79060ac0771175baa6e04b37bede840f8c30ee1` plus relevant worktree
changes. Freshly examined both projectors' ownership/review paths, migrations
023/024, topic-practice SQL, structural audit, importer validation and ADK lesson
state. **No new graph labels, edge types, properties or constraints** accompany
these additions. TopicLearningPlan, quiz results, learner feedback/audit snapshots
and reviewed retriever labels stay in PostgreSQL/ADK session state.

Interactive lesson stage status/timing, hints and navigation remain ADK
session-state fields; printed-work problem-context checks use the existing
attempt-media workflow. Neither is a graph projection or learner mastery edge.
The current update added no graph-writer or graph-reader contract.

Exact-topic practice uses PostgreSQL published-step evidence before ranking;
vector proximity and a graph edge alone do not establish applicability.
`STEP_SUPPORTED` is computed REST membership, not a newly projected
Problem-USES_TECHNIQUE assertion. Human-resolved retrieval negatives gate practice,
not the general graph/corpus views. Future unsupported Power import proposals are
held out of the canonical bridge, not automatically removed from Neo4j.
Canonical correction still requires explicit publication and verification of
each store. This source refresh made no graph queries/publications and does not
claim live graph parity or automatic graph/vector/cache reconciliation.

## Projection ownership

### Solution-grounded planning boundary

Incremental source revision `1582f808a731e571e79b588d4c73e717eefc7956` plus related
worktree changes. `solution_guidance.py` obtains private canonical references
from PostgreSQL, not from graph tags. Its explicit REST plan read itself does
not query/enrich the graph; the agent separately loads existing graph teaching
context. Neither a route rationale nor a retrieved UNVERIFIED solution record
is mathematical proof, a new annotation or a mastery edge. No projector file,
label, relationship, property or constraint changes in this update.

### Guided-workspace read reliability

Incremental source revision `1582f808a731e571e79b588d4c73e717eefc7956` plus
related worktree changes; examined both projector ownership paths,
`pedagogy.graph_rows`, orientation routes and workspace contracts.
Teaching graph reads now materialize record dictionaries within
`session.execute_read`; transient read retry is driver-managed instead of
auto-commit `session.run`. Persistent failures remain explicit 503 responses,
not fabricated metadata. Query directions, review filters and projection
ownership are unchanged.
When the bounded approved-ancestor read is empty, the deeper-path existence
probe is skipped: any approved longer path must have an approved shorter
suffix. This preserves results and avoids the observed Q31 depth-check stall.

Authored orientation, browser draft/stage state and optional Q31 construction
create no graph label, property, relationship or constraint.
`GET /v1/tutor/workspace/{code}` and visual definitions intentionally bypass
Neo4j, so a slow teaching graph cannot block the canonical question or authored
orientation. Current-object frame IDs are renderer element identities, not
graph node keys. Source-verified circumcenter definitions are not projected.
No new learner
projection or graph-backed PedagogySession is implied. No live Neo4j schema
probe or publication occurred in this documentation phase; the wider graph
inventory keeps its prior source evidence. See
[34](../34_GUIDED_PROBLEM_WORKSPACE.md).

Postgres is canonical. Neo4j is a rebuildable projection.

| Projector | Graph layer | Write behavior |
|---|---|---|
| `project_from_postgres.py` | corpus graph (`Competition`, `Paper`, `Problem`, `Solution`, `Concept`, `Technique`) | MERGE nodes by PostgreSQL UUID `canonical_id`; MERGE corpus edges by endpoint and role/relation. Records `pipeline.graph_projection(graph_name='corpus_graph')`. |
| `project_from_postgres.py --pedagogy` | reviewed/inspectable teaching metadata (`Skill` and semantic edges) | Ensures `Skill` constraint. In one Neo4j transaction deletes relationships with `projection_kind='pedagogy'`, removes pedagogy properties from `Problem`, marks missing owned `Skill` nodes `REJECTED`, and rewrites current pedagogy nodes/edges. Updates `pipeline.graph_projection`. |
| `project_textbook_steps.py` | textbook solution-step metadata (`SolutionPart`, `SolutionStep`, `LearningItem`) | Writes only objects tagged `projection_kind='solution_steps'`, `projection_version='v2'`; prunes stale step-layer nodes/edges of that kind; records `pipeline.graph_projection(graph_name='textbook_step_graph')` and package report. |

There is no cross-database atomic transaction between Postgres and Neo4j. Pedagogy replacement is atomic inside Neo4j; Postgres publication rows are written afterward by REST admin code.

## Constraints and indexes

Projectors create these Neo4j uniqueness constraints when run:

| Label | Constraint |
|---|---|
| `Competition` | `canonical_id` unique (`competition_id`) |
| `Paper` | `canonical_id` unique (`paper_id`) |
| `Problem` | `canonical_id` unique (`problem_id`) |
| `Concept` | `canonical_id` unique (`concept_id`) |
| `Technique` | `canonical_id` unique (`technique_id`) |
| `Solution` | `canonical_id` unique (`solution_id`) |
| `Skill` | `canonical_id` unique (`skill_id`, only with `--pedagogy`) |
| `SolutionPart` | `canonical_id` unique (text `pedagogy.solution_part.solution_part_id`) |
| `SolutionStep` | `canonical_id` unique (text `pedagogy.solution_step.solution_step_id`) |
| `LearningItem` | `canonical_id` unique (text `pedagogy.learning_item.learning_item_id`) |

No property type constraints are declared in source.

## Node labels and properties

Required means required by the source table/query for the projector path, not enforced by Neo4j.

| Label | Identity/merge key | Properties projected | Source |
|---|---|---|---|
| `Competition` | `canonical_id = core.competition.competition_id` | `external_code` optional text, `name` required text, `level` optional text | `core.competition` |
| `Paper` | `canonical_id = core.paper.paper_id` | `external_code` optional text, `paper_code` text, `question_count` optional integer, `year` nullable integer after textbook migration | `core.paper` + `core.competition_edition` |
| `Problem` | `canonical_id = core.problem.problem_id` | `canonical_code`, `problem_number`, `official_answer`, `source_url`, `difficulty_band`, `classification_status`, `problem_page_images`, `solution_page_images`; pedagogy layer may add `conceptual_depth`, `technical_load`, `algebraic_load`, `insight_required`, `number_of_steps`, `prerequisite_depth`, `estimated_contest_level`, `pedagogy_source`, `pedagogy_confidence`, `pedagogy_review_status`, `pedagogy_approval_method` | `core.problem`, image counts, `knowledge.problem_pedagogy` |
| `Solution` | `canonical_id = core.solution.solution_id` | `solution_kind`, `revision`, `verification_status` | `core.solution`; body text is deliberately not projected |
| `Concept` | `canonical_id = knowledge.concept.concept_id` | `slug`, `name`, `level`; some concept nodes also get secondary label `Subconcept` when a textbook taxonomy node of type `SUBCONCEPT` bridges to that concept | `knowledge.concept`, `pedagogy.taxonomy_node` |
| `Technique` | `canonical_id = knowledge.technique.technique_id` | `slug`, `name` | `knowledge.technique` |
| `Skill` | `canonical_id = knowledge.skill.skill_id` | `slug`, `name`, `objective`, `level`, `source`, `confidence`, `review_status`, `approval_method`, `projection_kind='pedagogy'` | `knowledge.skill` |
| `SolutionPart` | `canonical_id = pedagogy.solution_part.solution_part_id` | `projection_kind='solution_steps'`, `projection_version='v2'`, `postgres_id`, `external_id`, `book_code`, `source_package_id`, `content_version`, `occurrence`, `part_label`, `part_ordinal`, `step_count`, `source_page`, `problem_canonical_code`, `publication_status='IMPORTED'` | `pedagogy.solution_part` joined to package/problem |
| `SolutionStep` | `canonical_id = pedagogy.solution_step.solution_step_id` | `projection_kind='solution_steps'`, `projection_version='v2'`, `postgres_id`, `external_id`, `book_code`, `source_package_id`, `content_version`, `occurrence`, `global_step_index`, `step_index_in_part`, `step_type`, `tutor_role`, `hint_level`, `is_checkpoint`, `skill_name`, `source_page`, `problem_canonical_code`, `publication_status` | `pedagogy.solution_step`; step text is not projected |
| `LearningItem` | `canonical_id = pedagogy.learning_item.learning_item_id` | `projection_kind='solution_steps'`, `projection_version='v2'`, `postgres_id`, `external_id`, `book_code`, `source_package_id`, `content_version`, `transformation_type`, `transformed_form`, `difficulty_direction`, `publication_status` | approved + student-visible `pedagogy.learning_item`; question text/answers are not projected |
| `Subconcept` | Additional label on a `Concept` node | Same properties as the underlying `Concept` | `pedagogy.taxonomy_node.node_type='SUBCONCEPT' AND concept_id IS NOT NULL` |

## Relationship endpoint pairs

| Source -> relationship -> target | Identity/merge key | Properties | Source/direction |
|---|---|---|---|
| `Competition -[:HAS_PAPER]-> Paper` | endpoint pair | none | competition owns paper |
| `Paper -[:HAS_PROBLEM]-> Problem` | endpoint pair | none | paper contains problem |
| `Problem -[:HAS_SOLUTION]-> Solution` | endpoint pair | none | problem has solution metadata |
| `Problem -[:TESTS {role}]-> Concept` | `(problem_id, concept_id, role)` | `confidence`, `source`, `review_status`, later `approval_method` | `knowledge.problem_concept`; assertion direction problem tests concept |
| `Problem -[:USES_TECHNIQUE {role}]-> Technique` | `(problem_id, technique_id, role)` | `confidence`, `source`, `review_status`, later `approval_method` | `knowledge.problem_technique`; problem uses technique |
| `Concept -[:CONCEPT_RELATION {relation_type}]-> Concept` | `(from_concept_id, to_concept_id, relation_type)` | `strength`, `confidence` (same SQL value), `source`, `review_status`, later `approval_method` | raw authored/imported concept relation direction |
| `Skill -[:PART_OF]-> Concept` | `(skill_id, concept_id)` | `source`, `confidence`, `review_status`, `approval_method`, `projection_kind='pedagogy'` | `knowledge.skill_concept`; skill belongs to concept |
| `Skill -[:PREREQUISITE_OF]-> Skill` | `(from_skill_id, to_skill_id, relation_type)` | `source`, `confidence`, `review_status`, `approval_method`, `projection_kind='pedagogy'` | prior skill -> dependent skill |
| `Skill -[:PART_OF]-> Skill` | same | same | child/component skill -> parent/composite skill |
| `Skill -[:BUILDS_ON]-> Skill` | same | same | useful prior/supporting skill -> dependent skill |
| `Problem -[:REQUIRES {role}]-> Skill` | `(problem_id, skill_id, relation_type, role)` | `role`, `required_level`, `importance`, `source`, `confidence`, `review_status`, `approval_method`, `projection_kind='pedagogy'` | problem requires skill |
| `Problem -[:PRACTICES {role}]-> Skill` | same | same | problem practices skill |
| `Problem -[:TESTS {role}]-> Skill` | same | same | problem tests skill; distinct from `Problem -> Concept` `TESTS` |
| `Concept -[:PART_OF]-> Concept` | semantic edge from selected `knowledge.concept_relation` | `source`, `confidence`, `review_status`, `approval_method`, `projection_kind='pedagogy'` | `PART_OF` preserves from->to; `HAS_SUBCONCEPT` is reversed to child/subconcept -> parent concept |
| `Concept -[:PREREQUISITE_OF]-> Concept` | semantic edge from selected `knowledge.concept_relation` | same | exact `PREREQUISITE_OF` only; no synonym/case inference |
| `Concept -[:BUILDS_ON]-> Concept` | semantic edge from selected `knowledge.concept_relation` | same | exact `BUILDS_ON` only |
| `Solution -[:HAS_PART]-> SolutionPart` | solution id + part id | `projection_kind`, `projection_key`, `part_ordinal` | solution contains ordered part |
| `SolutionPart -[:HAS_STEP]-> SolutionStep` | part id + step id | `projection_kind`, `projection_key`, `step_index_in_part` | part contains ordered step |
| `SolutionStep -[:USES_SKILL]-> Skill` | step id + bridged skill id | `projection_kind`, `projection_key` | step metadata references taxonomy node bridged to `knowledge.skill` |
| `SolutionStep -[:USES_CONCEPT]-> Concept` | step id + bridged concept id | `projection_kind`, `projection_key` | step concept taxonomy bridge |
| `SolutionStep -[:USES_SUBCONCEPT]-> Subconcept` | step id + bridged subconcept concept id | `projection_kind`, `projection_key` | step subconcept taxonomy bridge; target also has `Concept` |
| `SolutionStep -[:USES_TECHNIQUE]-> Technique` | step id + bridged technique id (`pedagogy.taxonomy_node.technique_id` → `knowledge.technique`) | `confidence`, `source_type`, `review_status`, `approval_method`, `derivation_version`, `projection_kind`, `projection_key` | Migration 017 `pedagogy.solution_step_technique` rows with `review_status='APPROVED'` and a TECHNIQUE taxonomy node bridged to `knowledge.technique`; rejected/removed tags are pruned as stale `solution_steps` edges on the next projection. Distinct from the corpus `Problem -[:USES_TECHNIQUE {role}]-> Technique` pair (no `role`). Prasolov-only today. |
| `SolutionStep -[:NEXT]-> SolutionStep` | dependency endpoints + type | `logical_dependency`, `confidence`, `source_type`, `review_status`, `approval_method`, `projection_kind`, `projection_key` | accepted step dependency type |
| `SolutionStep -[:DEPENDS_ON]-> SolutionStep` | same | same | dependency direction from dependent/source row to target row as in package table |
| `SolutionStep -[:DERIVES_FROM]-> SolutionStep` | same | same | accepted dependency type |
| `SolutionStep -[:USES_RESULT_FROM]-> SolutionStep` | same | same | source `USES_RESULT` is normalized to `USES_RESULT_FROM`; source `USES_RESULT_FROM` already accepted |
| `SolutionStep -[:ALTERNATIVE_TO]-> SolutionStep` | same | same | accepted dependency type |
| `SolutionStep -[:JOINS_AT]-> SolutionStep` | same | same | accepted dependency type |
| `LearningItem -[:DERIVED_FROM]-> Problem` | item id + source problem id | `projection_kind`, `projection_key` | item derived from source problem |
| `LearningItem -[:ANCHORED_AT]-> SolutionStep` | item id + step id | `projection_kind`, `projection_key`, `ordinal` | learning item anchor |
| `LearningItem -[:ASSESSES]-> Skill` | item id + bridged skill id | `projection_kind`, `projection_key` | item assesses target skill |
| `LearningItem -[:TARGETS_CONCEPT]-> Concept` | item id + bridged concept id (`target_concept_node_id` → `taxonomy_node.concept_id`, node_type `CONCEPT`) | `projection_kind`, `projection_key` | item's chapter-level target concept; project extension beyond runtime_extension/06 ([25](../25_LEARNING_ITEM_CONCEPT_EDGES.md)) |
| `LearningItem -[:TARGETS_SUBCONCEPT]-> Subconcept` | item id + bridged subconcept id (`target_subconcept_node_id`, node_type `SUBCONCEPT`) | `projection_kind`, `projection_key` | item's section-level target; target also has `Concept`; `PART_OF` the `TARGETS_CONCEPT` target |

## Review filtering and visibility

- `project_textbook_steps.py` filters at projection time: step dependencies with `review_status='REJECTED'` (admin-rejected, migration 019) are excluded, `LearningItem` nodes require `review_status='APPROVED' AND student_visible`, and step techniques require `APPROVED`; anything no longer selected is pruned as stale on the next run.
- Projectors write PENDING/REVIEWED/REJECTED assertions for inspection; review filtering is enforced by REST/UI readers and web graph filters, not by projection alone.
- `mathbank-web/lib/graphConfig.js` exposes relationship views for corpus and pedagogy edges; pedagogical views are flagged for reviewed-only default filtering in UI code.
- `mathbank-web/lib/graphMetadata.mjs` exposes safe node/edge metadata fields only. It includes page-image counts and review/provenance fields; it does not expose solution bodies.
- `project_textbook_steps.py` deliberately omits `SolutionStep.step_text`, `LearningItem.question_text`, correct answers, and solution seeds from Neo4j.
- Learning items become graph-eligible only after `pedagogy.learning_item.review_status = 'APPROVED'` and `student_visible = true`; Phase 10 automatic approval records `approval_method`/`approved_at` in Postgres but the current graph projector uses those columns as eligibility provenance only and does not project them as `LearningItem` properties.
- Step-level retrieval in Postgres (`step_search.py`) can include solution step text only when callers explicitly request it; no current REST route exposes it.
- Migrations 021/022 add private PostgreSQL attempt/evidence and artifact-runtime tables, but neither graph projector reads them. The graph has no learner-attempt, media, transcript, assessment, artifact-asset or artifact-bundle label/edge. Private evidence, learner utterances, approved step text and artifact content are therefore not graph properties; no graph inventory or live server was queried in this refresh.
