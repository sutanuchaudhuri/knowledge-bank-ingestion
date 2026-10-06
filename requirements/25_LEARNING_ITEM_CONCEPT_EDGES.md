# 25 — Learning item → concept edges in the graph (NYI-ATB-7)

Status: ✅ **implemented and projected on 2026-10-05**. The Aura graph reconciled at 11,186 / 11,186 for each new edge type.

Related:
- Graph projection spec: [runtime_extension/06](../math_tutor_new_requirements_copilot_pack_v2_expanded/runtime_extension/06_GRAPH_PROJECTION_V2.md).
- Graph reference: [reference/GRAPH_SCHEMA.md](reference/GRAPH_SCHEMA.md).
- Admin dashboard: [24](24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md).
- Backlog: [20](20_NOT_YET_IMPLEMENTED.md) (NYI-ATB-7).
- Tracker: [18](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md).
- Gotchas: [19](19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md) (GOT-ATB-12…14).

## 1. Problem

Every Prasolov learning item (a transformed question: MCQ, subproblem, numeric variant, …) has three taxonomy targets in Postgres: `target_concept_node_id`, `target_subconcept_node_id` and `target_skill_node_id`. The graph projected only one of them:

| Edge | Before | Items covered |
|---|---:|---:|
| `LearningItem -[:ASSESSES]-> Skill` | 6,475 | 6,475 (every item with a skill) |
| `LearningItem -> Concept / Subconcept` | **0** | **0** |

That left **4,711 items (42%) with no taxonomy edge at all**. They could reach a concept only indirectly, through `DERIVED_FROM -> Problem -[:TESTS]-> Concept` or `ANCHORED_AT -> SolutionStep -[:USES_CONCEPT]-> Concept`. Those paths describe the *source problem* or the *step*, not what the transformation actually targets. As a result, graph queries such as "practice items for *Inscribed angle* / *Power of a point*", recovery coursework by subconcept, and the graph explorer could not select items by the concept they teach.

Runtime_extension/06 lists only `ASSESSES` / `PRACTICES -> Skill` for learning items. The concept edges are a **project extension**, consistent with the step-level `USES_CONCEPT` / `USES_SUBCONCEPT` pattern.

## 2. Data profile (Neon, 2026-10-05, read-only)

| Check | Result |
|---|---:|
| Approved, student-visible learning items | 11,186 |
| With `target_concept_node_id` / bridged to `core.concept` | 11,186 / 11,186 |
| With `target_subconcept_node_id` / bridged to `core.concept` | 11,186 / 11,186 |
| Concept target whose `node_type` ≠ `CONCEPT` | 0 |
| Subconcept target whose `node_type` ≠ `SUBCONCEPT` | 0 |
| Subconcept whose `PART_OF` parent ≠ the item's concept target | 0 |
| Distinct concept / subconcept targets | 30 / 214 |
| Items without a skill target | 4,711 |

## 3. Graph contract

```
(LearningItem)-[:TARGETS_CONCEPT]->(Concept)        // chapter-level concept
(LearningItem)-[:TARGETS_SUBCONCEPT]->(Subconcept)  // section-level subconcept; the node also has the Concept label
```

| Aspect | Rule |
|---|---|
| Direction | Learning item → taxonomy, the same as `ASSESSES` and step `USES_*`. |
| Source column | `pedagogy.learning_item.target_concept_node_id` / `target_subconcept_node_id`. |
| Bridge | `pedagogy.taxonomy_node.concept_id` (a `core.concept` uuid), which is the graph `canonical_id`. The node's type must match (`CONCEPT` resp. `SUBCONCEPT`); otherwise the row is skipped. |
| Target match | `MATCH (b:Concept {canonical_id})` for concepts, `MATCH (b:Subconcept {canonical_id})` for subconcepts. |
| Cardinality | At most one edge of each type per item, because the source columns are scalar. |
| Identity | `projection_key = "<TYPE>|<learning_item_id>|<concept uuid>"`; `MERGE (a)-[r:TYPE]->(b)`. |
| Properties | `projection_kind = 'solution_steps'`, `projection_key`. No text, answers or seeds. |
| Eligibility | Same as `LearningItem` nodes: `review_status = 'APPROVED' AND student_visible`, in a ready content package. |
| Null handling | A null or unbridgeable target produces no edge, and is excluded from the expected count, so it does not cause a mismatch. |
| Removal | Stale-key pruning: if a target changes or the item stops being eligible, the old edge is deleted on the next run. |
| Consistency invariant | `(li)-[:TARGETS_SUBCONCEPT]->(s)-[:PART_OF]->(c)<-[:TARGETS_CONCEPT]-(li)` holds for every item (verified 11,186 / 11,186). |

