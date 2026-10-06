# 21 — v2 Pack Implementation Coverage Audit

## Header

- **Purpose.** The pack under `math_tutor_new_requirements_copilot_pack_v2_expanded/` is planned for later deletion after its durable requirements are merged into `requirements/`. This audit, tracker [18](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md), and register [20](20_NOT_YET_IMPLEMENTED.md) must therefore carry every still-needed requirement.
- **Source revision.** `0925f37d82cc428202a12746df5112a3978c46b5` (`git HEAD`; worktree changes included).
- **Date.** 2026-10-05.
- **Evidence mode.** Source-derived only. Evidence cites repository paths; no DB writes, process changes, service restarts, paid model calls, or pack edits were used.

## Summary by unified execution phase

Method: each phase from `math_tutor_new_requirements_copilot_pack_v2_expanded/33_COPILOT_UNIFIED_EXECUTION_PLAN.md` and `runtime_extension/19_IMPLEMENTATION_PHASES.md` is given equal weight. Percent estimates are based on implemented source, tests, and the known remainders in [18](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md) and [20](20_NOT_YET_IMPLEMENTED.md). Overall weighted estimate: **79%** (mean of 13 equal phase scores; was 66% on 2026-10-05, raised on 2026-10-06 by doc [26](26_GEOMETRY_RUNTIME_COMPLETION_PLAN.md) WP1–WP4 for phases 5, 10, 11, 12).

| Phase | Pack phase requirement | Status | % | Evidence and rationale |
|---:|---|---:|---:|---|
| 0 | Repository reconnaissance / no duplicate models | ✅ done | 100 | Existing models extended additively: `mathbank-db/sql/010_textbook_import.sql`–`mathbank-db/sql/015_recovery_runtime.sql`; current map is documented in `requirements/reference/POSTGRES_SCHEMA.md`, `GRAPH_SCHEMA.md`, `REST_API.md`. |
| 1 | Original content/transformation model: learning items, versions, validation, review, publication, family/lineage | 🟡 partial | 35 | `pedagogy.learning_item` exists in `mathbank-db/sql/010_textbook_import.sql`; auto-approval metadata in `mathbank-db/sql/015_recovery_runtime.sql`; admin pedagogy review exists in `mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py`. No generated-item `LearningItemVersion`, `TransformationRun`, `ValidationResult`, item publication pointer, or problem-family API (NYI-AUD-1..5). |
| 2 | Textbook package import, staging, validation, reconciliation | ✅ done | 95 | `mathbank-db/sql/010_textbook_import.sql`; `mathbank-db/etl/import_textbook_package.py`; tests `mathbank-db/tests/test_textbook_import.py`. Remaining package lifecycle state `SUPERSEDED` is NYI-9; UI is Phase 11/NYI-P12. |
| 3 | Solution parts, steps, dependencies | ✅ done | 95 | `pedagogy.solution_part`, `solution_step`, `solution_step_dependency` in `mathbank-db/sql/010_textbook_import.sql`; importer and `mathbank-db/tests/test_textbook_import.py`; runtime traversal in `mathbank-rest/src/mathbank_rest/step_runtime.py`. Rich branch semantics remain Phase 12/NYI-P13. |
| 4 | Graph and vector projection | ✅ done | 90 | Graph projector `mathbank-graph/etl/project_textbook_steps.py`; vector schema `mathbank-db/sql/011_step_vector_metadata.sql`; embedder `mathbank-db/etl/embed_textbook_steps.py`; retrieval `mathbank-rest/src/mathbank_rest/db/step_search.py`; tests `mathbank-graph/tests/test_project_textbook_steps.py`, `mathbank-db/tests/test_embed_textbook_steps.py`, `mathbank-rest/tests/test_step_search.py`. Remainders: NYI-2, NYI-3, NYI-7. |
| 5 | Student attempt/event persistence | ✅ done | 95 | `mathbank-db/sql/012_step_runtime.sql`, `018_outbox_consumers.sql`; `mathbank-rest/src/mathbank_rest/step_runtime.py`, `outbox_worker.py`; tests `mathbank-rest/tests/test_step_runtime.py`, `test_outbox_worker.py`. Remainder: erasure (NYI-P6). |
| 6 | Student web UI | 🟡 partial | 80 | `mathbank-web/app/learn/solve/[code]/SolveWorkspace.jsx`; proxy tests `mathbank-web/tests/solveProxy.test.mjs`; flow helpers `mathbank-web/tests/solveFlow.test.mjs`. Remainders: equation editor, accessibility/mobile pass, step-solution figure reveal (NYI-P7). |
| 7 | Step evaluation and hints | 🟡 partial | 80 | `mathbank-db/sql/013_step_hints.sql`; `mathbank-rest/src/mathbank_rest/step_tutor.py`; route integration in `mathbank-rest/src/mathbank_rest/routers/step_runtime.py`; tests `mathbank-rest/tests/test_step_tutor.py`. Remainders: grader calibration, rubric, review/dispute paths, hint-quality review (NYI-P8). |
| 8 | Diagnosis | 🟡 partial | 75 | `mathbank-db/sql/014_gap_diagnosis.sql`; `mathbank-rest/src/mathbank_rest/step_diagnosis.py`; admin page `mathbank-web/app/admin/(protected)/knowledge-gaps/page.jsx`; tests `mathbank-rest/tests/test_step_diagnosis.py`, `mathbank-web/tests/adminGapsProxy.test.mjs`. Remainders: concept strength rollup and full LLM diagnosis (NYI-P9). |
| 9 | Recovery plan runtime | 🟡 partial | 80 | `mathbank-db/sql/015_recovery_runtime.sql`; `mathbank-rest/src/mathbank_rest/step_recovery.py`; UI in `mathbank-web/app/learn/solve/[code]/SolveWorkspace.jsx`; tests `mathbank-rest/tests/test_step_recovery.py`. Remainders: teacher-assigned route, spaced review, per-student tuning, generated practice (NYI-P10). |
| 10 | ADK agent integration for runtime APIs | 🟡 partial | 75 | 9 step-runtime tools in `mathbank-agent/agents/mathbank_tutor/tools/step_runtime_tools.py` with tests; remainder: chat panel in the solve workspace (NYI-P11). |
| 11 | Admin import/reconciliation UI | ✅ done | 90 | `/v1/admin/imports/*` + `/admin/imports` + DAG review + item review (doc [26](26_GEOMETRY_RUNTIME_COMPLETION_PLAN.md) WP3). Remainder: jobs-console rows (NYI-4). |
| 12 | Semantic DAG enrichment | 🟡 partial | 35 | Human edge editing/approval exists (WP3); no model-proposed rich edges yet (NYI-P13; NYI-11 for branch semantics). |

