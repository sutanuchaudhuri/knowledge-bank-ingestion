# 20 — Not Yet Implemented Register

What the v2 pack (`math_tutor_new_requirements_copilot_pack_v2_expanded/`) and earlier requirements ask for that is **not** built or not finished yet. This is the honest counterpart to the progress tracker [18](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md); pitfalls are in [19](19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md). Every row names the spec source and the next concrete step.

Status legend: ⏳ not started · 🟡 partial · ⛔ blocked on a decision or on data · ➖ not applicable to current data.
IDs use the prefix `NYI-`. When an item is delivered, move it to the tracker's change log and delete it here.

Last verified against Neon and the code: 2026-10-05.

## 1. v2 runtime phases (pack order)

| ID | Phase / capability | Status | Spec | What exists today | Next step |
|---|---|---|---|---|---|
| NYI-P6 | Phase 6 remainder: learner-data erasure on request | 🟡 | runtime_extension/08, 16 | **Delivered** (doc [26](26_GEOMETRY_RUNTIME_COMPLETION_PLAN.md) WP4, migration 018): outbox consumers `learner_analytics` + `projection_requests` with `outbox_consumption` idempotency, `PROBLEM_VIEWED`/`STEP_PRESENTED`/`HINT_PRESENTED`/`RECOVERY_ITEM_PRESENTED` events, `ATTEMPT_ABANDONED` stale-attempt job, retention policy (append-only, kept indefinitely) | Erasure endpoint deleting one student across learner/analytics tables in one transaction |
| NYI-P7 | Phase 7 remainder: step-diagram rendering for solution figures, MathText-quality step input (equation editor), accessibility audit, mobile layout check | 🟡 | runtime_extension/14; pack 32 | **Delivered** (tracker 18 §Phase 7): `/learn/solve/{code}` with hint ladder, timeline, restore, diagrams, practice | Show `SOLUTION_HIDDEN` figures once a step is done; keyboard/screen-reader pass |
| NYI-P8 | Phase 8 remainder: grader calibration, rubric per step type, teacher review of disputed grades, hint quality review | 🟡 | runtime_extension/10; pack 13 | **Delivered** (tracker 18 §Phase 8): server-side grader, hint ladder with cache and leak guard | Gold set of graded responses to measure agreement; admin view of `last_evaluation`; student "dispute" path |
| NYI-P9 | Phase 9 remainder: per-concept strength/weakness rollup from gaps; full LLM diagnosis (beyond re-ranking) | 🟡 | runtime_extension/10; pack 13 | **Delivered** (tracker 18 §Phase 9, §Phase 10): `rules-v1` diagnoser, auto trigger, hypothesis lifecycle, learning-item probes first, admin page `/admin/knowledge-gaps` (`GET /v1/admin/knowledge-gaps`), optional AI re-rank (`DIAGNOSIS_LLM_RERANK=1`, reorder-only) | Gaps do not yet feed `learner.mastery` or the concept strength/weakness score; the model may only reorder rules-v1 hypotheses, never invent new ones |
| NYI-P10 | Recovery remainder: teacher-assigned detours (`TUTOR` trigger has no route), spaced review after a detour, per-student policy tuning, generated (not imported) items | 🟡 | runtime_extension/11; pack 14, 31 | **Delivered** (tracker 18 §Phase 10): migration 015, `step_recovery.py`, 8 routes, staged plan with adaptation/branch, mastery policy, exact-step return, detour UI, admin plan view; browser-verified | SUBPROBLEM_FIRST_MOVE / NEXT_INTERMEDIATE seeds can leak the expected result into the question (GOT-REC-2); items come only from the imported package |
| NYI-P11 | ~~Google ADK agent tools for the step runtime~~ — remainder: chat panel inside the solve workspace (WP6) | 🟡 | runtime_extension/12; pack 19, 31 | **Delivered** (doc 26 WP2): 9 tools in `mathbank-agent/agents/mathbank_tutor/tools/step_runtime_tools.py` over the deterministic REST runtime; token as ADK temp state, never persisted | Embed the tutor chat in `/learn/solve/{code}` bound to the current attempt |
| NYI-P12 | ~~Admin import / reconciliation UI and learning-item review UI~~ | ✅ | runtime_extension/15; pack 10, 28 | **Delivered** (doc 26 WP3, migration 019): `/v1/admin/imports/*`, `/admin/imports`, DAG-review tab and item Approve/Reject on the problem page, audited in `ingest.admin_review_action`, projection queue drain | Move to the tracker change log on the next audit |
| NYI-P13 | Rich non-linear DAG enrichment (beyond the imported 7,309 edges) | ⏳ | runtime_extension/02; pack 27 | Imported linear `NEXT` + `DEPENDS_ON` edges, cycle-checked; admins can now add, retype and reject edges and approve a DAG (doc 26 WP3) | Model-proposed edges (paid) with an independent verifier (doc 26 WP7) |