Why two edges instead of only the subconcept edge: the concept is derivable through `PART_OF`, but a direct edge keeps one-hop queries (chapter-level practice lists, dashboard coverage) simple. It also survives any future subconcept that has no parent.

## 4. Implementation

| File | Change |
|---|---|
| [project_textbook_steps.py](../mathbank-graph/etl/project_textbook_steps.py) | `load()` joins `taxonomy_node` twice (type-checked) and returns `concept_id` / `subconcept_id` per item. `build_jobs()` emits `TARGETS_CONCEPT` / `TARGETS_SUBCONCEPT` edge jobs, skipping null targets. Reconciliation counts them automatically. |
| [test_project_textbook_steps.py](../mathbank-graph/tests/test_project_textbook_steps.py) | `test_learning_items_target_concept_and_subconcept_when_bridged`: expected counts, null skipping, keys and target labels. |
| [textbook_admin.py](../mathbank-rest/src/mathbank_rest/db/textbook_admin.py) | New coverage-matrix entity `learning_item_concept`, expected in `pg` and `graph`. PG side: eligible items with a concept target. Graph side: distinct items with `TARGETS_CONCEPT`. |
| [test_admin_textbooks.py](../mathbank-rest/tests/test_admin_textbooks.py) | `test_build_matrix_learning_item_concept_links_are_graph_only`. |

No migration, no paid model calls, no vector change. Postgres is unchanged: the projector only reads it, apart from the usual `pipeline.graph_projection` run row and the package `report`.

## 5. Operations

```bash
# plan only (reads Postgres)
cd mathbank-graph && GRAPH_ENV_FILE=remote.env .venv/bin/python etl/project_textbook_steps.py --dry-run
# write + prune + reconcile (idempotent; also part of `make -C mathbank-db textbook-graph-remote`)
cd mathbank-graph && GRAPH_ENV_FILE=remote.env .venv/bin/python etl/project_textbook_steps.py
# compare only
cd mathbank-graph && GRAPH_ENV_FILE=remote.env .venv/bin/python etl/project_textbook_steps.py --status
```

Run result, 2026-10-05: 0 pruned. Every type reconciled, with `TARGETS_CONCEPT` 11,186 / 11,186 and `TARGETS_SUBCONCEPT` 11,186 / 11,186. The admin coverage API reports `learning_item_concept` 11,186 / 11,186, status OK.

## 6. Example read queries (Cypher, read-only)

```cypher
// Practice items for a subconcept (e.g. recovery coursework)
MATCH (s:Subconcept {canonical_id: $subconcept_id})<-[:TARGETS_SUBCONCEPT]-(li:LearningItem)
RETURN li.canonical_id, li.transformation_type, li.difficulty_direction LIMIT 25;

// Items per concept, split by whether they also assess a skill
MATCH (c:Concept)<-[:TARGETS_CONCEPT]-(li:LearningItem)
RETURN c.name, count(li) AS items, sum(CASE WHEN (li)-[:ASSESSES]->() THEN 1 ELSE 0 END) AS with_skill
ORDER BY items DESC;

// Invariant check (expect 0)
MATCH (li:LearningItem)-[:TARGETS_SUBCONCEPT]->(s), (li)-[:TARGETS_CONCEPT]->(c)
WHERE NOT (s)-[:PART_OF]->(c) RETURN count(li);
```

## 7. Acceptance criteria

| ID | Criterion | Result |
|---|---|---|
| LIC-1 | Every eligible item whose target bridges has exactly one `TARGETS_CONCEPT` and one `TARGETS_SUBCONCEPT`. | ✅ 11,186 / 11,186 each |
| LIC-2 | No learning item lacks a concept edge, when the source has a target. | ✅ 0 orphans |
| LIC-3 | Subconcept and concept targets are consistent through `PART_OF`. | ✅ 11,186 |
| LIC-4 | Re-running is idempotent: 0 pruned, same counts. | ✅ |
| LIC-5 | Edges carry no question text, answers or seeds. | ✅ only `projection_kind` / `projection_key` |
| LIC-6 | Admin coverage shows the new row with OK status. | ✅ |
| LIC-7 | Offline tests cover counts, null skipping and labels. | ✅ graph 3 / admin 14 pass |

## 8. Not done / follow-ups

- **Consumers:** no REST endpoint, agent tool or web graph view queries these edges yet. Recovery practice selection (Phase 9/10) still ranks items in Postgres by `target_subconcept_node_id`, which is equivalent. Wire into the graph explorer and the ADK tools with NYI-P11.
- **`PRACTICES -> Skill`** (from 06) is still unused; `ASSESSES` is the only item→skill edge.
- **Technique targets:** learning items have no technique column, so there is no `TARGETS_TECHNIQUE`.
- **Web graph config:** `mathbank-web/lib/graphConfig.js` does not list the new types, so the explorer does not offer them as a relationship view.
