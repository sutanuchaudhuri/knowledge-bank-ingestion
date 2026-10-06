# 24 — Admin Textbook Corpus Dashboard and Store Coverage

Status: ✅ implemented 2026-10-05 (Prasolov packages Ch01_20 + Ch21_30).
Related: tracker [18](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md), gotchas [19 §13](19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md),
not-implemented [20](20_NOT_YET_IMPLEMENTED.md) (`NYI-ATB-*`), REST reference [reference/REST_API.md](reference/REST_API.md).

## 1. Why

The Prasolov source folders hold three kinds of input:

- `GEOMETRY-TEXTBOOKS/*/csv` (raw extraction).
- `*/pedagogy_v3/csv` (enriched import set).
- `*/diagrams`.

An admin must be able to answer two questions without SQL or Cypher:

1. *What is in the corpus?* Every problem, its solution(s), solution parts and steps, the step dependency DAG, every transformation (learning item), the concept/skill/technique taxonomy and every diagram, including answer-revealing ones.
2. *Did everything land in each store?* Compare source CSV rows with PostgreSQL, the pgvector embeddings and the Neo4j projection, and explain every difference.

## 2. Requirements

| ID | Requirement | Implementation |
|---|---|---|
| ATB-1 | Admin-only. The REST routes need `X-Admin-Api-Key`; the web pages and proxy need an admin session. Students never reach these routes. | Router-level `Depends(require_admin_api_key)`; `app/admin/(protected)/` layout; proxy returns 401 without a session. |
| ATB-2 | Read-only. No route writes to Postgres or Neo4j, enqueues jobs or calls a model. | `db/textbook_admin.py` contains only SELECT/MATCH statements. |
| ATB-3 | Coverage matrix per entity: source rows (summed across packages), Postgres, vectors, graph, expected stores, status (`OK`, `GAP`, `UNKNOWN`, `PROVENANCE`) and an explanatory note. | `GET /v1/admin/textbooks/coverage`. Coverage tab. |
| ATB-4 | If Neo4j is unavailable, coverage still returns and the graph columns show `UNKNOWN`, not a 500. | `graph_counts()` never raises; it returns `graph_ok=false` and `graph_error`. |
| ATB-5 | Per-chapter breakdown: sections, problems, solutions, steps, items, diagrams and problems embedded. | `chapters[]` in coverage. "Per chapter" table. |
| ATB-6 | Package list (status, version, import time, conflict count) and grouped import conflicts. | `packages[]` and `conflicts[]`. |
| ATB-7 | Problem browser with filters for text/code/number, chapter, taxonomy node, has-diagram and has-solution. Paginated, with per-row counts and an embedded flag. | `GET …/problems`. Problems tab. |
| ATB-8 | Problem detail covering statement, source metadata, enrichment and taxonomy, solutions, parts → steps (type, role, skill, checkpoint, hint level, embedded flag), dependencies, transformations (question, choices, correct answer, seed, anchors), diagrams, and per-store status. | `GET …/problems/{canonical_code}`. `/admin/textbooks/problems/[code]` with 5 tabs. |
| ATB-9 | Transformation browser filtered by type (with per-type counts), chapter and text. | `GET …/learning-items`. Transformations tab. |
| ATB-10 | Taxonomy browser by node type with problem, step and edge counts. Node detail lists parent, children, in/out edges with confidence, and problems, with one click to "all problems with this node". | `GET …/taxonomy`, `GET …/taxonomy/{id}`. Taxonomy tab. |
| ATB-11 | Diagram images, including `SOLUTION_HIDDEN`. The id is validated and the file must resolve inside the repository root; responses use private caching. | `GET …/diagrams/{source_diagram_id}/image?book=`. |
| ATB-12 | All inputs validated: book `^[A-Z0-9_]+$`, ids `^[A-Za-z0-9_.-]+$`, node type enum, booleans, clamped limit/offset. The proxy allowlists paths. | FastAPI `Query`/`Path` plus `lib/adminTextbooksProxy.mjs`. |

## 3. Coverage at implementation time (live Neon + Aura, observed 2026-10-05 UTC)