## 2. Gaps inside delivered phases

| ID | Gap | Status | Spec | Detail / next step |
|---|---|---|---|---|
| NYI-1 | Human review of learning items | ✅ | pack 05, 10 | All 11,186 items remain **auto-approved**; admins can now Approve/Reject each item on `/admin/textbooks/problems/{code}` → Transformations (`approval_method='human'`, never overwritten by re-import; rejection hides from students and prunes the graph node). Bulk queue view is optional future work. |
| NYI-2 | Learning-item retrieval is not exposed to the agent | 🟡 | runtime_extension/07, 13 | Items are now used by diagnosis probes and recovery plans (SQL by skill/subconcept). Vector search over items (`search_learning_items`) still has no REST route or agent tool; all 22,372 item vectors are embedded and 11,186 `:LearningItem` nodes are in Aura. Add it with Phase 11. |
| NYI-3 | Step-level technique tags | 🟡 | runtime_extension/06, 07 | **Rule tier delivered** (doc 26 WP1, migration 017): 4,354 tags on 3,397 / 7,814 Prasolov steps, projected as `(:SolutionStep)-[:USES_TECHNIQUE]->`. Remaining: paid `--llm` tier for the 3,490 `NO_MATCH` steps (needs approval); non-Prasolov corpora are empty by design (doc 26 §3). |
| NYI-4 | Admin "jobs" console does not show textbook packages / step graph / step vectors as competition rows | 🟡 | doc 16 | Results are recorded in `ingest.content_package.report` (`graph_projection`, `vector_projection`) and `pipeline.graph_projection`; surface them in the console. |
| NYI-5 | Hybrid search year filter excludes textbook problems | 🟡 | doc 16 | Textbook edition has `year NULL` (GOT-PG-6). Decide whether a year filter should include undated sources. |
| NYI-7 | Batched embedding inserts | ⏳ | — | Embedding inserts are one row per round trip (GOT-VEC-5). A batched `executemany`/COPY would cut backfill time. |
| NYI-8 | Legacy `core.solution_step` table removal | ⏳ | — | Empty legacy table (GOT-PG-5); needs a dedicated migration once nothing references it. |
| NYI-9 | `ingest.content_package` lifecycle has no SUPERSEDED state | ⏳ | pack 28 | Re-imports update in place; a new package version replacing an old one is not modelled yet. |
| NYI-10 | Host-independent image paths | ⏳ | — | `core.problem_image.local_path` is absolute (GOT-PG-7). |
| NYI-11 | Alternative solution branches / `required` part semantics | ➖ n/a for Prasolov | runtime_extension/09 | Every Prasolov problem has exactly one solution. Its parts (MAIN, A–F) are all required sub-questions with no cross-part dependencies, so the runtime walks all steps in order. Revisit for sources that have multiple solutions. |
| NYI-12 | ~~`recovery_plan_id` FK and the DETOURED step state are unused~~ | ✅ | runtime_extension/11 | Wired by migration 015 and `step_recovery.py` (Phase 10). |

## 3. Data / operations backlog (verified 2026-10-05)

| ID | Item | Count | Detail / next step |
|---|---|---|---|
| NYI-OPS-1 | Paper parse timeouts (900 s, CPU Docling) | 12 papers | HMMT_2009_NOV_GUTS, HMMT_2019_FEB_ALGNT/GUTS/TEAM, HMMT_2020_FEB_ALGNT/COMB/TEAM, HMMT_2020/2022/2023_HMIC, SMT_2002_TEAM, SMT_2022_GENERAL. Retry individually with a longer timeout (GOT-RUN-2). |
| NYI-OPS-2 | Parse exit 1 (whole-paper fallback rejected / layout) | 12 papers | HMMT_1999_FEB_ADV/ALG/CALC/GEO/ORAL/TEAM, HMMT_2000_FEB_GUTS, SMT_2002_ADV/ALG/CALC/GENERAL/GEOM. Needs a splitter for these layouts (GOT-RUN-13, GOT-SRC-16). |
| NYI-OPS-3 | Classification coverage below 100 % | 5 papers | HMMT_2016_NOV_GEN/GUTS/TEAM, SMT_2019_TB_GEOM, SMT_2019_TEAM (e.g. 73/74 questions). Re-run classification for the missing questions. |
| NYI-OPS-4 | Teaching-metadata enrichment failures | 40 jobs (34 with 3 attempts used) | Mostly "failed validation after three attempts" plus a few rate-limit errors. The enum-overflow failures are all cleared. Needs a manual review or a deliberate attempt reset. |
| NYI-OPS-5 | Stale `pipeline.run` d50d9e51… still `IN_PROGRESS` | 1 run / 2 work items | PAPER_PURPLE_2026_HS/MS were completed by a later run. Mark the old run and its work items abandoned once no runner holds the batch lock. |