## Per-file implementation matrix

Status legend: ✅ done · 🟡 partial · ⏳ not started · ➖ n/a · ❌ deliberately not done.

| Pack file | Requires | Status | Implementing evidence | Gaps |
|---|---|---:|---|---|
| `math_tutor_new_requirements_copilot_pack_v2_expanded/00_INDEX.md` | Whole v2 architecture: content factory, runtime, ADK, UI, admin. | 🟡 partial | Broad implementation spans `mathbank-db/sql/010_textbook_import.sql`–`mathbank-db/sql/015_recovery_runtime.sql`, `mathbank-rest/src/mathbank_rest/step_*`, `mathbank-web/app/learn/solve/[code]/SolveWorkspace.jsx`. | NYI-P11, NYI-P12, NYI-P13; NYI-AUD-1..7. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/01_SCOPE_AND_NON_GOALS.md` | Textbook ingestion, enrichment, transformations, diagnosis/recovery; exclude LMS/payment/etc. | 🟡 partial | Textbook/runtime pieces in `mathbank-db/etl/import_textbook_package.py`, `mathbank-rest/src/mathbank_rest/step_diagnosis.py`, `mathbank-rest/src/mathbank_rest/step_recovery.py`. | Generated transformation engine and full validation/publication not done: NYI-AUD-1..5. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/02_BUSINESS_FLOW.md` | End-to-end authoring/import/review/publication/student remediation flow. | 🟡 partial | Import + auto-approval + student runtime: `mathbank-db/sql/010_textbook_import.sql`, `mathbank-db/sql/015_recovery_runtime.sql`, `mathbank-rest/src/mathbank_rest/routers/step_runtime.py`. | Human review/publish for generated items and admin import UI absent: NYI-1, NYI-P12, NYI-AUD-4, NYI-AUD-5. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/03_DOMAIN_MODEL.md` | Domain entities including LearningItemVersion, TransformationRun, ValidationResult, ReviewEvent. | 🟡 partial | `pedagogy.learning_item` in `mathbank-db/sql/010_textbook_import.sql`; `knowledge.pedagogy_review_event` exists for metadata review (`mathbank-db/sql/007_pedagogy_review.sql`). | Missing generated-item lifecycle entities: NYI-AUD-1. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/04_TEXTBOOK_INGESTION.md` | Safe source/canonical ingestion with provenance and no destructive import. | ✅ done | `mathbank-db/sql/010_textbook_import.sql`; `mathbank-db/etl/import_textbook_package.py`; `mathbank-db/tests/test_textbook_import.py`; gotchas GOT-SRC-* in [19](19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md). | Package lifecycle `SUPERSEDED` missing: NYI-9. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/05_LEARNING_ITEM_MODEL.md` | Learning item records, anchors, visibility gate, versions. | 🟡 partial | `pedagogy.learning_item`, `learning_item_step_anchor`, approval gate in `mathbank-db/sql/010_textbook_import.sql`; `mathbank-db/sql/015_recovery_runtime.sql` adds approval method. | No `LearningItemVersion`/published version pointer: NYI-AUD-1, NYI-AUD-5; human review UI NYI-1/NYI-P12. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/06_PROBLEM_FAMILY_AND_LINEAGE.md` | Acyclic source/derivative family lineage and lineage queries. | ⏳ not started | Imported items reference `source_problem_id` in `mathbank-db/sql/010_textbook_import.sql`. | No family/lineage graph/API/cycle guard for derivatives: NYI-AUD-2. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/07_TRANSFORMATION_ENGINE.md` | Generate new practice items from source problems through recipes. | ⏳ not started | Pre-generated Prasolov items are imported by `mathbank-db/etl/import_textbook_package.py`. | No in-repo generator for new items: NYI-AUD-3; generated items noted in NYI-P10. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/08_TRANSFORMATION_RECIPES.md` | Specific proof-to-calculation/MCQ/subproblem/transfer recipes. | 🟡 partial | Imported `transformation_type` and recovery stage selection in `mathbank-rest/src/mathbank_rest/step_recovery.py`; tests `mathbank-rest/tests/test_step_recovery.py`. | Recipes are data-imported, not generated/validated in repo: NYI-AUD-3; transfer diversity NYI-AUD-7. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/09_VALIDATION_PIPELINE.md` | Validators, thresholds, failure preservation, review routing. | ⏳ not started | SQL gates visibility (`learning_item_visible_requires_approval`) but not generator validation. | No generated-item validation-result pipeline: NYI-AUD-4. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/10_ADMIN_REVIEW_AND_APPROVAL.md` | Admin review, auto-approval policy, edit/reclassify, review events. | 🟡 partial | Metadata admin routes in `mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py`; `mathbank-web/app/admin/(protected)/pedagogy/page.jsx`; auto-approval SQL `mathbank-db/sql/ops/approve_learning_items_auto.sql`. | No learning-item review UI; generated-item review/versioning incomplete: NYI-1, NYI-P12, NYI-AUD-1, NYI-AUD-5. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/11_PUBLICATION_PIPELINE.md` | Draft/review/publish/supersede lifecycle and student visibility. | 🟡 partial | Student visibility gate in `mathbank-db/sql/010_textbook_import.sql`; graph publication for pedagogy metadata in `mathbank-rest/src/mathbank_rest/publication.py` and `mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py`. | No item-level publication pointer/SUPERSEDED lifecycle: NYI-AUD-5; package SUPERSEDED NYI-9. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/12_TAXONOMY_VECTOR_GRAPH_INTEGRATION.md` | Integrate taxonomy, graph, pgvector, and student-safe retrieval. | ✅ done | `mathbank-graph/etl/project_textbook_steps.py`, `mathbank-db/etl/embed_textbook_steps.py`, `mathbank-rest/src/mathbank_rest/db/step_search.py`, tests `mathbank-rest/tests/test_step_search.py`. | Item retrieval not exposed to agent: NYI-2; technique tags NYI-3. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/13_ATTEMPT_DIAGNOSIS.md` | Diagnose attempts and create knowledge gaps. | 🟡 partial | `mathbank-db/sql/014_gap_diagnosis.sql`; `mathbank-rest/src/mathbank_rest/step_diagnosis.py`; tests `mathbank-rest/tests/test_step_diagnosis.py`. | Mastery/strength rollup and full LLM diagnosis absent: NYI-P9. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/14_RECOVERY_ENGINE.md` | Persisted remediation plans with adaptive branching and return. | 🟡 partial | `mathbank-db/sql/015_recovery_runtime.sql`; `mathbank-rest/src/mathbank_rest/step_recovery.py`; `mathbank-web/app/learn/solve/[code]/SolveWorkspace.jsx`; tests `mathbank-rest/tests/test_step_recovery.py`. | Teacher trigger/spaced review/generated items: NYI-P10; diversity NYI-AUD-7. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/15_PRACTICE_SELECTION.md` | Select practice by skill, prerequisite, difficulty, misconception, diversity. | 🟡 partial | `mathbank-rest/src/mathbank_rest/db/step_search.py` hard filters; `mathbank-rest/src/mathbank_rest/step_recovery.py` selects approved learning items. | Near-duplicate/transfer diversity not fully enforced: NYI-AUD-7; generated items NYI-P10. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/16_POSTGRES_SCHEMA.md` | PostgreSQL schema for import, item lifecycle, runtime. | 🟡 partial | `mathbank-db/sql/010_textbook_import.sql`–`mathbank-db/sql/015_recovery_runtime.sql`; `requirements/reference/POSTGRES_SCHEMA.md`. | Missing content-factory lifecycle tables and package SUPERSEDED: NYI-AUD-1, NYI-AUD-5, NYI-9. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/17_GRAPH_PROJECTION.md` | Project graph metadata but keep review/lineage canonical in Postgres. | ✅ done | `mathbank-graph/etl/project_textbook_steps.py`; `mathbank-graph/etl/project_from_postgres.py`; `requirements/reference/GRAPH_SCHEMA.md`. | Rich inferred edges need review before backfill: NYI-P13. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/18_REST_API.md` | REST APIs for learning items, families, review, search/runtime. | 🟡 partial | Runtime routes in `mathbank-rest/src/mathbank_rest/routers/step_runtime.py`; admin routes in `routers/pedagogy_admin.py`; reference `requirements/reference/REST_API.md`. | No problem-family or transformation lifecycle API: NYI-AUD-2, NYI-AUD-5; runtime agent API NYI-P11. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/19_ADK_AGENT_TOOLS.md` | ADK tools wrap deterministic services. | ⏳ not started | Existing legacy tools in `mathbank-agent/agents/mathbank_tutor/tools/rest_tools.py`. | No Phase 6–10 runtime tools: NYI-P11. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/20_END_TO_END_EXAMPLES.md` | Demonstrate complete student/recovery flows. | 🟡 partial | Golden/live tests: `mathbank-rest/tests/test_step_runtime.py`, `mathbank-rest/tests/test_step_diagnosis.py`, `mathbank-rest/tests/test_step_recovery.py`; UI tests `mathbank-web/tests/solveFlow.test.mjs`. | Content-factory examples missing: NYI-AUD-3..5. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/21_TECH_STACK_AND_REPO.md` | Fit implementation into repo services and stack. | ✅ done | Code lives in `mathbank-db`, `mathbank-rest`, `mathbank-graph`, `mathbank-web`, `mathbank-agent` as specified. | New service modules for generation/lineage still absent: NYI-AUD-1..5. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/22_IMPLEMENTATION_PHASES.md` | Original content-factory implementation phases. | 🟡 partial | Textbook import implemented; learning items imported. | Most content-factory phases not complete: NYI-AUD-1..5. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/23_ACCEPTANCE_TESTS.md` | A–L content-factory acceptance tests. | 🟡 partial | Some gates covered by `mathbank-db/tests/test_textbook_import.py`, `mathbank-rest/tests/test_step_search.py`, `mathbank-rest/tests/test_step_recovery.py`. | Many A–L criteria missing/partial; see acceptance table below. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/24_WHAT_NOT_TO_DO.md` | Guardrails for source, versions, RAG, SQL, validation, recovery. | 🟡 partial | Most runtime/import guardrails enforced in SQL/routes/tests. | Version/publish/validation guardrails for generated items remain NYI-AUD-1, NYI-AUD-4, NYI-AUD-5. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/25_COPILOT_EXECUTION_INSTRUCTIONS.md` | Ordered build instructions and review checklist. | 🟡 partial | Phases 0–10 tracked in [18](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md). | Later phases NYI-P11..P13; content-factory items NYI-AUD-1..5. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/26_ARCHITECTURE_INTEGRATION_MAP.md` | Map requirements to existing architecture. | 🟡 partial | Reference docs under `requirements/reference/`; implementation paths above. | Missing modules named by pack for lineage/validation/publication: NYI-AUD-1..5. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/27_SOLUTION_STEP_ENRICHMENT.md` | Enrich steps with semantic DAG metadata. | 🟡 partial | Imported step dependencies in `mathbank-db/sql/010_textbook_import.sql`; graph supports rich types. | No model-assisted enrichment/review pipeline: NYI-P13; branch runtime NYI-11. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/28_POSTGRES_IMPORT_AND_RECONCILIATION.md` | Robust idempotent import/reconciliation. | ✅ done | `mathbank-db/etl/import_textbook_package.py`; `ingest.reconciliation` and conflicts in `mathbank-db/sql/010_textbook_import.sql`; `mathbank-db/tests/test_textbook_import.py`. | Admin UI absent: NYI-P12; lifecycle SUPERSEDED NYI-9. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/29_GRAPH_VECTOR_METADATA_V2.md` | Canonical graph/vector metadata for steps and learning items. | ✅ done | `mathbank-db/sql/011_step_vector_metadata.sql`; `mathbank-db/etl/embed_textbook_steps.py`; `mathbank-graph/etl/project_textbook_steps.py`; `step_search.py`. | NYI-2, NYI-3, NYI-7. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/30_STUDENT_RUNTIME_AND_EVENTS.md` | Attempt, event, state machine, optimistic concurrency. | 🟡 partial | `mathbank-db/sql/012_step_runtime.sql`; `mathbank-rest/src/mathbank_rest/step_runtime.py`; `mathbank-rest/tests/test_step_runtime.py`. | NYI-P6. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/31_RECOVERY_RUNTIME_AND_AGENT.md` | Recovery runtime plus agent orchestration. | 🟡 partial | Runtime in `mathbank-rest/src/mathbank_rest/step_recovery.py`; UI in `mathbank-web/app/learn/solve/[code]/SolveWorkspace.jsx`. | Agent orchestration NYI-P11; recovery remainders NYI-P10. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/32_STUDENT_WEB_UI_RUNTIME.md` | Solve workspace with diagrams, hints, recovery, refresh. | 🟡 partial | `mathbank-web/app/learn/solve/[code]/SolveWorkspace.jsx`; `mathbank-web/tests/solveFlow.test.mjs`, `mathbank-web/tests/solveProxy.test.mjs`. | NYI-P7. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/33_COPILOT_UNIFIED_EXECUTION_PLAN.md` | Combined execution order phases 0–12. | 🟡 partial | Summary table above. | Phases 10–12 not started; phase 1 partial. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/34_UNIFIED_ACCEPTANCE_CRITERIA.md` | Cross-cutting acceptance criteria. | 🟡 partial | Runtime/import criteria mostly tested; table below. | Agent and content-factory criteria partial/missing. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/35_COPILOT_REVIEW_CHECKLIST.md` | Final review checklist. | 🟡 partial | This audit plus [18](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md), [20](20_NOT_YET_IMPLEMENTED.md). | New NYI-AUD gaps below. |
| `math_tutor_new_requirements_copilot_pack_v2_expanded/README.md` | Pack reading order and package purpose. | ➖ n/a | Documentation index only. | Keep durable requirements via this audit/register before deletion. |
| `runtime_extension/00_INDEX.md` | Runtime extension index. | 🟡 partial | Runtime phases 1–9 implemented/partial in `step_*`, SQL 010–015, UI. | Runtime phases 10–12 NYI-P11..P13. |
| `runtime_extension/01_TARGET_ARCHITECTURE.md` | Target runtime architecture across DB, graph, REST, agent, UI. | 🟡 partial | DB/REST/UI/graph implemented; agent legacy only. | NYI-P11, NYI-P12, NYI-P13. |
| `runtime_extension/02_STEP_DAG_SEMANTICS.md` | Step DAG semantics including alternatives/joins/reused results. | 🟡 partial | Linear and imported dependency traversal in `mathbank-rest/src/mathbank_rest/step_runtime.py`; full edge vocabulary documented (migration 019); admin add/retype/reject + cycle-checked `DEPENDS_ON` + per-solution DAG approval in `mathbank-rest/src/mathbank_rest/db/import_admin.py` (doc 26 WP3). | Model-proposed rich edges NYI-P13; branch runtime NYI-11. |
| `runtime_extension/03_POSTGRES_RUNTIME_SCHEMA.md` | Runtime schema for attempts/events/state/recovery. | ✅ done (Prasolov) | `mathbank-db/sql/012_step_runtime.sql`, `014_gap_diagnosis.sql`, `015_recovery_runtime.sql`, `017_step_techniques.sql`, `018_outbox_consumers.sql`, `019_admin_import_review.sql`. | Learner erasure (NYI-P6); non-Prasolov rows empty by design (doc 26 §3). |
| `runtime_extension/04_IMPORT_PACKAGE_CONTRACT.md` | Contract for enriched import package. | ✅ done | `mathbank-db/etl/import_textbook_package.py`; `mathbank-db/tests/test_textbook_import.py`. | Future richer edge imports need review: NYI-P13. |
| `runtime_extension/05_METADATA_IMPORT_PIPELINE.md` | Import validation/upsert/reconciliation and lineage. | 🟡 partial | Import pipeline done; reconciliation, conflict decisions and human-edit protection via `/v1/admin/imports` (doc 26 WP3); source collisions in [19](19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md). | Derivative lineage absent: NYI-AUD-2; `SUPERSEDED` NYI-9. |
| `runtime_extension/06_GRAPH_PROJECTION_V2.md` | Project runtime graph v2. | ✅ done | `mathbank-graph/etl/project_textbook_steps.py`; `mathbank-graph/tests/test_project_textbook_steps.py`; `requirements/reference/GRAPH_SCHEMA.md`. | Rich inferred edges not generated/reviewed: NYI-P13. Project extension: `LearningItem -[:TARGETS_CONCEPT|TARGETS_SUBCONCEPT]->` ([25](25_LEARNING_ITEM_CONCEPT_EDGES.md)). |
| `runtime_extension/07_VECTOR_METADATA_AND_RAG.md` | Step/item vectors with hard filters. | ✅ done | `mathbank-db/sql/011_step_vector_metadata.sql`; `mathbank-db/etl/embed_textbook_steps.py`; `mathbank-rest/src/mathbank_rest/db/step_search.py`; tests `mathbank-db/tests/test_embed_textbook_steps.py`, `mathbank-rest/tests/test_step_search.py`. | Agent exposure NYI-2; technique tags NYI-3. |
| `runtime_extension/08_STUDENT_EVENT_MODEL.md` | Immutable student events. | ✅ done (except erasure) | Append-only `learner.event` (012); `PROBLEM_VIEWED`/`STEP_PRESENTED`/`HINT_PRESENTED`/`RECOVERY_ITEM_PRESENTED`/`ATTEMPT_ABANDONED` (018); consumers in `mathbank-rest/src/mathbank_rest/outbox_worker.py`; retention policy in doc 26 WP4. | Erasure endpoint: NYI-P6. |
| `runtime_extension/09_STEP_PROGRESS_STATE.md` | Step state machine and exact current step. | ✅ done | `attempt_step_state` in `mathbank-db/sql/012_step_runtime.sql`; `outcome_transition`/`next_step` in `mathbank-rest/src/mathbank_rest/step_runtime.py`; `mathbank-rest/tests/test_step_runtime.py`. | Alternative branch semantics NYI-11. |
| `runtime_extension/10_ATTEMPT_DIAGNOSIS_RUNTIME.md` | Diagnosis runtime and probes. | 🟡 partial | `mathbank-rest/src/mathbank_rest/step_diagnosis.py`; learning-item probes in `mathbank-rest/src/mathbank_rest/step_recovery.py`; tests `mathbank-rest/tests/test_step_diagnosis.py`, `mathbank-rest/tests/test_step_recovery.py`. | NYI-P9. |
| `runtime_extension/11_RECOVERY_PLAN_RUNTIME.md` | Persisted recovery plans, adaptation, return. | 🟡 partial | `mathbank-db/sql/015_recovery_runtime.sql`; `mathbank-rest/src/mathbank_rest/step_recovery.py`; `mathbank-rest/tests/test_step_recovery.py`. | NYI-P10, NYI-AUD-7. |
| `runtime_extension/12_TUTOR_AGENT_CONTEXT.md` | Agent reads runtime state and acts through APIs. | 🟡 partial | 9 tools in `mathbank-agent/agents/mathbank_tutor/tools/step_runtime_tools.py` (state_version + idempotency, temp-state token); `mathbank-agent/tests/test_step_runtime_tools.py`. | Chat panel inside the solve workspace (NYI-P11 / doc 26 WP6). |
| `runtime_extension/13_REST_API_RUNTIME.md` | Runtime REST endpoints. | 🟡 partial | `mathbank-rest/src/mathbank_rest/routers/step_runtime.py` (attempts, responses, hints, diagnoses, recovery); admin `routers/admin_imports.py`; agent tool surface (WP2). | Teacher detour trigger: NYI-P10. |
| `runtime_extension/14_STUDENT_WEB_UI.md` | Student solve UI. | 🟡 partial | `mathbank-web/app/learn/solve/[code]/SolveWorkspace.jsx`; `mathbank-web/tests/solveFlow.test.mjs`; `mathbank-web/tests/solveProxy.test.mjs`. | NYI-P7. |
| `runtime_extension/15_ADMIN_IMPORT_UI.md` | Admin import/reconciliation/review UI. | ✅ done (Prasolov) | `mathbank-rest/src/mathbank_rest/routers/admin_imports.py`, `db/import_admin.py`, migration 019; web `/admin/imports`, DAG-review tab and item Approve/Reject; `mathbank-rest/tests/test_admin_imports.py`, `mathbank-web/tests/adminImportsProxy.test.mjs`, `mathbank-web/e2e/admin.spec.mjs`. | Jobs-console rows NYI-4. |
| `runtime_extension/16_EVENTING_AND_IDEMPOTENCY.md` | Idempotency, optimistic locking, outbox. | ✅ done | `idempotency_record`, `state_version`, `outbox_event` (012); `outbox_consumption`, `projection_request` (018) with idempotent consumers in `outbox_worker.py`; stale-attempt job. | — |
| `runtime_extension/17_SECURITY_AND_VISIBILITY.md` | Hide future solutions; student/admin separation. | ✅ done | `mathbank-rest/src/mathbank_rest/step_runtime.py` student payload filter; `mathbank-rest/src/mathbank_rest/routers/step_runtime.py` auth; tests `mathbank-rest/tests/test_step_tutor.py`, `mathbank-rest/tests/test_step_diagnosis.py`, `mathbank-web/tests/solveProxy.test.mjs`. | Step diagrams reveal after completion NYI-P7. |
| `runtime_extension/18_TESTING_AND_GOLDEN_FLOWS.md` | Golden flows A–J. | 🟡 partial | Tables below cite tests; admin e2e covers import/reconciliation/DAG review. | Semantic DAG branch flow J missing: NYI-P13/NYI-11. |
| `runtime_extension/19_IMPLEMENTATION_PHASES.md` | Runtime phases 1–12. | 🟡 partial | Summary table above. | Phase 12 (rich DAG) not started; phase 10 lacks the solve-page chat. |
| `runtime_extension/20_COPILOT_MASTER_INSTRUCTIONS.md` | Master instructions for safe ordered implementation. | 🟡 partial | Implementation followed additive/read-only checks in current work; tracker/register document status. | Later phases remain. |
| `runtime_extension/21_COPILOT_PROMPT_SEQUENCE.md` | Prompt sequence for runtime implementation. | 🟡 partial | Phases 1–9 implemented/partial as above. | Agent/admin/DAG prompts not complete: NYI-P11..P13. |
| `runtime_extension/22_WHAT_NOT_TO_DO.md` | Runtime-specific guardrails. | 🟡 partial | Compliance table below. | Near-duplicate/diversity only partial: NYI-AUD-7. |
| `runtime_extension/README.md` | Runtime extension reading order. | ➖ n/a | Documentation index only. | Keep durable requirements via audit/register. |

## New gaps proposed by this audit

> **Merged into [20](20_NOT_YET_IMPLEMENTED.md) §4 (NYI-AUD-1…7) on 2026-10-05.** The register is now authoritative; this table is the audit-time snapshot.

| ID | Gap | Source pack refs | Why existing register does not fully carry it |
|---|---|---|---|
| NYI-AUD-1 | Generated-item lifecycle entities: `LearningItemVersion`, `TransformationRun`, `ValidationResult`, and item-level `ReviewEvent` for generated practice. | `math_tutor_new_requirements_copilot_pack_v2_expanded/03_DOMAIN_MODEL.md`, `05_LEARNING_ITEM_MODEL.md`, `09_VALIDATION_PIPELINE.md`, `10_ADMIN_REVIEW_AND_APPROVAL.md` | [20](20_NOT_YET_IMPLEMENTED.md) covers learning-item review UI, but not these durable generated-item lifecycle entities. |
| NYI-AUD-2 | Problem family and acyclic transformation lineage query/API. | `math_tutor_new_requirements_copilot_pack_v2_expanded/06_PROBLEM_FAMILY_AND_LINEAGE.md`, `18_REST_API.md`, `25_COPILOT_EXECUTION_INSTRUCTIONS.md` | Current schema has `source_problem_id` only; no family endpoint/cycle guard is registered. |
| NYI-AUD-3 | In-repo transformation engine and recipes for generating new practice items. | `math_tutor_new_requirements_copilot_pack_v2_expanded/07_TRANSFORMATION_ENGINE.md`, `08_TRANSFORMATION_RECIPES.md` | [20](20_NOT_YET_IMPLEMENTED.md) says recovery uses imported items only, but does not carry the full recipe engine requirement. |
| NYI-AUD-4 | Generated-item validation pipeline and persisted validation results before auto-approval/publication. | `math_tutor_new_requirements_copilot_pack_v2_expanded/09_VALIDATION_PIPELINE.md`, `23_ACCEPTANCE_TESTS.md` D/E, `24_WHAT_NOT_TO_DO.md` #7 | Visibility gates exist, but validator thresholds/results are not registered. |
| NYI-AUD-5 | Item publication pipeline with draft/published/superseded versions and final reclassification after admin edits. | `math_tutor_new_requirements_copilot_pack_v2_expanded/10_ADMIN_REVIEW_AND_APPROVAL.md`, `11_PUBLICATION_PIPELINE.md`, `23_ACCEPTANCE_TESTS.md` C/F | NYI-9 covers package SUPERSEDED only, not item-level publication/version pointers. |
| NYI-AUD-6 | Source-fragment correction/version audit: raw source unchanged while canonical corrections remain traceable. | `math_tutor_new_requirements_copilot_pack_v2_expanded/04_TEXTBOOK_INGESTION.md`, `23_ACCEPTANCE_TESTS.md` A | Import preserves source rows, but an explicit correction/version workflow is not carried. |
| NYI-AUD-7 | Practice diversity/transfer guarantee: transfer item must not be an exact paraphrase; avoid endless near-duplicates. | `math_tutor_new_requirements_copilot_pack_v2_expanded/23_ACCEPTANCE_TESTS.md` I, `24_WHAT_NOT_TO_DO.md` #9, `15_PRACTICE_SELECTION.md` | Recovery has transfer stages, but no duplicate/diversity validator is registered. |

## Requirements not yet carried into `requirements/`

These concrete pack requirements are not preserved with enough specificity in `requirements/` 00–20 and would be lost or weakened if the pack were deleted.

1. **Generated-item lifecycle entities** — `LearningItemVersion`, `TransformationRun`, `ValidationResult`, item `ReviewEvent` (`03_DOMAIN_MODEL.md`, `05_LEARNING_ITEM_MODEL.md`, `09_VALIDATION_PIPELINE.md`).
2. **Problem family and acyclic lineage API** — every derivative belongs to a queryable family and ancestor/descendant cycles fail (`06_PROBLEM_FAMILY_AND_LINEAGE.md`, `18_REST_API.md`, `23_ACCEPTANCE_TESTS.md` K).
3. **Transformation engine/recipe idempotency** — recipes generate distinct practice items, keep source links, and repeat runs do not silently duplicate equivalent jobs (`07_TRANSFORMATION_ENGINE.md`, `08_TRANSFORMATION_RECIPES.md`, `23_ACCEPTANCE_TESTS.md` B/L).
4. **Validation-before-auto-approval** — auto-approval is policy after required validators pass; failing candidates preserve raw generation and do not publish (`09_VALIDATION_PIPELINE.md`, `10_ADMIN_REVIEW_AND_APPROVAL.md`, `23_ACCEPTANCE_TESTS.md` D/E, `24_WHAT_NOT_TO_DO.md` #7).
5. **Item publication/version pointer** — admin edits create new versions, final classification and embeddings use final text, and superseded versions stay hidden by default (`11_PUBLICATION_PIPELINE.md`, `23_ACCEPTANCE_TESTS.md` C/F/G).
6. **Canonical correction audit** — raw source fragment remains unchanged while corrected canonical text has provenance to source/page (`23_ACCEPTANCE_TESTS.md` A).
7. **Practice diversity and transfer non-paraphrase** — recovery practice must vary structure and transfer must not be an exact paraphrase (`15_PRACTICE_SELECTION.md`, `23_ACCEPTANCE_TESTS.md` I, `24_WHAT_NOT_TO_DO.md` #9).

## Acceptance criteria and golden-flow check

### `23_ACCEPTANCE_TESTS.md`

| Criterion | Status | Covering test/evidence | Notes |
|---|---:|---|---|
| A. Source preservation | 🟡 partial | `mathbank-db/tests/test_textbook_import.py` | Import preserves raw/staging/provenance, but canonical correction workflow NYI-AUD-6. |
| B. Multiple transformations | 🟡 partial | `mathbank-db/tests/test_textbook_import.py::test_learning_items_are_review_gated_and_anchor_split` | Imported pre-generated items reference source; no generator creating 5 items: NYI-AUD-3. |
| C. Versioning | ⏳ missing | none found for learning-item versions | NYI-AUD-1, NYI-AUD-5. |
| D. Auto approval | 🟡 partial | `mathbank-rest/tests/test_automatic_approval_live.py`; `mathbank-db/sql/ops/approve_learning_items_auto.sql` | Auto-approval exists for imported items; validation thresholds/results absent: NYI-AUD-4. |
| E. Auto approval failure | ⏳ missing | none found for generated item validator failure | NYI-AUD-4. |
| F. Admin edit requires reclassification | 🟡 partial | `mathbank-rest/tests/test_pedagogy_admin.py`, `test_automatic_approval_live.py` | Covers pedagogy metadata, not generated learning item versions: NYI-AUD-5. |
| G. Student retrieval isolation | ✅ pass | `mathbank-rest/tests/test_step_search.py::test_learning_item_search_always_requires_published_no_proof`; SQL visibility checks | Student search excludes unapproved/non-visible/proof learning items. |
| H. Recovery loop | ✅ pass | `mathbank-rest/tests/test_step_recovery.py::test_build_plan_orders_stages_and_ends_with_return`; live recovery tests | Uses approved imported items. |
| I. Transfer not paraphrase | 🟡 partial | `mathbank-rest/tests/test_step_recovery.py::test_build_plan_orders_stages_and_ends_with_return` | Transfer stage exists; no paraphrase/near-duplicate validator: NYI-AUD-7. |
| J. Return to original | ✅ pass | `mathbank-rest/tests/test_step_recovery.py::test_live_recovery_completes_and_returns_to_exact_step` | Exact step return covered. |
| K. Lineage cycle | ⏳ missing | none found for transformation lineage | NYI-AUD-2. |
| L. Idempotent recipe | 🟡 partial | `mathbank-db/tests/test_textbook_import.py` for import idempotence | Recipe/job idempotency not implemented: NYI-AUD-3. |

### `34_UNIFIED_ACCEPTANCE_CRITERIA.md`

| Criterion | Status | Covering test/evidence | Notes |
|---|---:|---|---|
| Content lineage | 🟡 partial | `mathbank-db/tests/test_textbook_import.py`; `mathbank-db/sql/010_textbook_import.sql` | Source links exist; versions/history missing: NYI-AUD-1/2/5. |
| Transformation | 🟡 partial | `mathbank-db/tests/test_textbook_import.py`; `mathbank-rest/tests/test_step_recovery.py` | Imported no-proof items only; no generator: NYI-AUD-3. |
| Import | ✅ pass | `mathbank-db/tests/test_textbook_import.py`; tracker [18](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md) idempotent rerun | No duplicate canonical rows for package import. |
| Step DAG | ✅ pass | `mathbank-db/tests/test_textbook_import.py::test_dependency_dag_rejects_self_loops_cycles_and_missing_endpoints`; `mathbank-rest/tests/test_step_runtime.py` | Simple dependency semantics covered. |
| Graph | ✅ pass | `mathbank-graph/tests/test_project_textbook_steps.py` | Projection reconciliation/replay covered. |
| Vector | ✅ pass | `mathbank-db/tests/test_embed_textbook_steps.py`; `mathbank-rest/tests/test_step_search.py` | Hard filters, visibility, no-proof checks covered. |
| Student runtime | ✅ pass | `mathbank-rest/tests/test_step_runtime.py::test_live_golden_flows`; `mathbank-web/tests/solveFlow.test.mjs` | Refresh/resume covered in backend and UI helpers. |
| Hint behavior | ✅ pass | `mathbank-rest/tests/test_step_runtime.py`; `mathbank-rest/tests/test_step_tutor.py`; `mathbank-web/tests/solveFlow.test.mjs` | Help success not independent; hint ladder tested. |
| Recovery | ✅ pass | `mathbank-rest/tests/test_step_recovery.py` live tests | Persisted plan and exact return covered. |
| Hidden solution | ✅ pass | `mathbank-rest/tests/test_step_tutor.py::test_step_goal_never_contains_step_text`; `mathbank-rest/tests/test_step_diagnosis.py` student-view tests; `mathbank-web/tests/solveProxy.test.mjs` | Future solution text not returned to student payloads. |
| Agent | ⏳ missing | `mathbank-agent/agents/mathbank_tutor/tools/rest_tools.py` only legacy tools | Runtime tools absent: NYI-P11. |

### `runtime_extension/18_TESTING_AND_GOLDEN_FLOWS.md`

| Flow | Status | Covering test/evidence | Notes |
|---|---:|---|---|
| A. Import package | ✅ pass | `mathbank-db/tests/test_textbook_import.py`; tracker [18](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md) | Import, dependencies, hidden pending items, idempotency covered. |
| B. Graph projection | ✅ pass | `mathbank-graph/tests/test_project_textbook_steps.py`; `mathbank-graph/etl/project_textbook_steps.py` | Projection tagging/replay covered. |
| C. Student independent success | ✅ pass | `mathbank-rest/tests/test_step_runtime.py::test_live_golden_flows` | Event, state, help=0, advance covered. |
| D. Hint success | ✅ pass | `mathbank-rest/tests/test_step_runtime.py::test_live_golden_flows`; `mathbank-rest/tests/test_step_tutor.py::test_live_hint_ladder_cache_and_evaluated_outcome` | Hint event and success-with-help covered. |
| E. Recovery trigger | ✅ pass | `mathbank-rest/tests/test_step_diagnosis.py::test_live_diagnosis_golden_flow`; `mathbank-rest/tests/test_step_recovery.py::test_live_diagnosis_detour_with_learning_item_probes_and_gap_outcome` | Gap and plan persisted. |
| F. Recovery adaptation | ✅ pass | `mathbank-rest/tests/test_step_recovery.py::test_live_recovery_adapts_on_failure_and_abort_returns` | Branch/adapt history covered. |
| G. Return | ✅ pass | `mathbank-rest/tests/test_step_recovery.py::test_live_recovery_completes_and_returns_to_exact_step` | Completion and return event covered. |
| H. Browser refresh | 🟡 partial | `mathbank-web/tests/solveFlow.test.mjs`; `mathbank-web/tests/solveProxy.test.mjs`; backend `get_runtime`/`get_plan` routes | Helper/proxy coverage; no full browser test in repo. |
| I. Hidden solution | ✅ pass | `mathbank-rest/tests/test_step_tutor.py`, `mathbank-rest/tests/test_step_diagnosis.py`, `mathbank-web/tests/solveProxy.test.mjs` | Student payload filters tested. |
| J. Semantic DAG branch | ⏳ missing | none found | NYI-P13/NYI-11. |

## What-not-to-do compliance

### `24_WHAT_NOT_TO_DO.md`

| Rule | Compliance | Evidence |
|---|---:|---|
| Do not overwrite source textbook content. | ✅ compliant | Raw/staging import and conflicts in `mathbank-db/sql/010_textbook_import.sql`; importer preserves source metadata. |
| Do not overwrite generated versions. | 🟡 partial | No generated-item versioning exists; metadata review events preserve snapshots in `mathbank-db/sql/007_pedagogy_review.sql`. NYI-AUD-1/5. |
| Do not model every derivative as a version. | ✅ compliant | Imported transformations are distinct `pedagogy.learning_item` rows, not problem versions. |
| Do not put every draft into pgvector/student RAG. | ✅ compliant | `step_search.py` requires `APPROVED`, `student_visible`, `no_proof`; `mathbank-rest/tests/test_step_search.py`. |
| Do not use similarity search as the full pedagogical strategy. | 🟡 partial | `mathbank-rest/src/mathbank_rest/step_recovery.py` uses skill/stage/mastery policy; diversity/prereq tuning incomplete (NYI-AUD-7, NYI-P10). |
| Do not let LLM generate raw SQL. | ✅ compliant | Routes call typed service functions; agent tools call REST in `rest_tools.py`. |
| Do not let auto-approval skip validation. | 🟡 partial | Visibility gates exist; no generated validation pipeline/results: NYI-AUD-4. |
| Do not assume chapter order is only prerequisite order. | 🟡 partial | Imported `DEPENDS_ON` and graph prerequisites used; rich enrichment not done: NYI-P13. |
| Do not generate endless near-duplicate practice. | 🟡 partial | Recovery selects staged items; no near-duplicate validator: NYI-AUD-7. |
| Do not reveal original solution merely because student is stuck. | ✅ compliant | Diagnosis/recovery detour in `mathbank-rest/src/mathbank_rest/step_diagnosis.py`/`mathbank-rest/src/mathbank_rest/step_recovery.py`; hidden-solution tests. |
| Do not treat one failed attempt as permanent mastery evidence. | ✅ compliant | `knowledge_gap` hypothesis status and recovery outcome in `014`/`015`; admin page notes no direct mastery write. |
| Do not publish before final classification. | 🟡 partial | Metadata publish separated; item final reclassification pipeline absent: NYI-AUD-5. |
| Do not project raw generation/review history into Neo4j. | ✅ compliant | Review/history remain PostgreSQL; graph projectors write public/reviewed metadata only. |
| Do not add separate taxonomies per book. | ✅ compliant | Import maps nodes into canonical taxonomy in `mathbank-db/etl/import_textbook_package.py`; gotchas GOT-SRC-8. |
| Do not regenerate everything when one pipeline stage fails. | 🟡 partial | Import/status records exist; generated transformation pipeline absent: NYI-AUD-3/4. |

### `runtime_extension/22_WHAT_NOT_TO_DO.md`

| Rule | Compliance | Evidence |
|---|---:|---|
| Do not load CSV straight into production tables. | ✅ compliant | Staging/content package tables in `mathbank-db/sql/010_textbook_import.sql`; `mathbank-db/etl/import_textbook_package.py`. |
| Do not treat display names as stable taxonomy IDs. | ✅ compliant | Canonical node IDs/slugs used; conflicts recorded in import gotchas. |
| Do not overwrite admin-reviewed content with a later import. | ✅ compliant | Learning-item visibility/review gates; review decisions protected in tests and [20](20_NOT_YET_IMPLEMENTED.md) NYI-1 detail. |
| Do not make graph import the canonical import. | ✅ compliant | Postgres import is canonical; graph projector reads from Postgres. |
| Do not equate `NEXT` with `DEPENDS_ON`. | ✅ compliant | Separate relationship types in `solution_step_dependency`; `mathbank-rest/src/mathbank_rest/step_runtime.py` gates only hard dependencies. |
| Do not chain separate solution parts unless logically required. | ✅ compliant | Import/test preserve separate parts; NYI-11 notes Prasolov parts are required without cross-part deps. |
| Do not expose all future step text to student browser. | ✅ compliant | `mathbank-rest/src/mathbank_rest/step_runtime.py` docstring and filters; hidden-solution tests. |
| Do not mark full-reveal completion as independent success. | ✅ compliant | SQL CHECK in `mathbank-db/sql/012_step_runtime.sql`; `outcome_transition` maps help>0 to with-help. |
| Do not store only a chat transcript. | ✅ compliant | `solve_attempt`, `attempt_step_state`, `learner.event`, `runtime_state` in `012`. |
| Do not store only problem correct/incorrect. | ✅ compliant | Per-step state/evaluation/hints persisted. |
| Do not lose the exact failed step. | ✅ compliant | Diagnosis/recovery rows store `solution_step_id`/origin step; tests verify exact return. |
| Do not keep recovery state only in agent memory. | ✅ compliant | `recovery_plan` and `recovery_plan_item` in `015`. |
| Do not overwrite immutable events. | ✅ compliant | Append-only trigger in `012`; `test_live_events_are_append_only`. |
| Do not let the LLM update PostgreSQL directly. | ✅ compliant | REST/service layer owns writes; agent tools are REST calls. |
| Do not let the LLM choose arbitrary graph queries. | ✅ compliant | Agent tools expose bounded endpoints, not arbitrary Cypher/SQL. |
| Do not infer authorization from conversation. | ✅ compliant | JWT/admin key dependencies in `mathbank-rest/src/mathbank_rest/routers/step_runtime.py`; proxy tests. |
| Do not let model invent current progress when REST state exists. | ⏳ n/a/partial | Runtime REST exists, but ADK tools not wired (NYI-P11). |
| Do not immediately reveal next solution step after prerequisite gap. | ✅ compliant | Diagnosis recommends detour/probes; recovery UI and runtime hide future steps. |
| Do not use only vector similarity for remediation. | 🟡 partial | Recovery uses staged learning items and skill filters; broader prerequisite/diversity policy incomplete. |
| Do not generate proof-based transformed items in this pipeline. | ✅ compliant | `no_proof` CHECK and search visibility filters in `010`/`step_search.py`. |
| Do not repeatedly serve near-duplicate exercises. | 🟡 partial | Not fully enforced: NYI-AUD-7. |
| Do not encode pedagogical business logic only in React state. | ✅ compliant | Server-side runtime, diagnosis, and recovery services drive UI. |
| Do not trust client-computed completion. | ✅ compliant | Server routes require `state_version` and compute transitions. |
| Do not treat page refresh as a new attempt. | ✅ compliant | `start_attempt` resumes open attempt; runtime reload routes. |
| Do not send admin/review metadata to ordinary student endpoints. | ✅ compliant | Student views redact evidence; admin routes require admin key; tests in `mathbank-rest/tests/test_step_diagnosis.py`, `mathbank-web/tests/solveProxy.test.mjs`. |
| Do not dual-write graph + PostgreSQL without outbox/retry strategy. | 🟡 partial | `pipeline.outbox_event` exists; consumer/retry not built: NYI-P6. |
| Do not make retries create duplicate student submissions. | ✅ compliant | `learner.idempotency_record`; route idempotency tests. |