| Entity | Source rows | Postgres | Vectors | Graph | Status | Why counts differ |
|---|---:|---:|---:|---:|---|---|
| problem | 1,698 | 1,697 | 1,697 | 1,697 | OK | 1 `DUPLICATE_PROBLEM_ID` (chapter-intro prose row in 13.39). |
| solution | 1,548 | 1,546 | 1,546 (`SOLUTION_FULL`) | 1,546 | OK | 2 `ORPHAN_SOLUTION` rows (no matching problem). |
| chapter_section | 239 | 214 | — | — | OK (PG only) | Repeated (chapter, section) keys: 21 in Ch01_20 and 4 in Ch21_30; the last row wins. Graph has 30 `Paper` nodes (chapters); sections are not projected. |
| diagram | 250 | 250 | — | — | OK (PG only) | 40 `STUDENT_PROBLEM`, 210 `SOLUTION_HIDDEN`. |
| taxonomy_node | 544 | 501 | 501 | 501 | OK | The same ids appear in both packages. Embedded as `TAXONOMY_NODE` on 2026-10-05; the vector count is book-scoped and counts embedded chunks via `metadata->>'taxonomy_node_id'`. |
| learning_item_concept | — | 11,186 | n/a | 11,186 | OK | Added 2026-10-05: eligible items with a concept target vs distinct items with `TARGETS_CONCEPT` ([25](25_LEARNING_ITEM_CONCEPT_EDGES.md)). |
| taxonomy_edge | 3,065 | 3,065 | — | — | OK (PG only) | Graph uses the derived Concept/Skill/Technique relations, not these raw edges. |
| problem_enrichment | 1,698 | 1,697 | — | 1,697 (`TESTS`) | OK | Follows the duplicate problem. |
| solution_part | 2,001 | 2,001 | — | 2,001 | OK | |
| solution_step | 7,814 | 7,814 | 7,814 | 7,814 | OK | |
| step_dependency | 7,376 | 7,309 | — | 7,309 | OK | 163 `AMBIGUOUS_REPEATED_STEP_ID` dependencies skipped (NEXT 5,753 / DEPENDS_ON 1,556 imported). |
| learning_item | 11,186 | 11,186 | 11,186 (question + skill signature) | 11,186 | OK | All `APPROVED` and `student_visible` (auto-approval). |
| learning_item_anchor | — | 10,378 | — | 10,378 | OK | |
| raw problem_concepts / skills / techniques | 4,771 / 3,396 / 3,108 | — | — | — | PROVENANCE | Superseded by `problem_taxonomy_enriched.csv`. Registered with a hash in `ingest.package_file`, not imported. |
| raw `csv/transformations.csv` | 4,453 | — | — | — | PROVENANCE | Superseded by `transformations_v3_no_proof.csv`. |

Other conflicts recorded in `ingest.import_conflict` (visible on the Coverage tab):

| Conflict | Count |
|---|---:|
| `REPEATED_STEP_ID` | 140 |
| `REPEATED_PART_ID` | 81 |
| `STEP_COUNT_MISMATCH` | 47 |
| `DUPLICATE_TRANSFORMATION_ID` | 7 |
| `NAME_CONFLICT` | 1 |
| `DUPLICATE_TAXONOMY_ROW` | 1 |

**Conclusion:**

- Problems, solutions, steps, dependencies and transformations are fully present in Postgres, pgvector and Neo4j. Every shortfall against the source rows is an explained de-duplication or conflict.
- The real gaps are:
  - Taxonomy nodes have no vectors.
  - Diagrams are neither in the graph nor vectorised.
  - Chapter sections are not graph nodes.
  - Diagram files still live inside the requirements pack (§6).

## 4. Endpoints

All routes are under `/v1/admin/textbooks` and require the admin key. Default `book=PRASOLOV_PGV1`.