## 4. Content-engine gaps carried over from the v2 pack audit

Merged from [21](21_V2_PACK_IMPLEMENTATION_AUDIT.md) so they survive deletion of the pack. Source references are pack file names.

| ID | Gap | Status | Spec | Requirement to preserve |
|---|---|---|---|---|
| NYI-AUD-1 | Generated-item lifecycle entities | ⏳ | 03, 05, 09, 10 | `LearningItemVersion`, `TransformationRun`, `ValidationResult` and item-level `ReviewEvent` exist as durable rows for every generated practice item. |
| NYI-AUD-2 | Problem family and acyclic lineage API | ⏳ | 06, 18, 23 K | Every derivative belongs to a queryable family; ancestor/descendant queries exist; a lineage cycle is rejected. Today only `source_problem_id` exists. |
| NYI-AUD-3 | In-repo transformation engine and recipes | ⏳ | 07, 08, 23 B/L | Recipes produce distinct practice items, keep source links, and repeat runs do not silently duplicate equivalent jobs (idempotent job keys). |
| NYI-AUD-4 | Validation before auto-approval | ⏳ | 09, 10, 23 D/E, 24 #7 | Auto-approval is a policy applied only after required validators pass; failing candidates keep their raw generation and are never published. (Imported items are auto-approved today by product-owner decision.) |
| NYI-AUD-5 | Item publication and version pointer | ⏳ | 10, 11, 23 C/F/G | Admin edits create a new version; final classification and embeddings use the final text; superseded versions are hidden by default. |
| NYI-AUD-6 | Canonical correction audit | ⏳ | 04, 23 A | Raw source fragments never change; corrected canonical text is versioned with provenance to source and page. |
| NYI-AUD-7 | Practice diversity and transfer non-paraphrase | ⏳ | 15, 23 I, 24 #9 | Recovery practice varies structure; the transfer item must not be an exact paraphrase; avoid endless near-duplicates (duplicate/diversity validator). |

## 5. Walkthrough, transcript and test findings (2026-10-05)

| ID | Gap | Status | Detail / next step |
|---|---|---|---|
| NYI-WALK-1 | Technique tagging gap for Power of a Point | 🟡 | 1 of 1,697 Prasolov problems has `TECH.GEO.POWER_OF_A_POINT` (GOT-WALK-2). Re-classify `GEO.C03.S10` problems for technique tags or map subconcept → technique. |
| NYI-WALK-2 | MCQ distractor quality | ⏳ | "Pick the first move" distractors are templates (GOT-WALK-6). Generate topic-specific distractors and validate them (ties to NYI-AUD-4). |
| NYI-WALK-3 | Presentation normalisation of Prasolov text | ⏳ | Book references ("Problem 17.30") and PDF glyphs (`◦`, `∗`) shown to students (GOT-WALK-7). |
| NYI-WALK-4 | Learning-context tool latency | ⏳ | `get_problem_learning_context` ~28 s vs 30 s agent timeout (GOT-WALK-8). |
| NYI-WALK-5 | Solve-workspace agent chat | ⏳ | `SOLVE_WORKSPACE` link surface is reserved ([22](22_AGENT_SESSION_TRANSCRIPTS.md)); the solve page has no embedded tutor chat yet (pairs with NYI-P11). |
| NYI-WALK-6 | Transcript export / retention / redaction | ⏳ | No export, no retention policy, only tool-payload truncation ([22](22_AGENT_SESSION_TRANSCRIPTS.md) §6). |
| NYI-WALK-7 | Browser regression in CI | ⏳ | Playwright suite ([23](23_E2E_REGRESSION_SUITE.md)) runs only against a local stack; no CI job or seeded test environment. |
| NYI-ATB-1 | Taxonomy node embeddings | ✅ | **Delivered 2026-10-05.** 501/501 nodes are embedded as `TAXONOMY_NODE` (profile `pedagogy_step_v2`, `embed_textbook_steps.py`). The rendered text is name + parent path + chapter/section + taxonomy-edge neighbours, and provenance-only descriptions are dropped. **Remainder:** there is no retrieval API or agent tool over these vectors yet (pairs with NYI-P11), and technique/skill texts are thin where the source edges are sparse (NYI-ATB-8). |
| NYI-ATB-2 | Diagrams in graph / vectors | ⏳ | 250 diagrams exist only in Postgres. Project `Problem-[:HAS_DIAGRAM]->Diagram` (visibility-aware) and optionally embed captions or images. |
| NYI-ATB-3 | Durable diagram asset location | ⏳ | **Blocks deleting the pack.** All 250 `pedagogy.diagram.local_path` values point inside the requirements pack. Copy the assets and update the paths **before** deleting the pack (GOT-ATB-5). |
| NYI-ATB-4 | Chapter sections in the graph | ⏳ | 214 sections are PG-only; the graph has chapter `Paper` nodes only. |
| NYI-ATB-5 | Technique re-tagging | ⏳ | 280 problems have no `technique_ids` in the source; Power of a Point appears on 1 problem (with NYI-WALK-1). |
| NYI-ATB-7 | Learning-item → concept edges in the graph | ✅ | **Delivered 2026-10-05** ([25](25_LEARNING_ITEM_CONCEPT_EDGES.md)). `TARGETS_CONCEPT` and `TARGETS_SUBCONCEPT` 11,186 / 11,186 each, consistent via `PART_OF`; the dashboard row `learning_item_concept` is OK. **Remainder:** no REST, agent or graph-explorer consumer yet (with NYI-P11). |
| NYI-ATB-8 | Usage-weighted taxonomy texts | ⏳ | Imported `SUPPORTS` edges are sparse (for example, the *Power of a point* technique supports only 1 subconcept), so its vector text is thin. Enrich technique/skill texts with the subconcepts ranked by problem usage from `pedagogy.problem_enrichment`. |
| NYI-ATB-9 | Remaining v2 graph vocabulary | ⏳ | runtime_extension/06 lists `TheoryUnit`, `Misconception`, `VARIANT_OF`, `DERIVES_FROM`, `USES_RESULT_FROM`, `ALTERNATIVE_TO`, `JOINS_AT` and `Step-[:USES_TECHNIQUE]`. None exist in Aura because there is no source data (NYI-P13, NYI-3, NYI-AUD-2). |
| NYI-ATB-6 | Dashboard write actions | ⏳ | `/admin/textbooks` is read-only; edit, re-import, conflict resolution and per-row re-embed/re-project belong to Phase 12. |

## Change log

- 2026-10-06: Doc 26 WP1–WP4: NYI-P6 narrowed to erasure; NYI-P11 narrowed to the solve-page chat; NYI-P12 and NYI-1 delivered; NYI-3 rule tier delivered.
- 2026-10-05: NYI-ATB-7 delivered (learning-item concept/subconcept edges, [25](25_LEARNING_ITEM_CONCEPT_EDGES.md)).
- 2026-10-05: NYI-ATB-1 delivered (taxonomy embeddings 501/501). Added NYI-ATB-7 (learning-item concept edges), NYI-ATB-8 (usage-weighted taxonomy texts) and NYI-ATB-9 (remaining v2 graph vocabulary), all from a live Aura audit against runtime_extension/06.
- 2026-10-05: Added NYI-ATB-1…6 from the admin textbook corpus dashboard and coverage audit ([24](24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md)).

- 2026-10-05 (Pack audit / walkthrough): Added §4 NYI-AUD-1…7, merged from audit [21](21_V2_PACK_IMPLEMENTATION_AUDIT.md) so they survive deletion of the pack, and §5 NYI-WALK-1…7 from the Power-of-a-Point walkthrough, transcripts and the Playwright suite. Agent-session transcripts ([22](22_AGENT_SESSION_TRANSCRIPTS.md)) delivered.

- 2026-10-05 (Phase 9): NYI-P9 narrowed to its remainder; NYI-P10 now names the Phase 9 inputs.
- 2026-10-05 (Phases 7–8): NYI-P7 and NYI-P8 narrowed to their remainders (workspace, grader and hints delivered).
- 2026-10-05 (Phase 6): NYI-P6 narrowed to its remainder (the backend is delivered); NYI-P7/P8 now describe the REST hooks; NYI-2 partly delivered (step practice route); NYI-6 delivered and removed (3,243 problem/solution representations embedded); added NYI-11 and NYI-12.

- 2026-10-05: Created after Phase 5 (step vectors). It consolidates the open phases 6–13, partial gaps in delivered phases, and the verified operational backlog.