| Method/path | Purpose | Notes |
|---|---|---|
| GET `/coverage?book&graph=true` | Matrix, packages, files, conflicts, chapters | ~3 s with graph; `graph=false` skips Neo4j. |
| GET `/problems?chapter&q&node&has_diagram&has_solution&limit≤200&offset` | Paginated problems | `{total, limit, offset, items[]}`. |
| GET `/problems/{canonical_code}` | Full detail | 404 if unknown. Includes answers and hidden diagrams. |
| GET `/learning-items?transformation_type&chapter&q&limit&offset` | Paginated transformations | Includes `types[]` counts. |
| GET `/taxonomy?node_type&q&limit≤500&offset` | Paginated nodes | `node_type` ∈ DOMAIN, CONCEPT, SUBCONCEPT, SKILL, TECHNIQUE. |
| GET `/taxonomy/{node_id}` | Node detail | Edges capped at 500, problems at 50. |
| GET `/diagrams/{source_diagram_id}/image?book` | PNG | 404 if the row is missing, the file is missing or it resolves outside the repo root. |

Web proxy: `GET /api/rest/admin/textbooks/<same path>` (admin session; allowlisted paths; images streamed).

## 5. UI

- `/admin/textbooks` (link on `/admin`) has four tabs:
  - **Coverage**: cards, matrix, gaps alert, per-chapter table, packages and conflicts.
  - **Problems**: filters and a paginated table.
  - **Transformations**: type/chapter/text filters.
  - **Taxonomy**: type buttons, search and a node side panel.
  - The page supports `?tab=` and `?node=`.
- `/admin/textbooks/problems/{canonical_code}` has five tabs:
  - **Problem**: statement (KaTeX), concepts, taxonomy chips linking back to the filtered list, and source metadata.
  - **Solution & steps**: full solution plus parts → steps with dependency hints and per-step vector flags.
  - **Transformations**: cards by type with choices, the correct answer highlighted, the seed and anchors.
  - **Diagrams**: images with visibility badges.
  - **Store status**: pgvector counts and Neo4j edges/step reachability.

## 6. Gaps and follow-ups

The status column below is a snapshot; see [20](20_NOT_YET_IMPLEMENTED.md) for the live status.

- **NYI-ATB-1:** ✅ delivered. Taxonomy node embeddings exist (501/501); a retrieval API over them is still open.
- **NYI-ATB-7:** ✅ delivered ([25](25_LEARNING_ITEM_CONCEPT_EDGES.md)).
- **NYI-ATB-8…9:** usage-weighted taxonomy texts and the remaining v2 graph vocabulary (see [20](20_NOT_YET_IMPLEMENTED.md)).
- **NYI-ATB-2:** diagrams in the graph (`Problem-[:HAS_DIAGRAM]->Diagram` with visibility) and optional image/caption embeddings.
- **NYI-ATB-3 (blocker for deleting the pack):** all 250 `pedagogy.diagram.local_path` values point inside `math_tutor_new_requirements_copilot_pack_v2_expanded/GEOMETRY-TEXTBOOKS/*/diagrams/`. The files (~18 MB) must be copied to a durable asset location, and `local_path` updated, **before** the pack is deleted. Otherwise every admin and student diagram returns 404.
- **NYI-ATB-4:** chapter sections as graph nodes (`Paper-[:HAS_SECTION]->Section`) if section-level navigation is needed.
- **NYI-ATB-5:** 280 problems have no `technique_ids` in the source, and Power of a Point is tagged on only 1 problem (see NYI-WALK-1). Needs a re-tagging pass.
- **NYI-ATB-6:** the dashboard is read-only. Editing, re-import, conflict resolution and per-row re-embed/re-project actions are Phase 12 (admin import/reconciliation UI).

## 7. Tests

| Suite | Coverage |
|---|---|
| `mathbank-rest/tests/test_admin_textbooks.py` (13) | Every route needs the admin key; parameter validation; 404s; list pass-through; matrix statuses (OK/GAP/UNKNOWN/PROVENANCE); graph failure is non-fatal; diagram path refuses files outside the root. |
| `mathbank-web/tests/adminTextbooksProxy.test.mjs` (2) | Allowlist, clamping, bad ids/types, 401 without session, image streaming with private cache, upstream status preserved. |
| `mathbank-web/e2e/admin.spec.mjs` | Anonymous proxy 401 (JSON and image); `/admin/textbooks` renders; matrix plus 30 chapters; filter → problem 1.9 → statement, steps, transformations, diagram image loaded, store status. |

Run: `cd mathbank-rest && .venv/bin/python -m pytest -q tests/test_admin_textbooks.py`, `make -C mathbank-web test`, `make -C mathbank-web e2e`.
