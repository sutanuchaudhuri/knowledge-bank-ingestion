# 18 — Prasolov Import & v2 Runtime Progress Tracker

Source specification: `math_tutor_new_requirements_copilot_pack_v2_expanded/`
(`00_INDEX.md`, `33_COPILOT_UNIFIED_EXECUTION_PLAN.md`, `28_POSTGRES_IMPORT_AND_RECONCILIATION.md`,
`runtime_extension/03…05`, `20`, `21`).
Data: `math_tutor_new_requirements_copilot_pack_v2_expanded/GEOMETRY-TEXTBOOKS/Prasolov_Geometry_Corpus_Ch01_20`
and `…_Ch21_30` (`csv/` raw provenance, `pedagogy_v3/csv/` enriched import set, `diagrams/`).

Guiding rule from the product owner: **on a collision, extend the design; don't be too strict.**
The existing schema is extended additively, source quirks become `ingest.import_conflict` rows rather than aborting the import, and every step is idempotent.

Status legend: ✅ done · 🟡 in progress · ⏳ not started · ⛔ blocked

## Phase status

| # | Phase (pack order) | Status | Updated (UTC) | Evidence |
|---|---|---|---|---|
| 0 | Profile packages, map spec → existing schema | ✅ | 2026-10-05 | mapping table below |
| 1 | Import package + PostgreSQL (`ingest.*`, migration 010) | ✅ | 2026-10-05 17:3x | `make migrate-textbook-import-remote` |
| 2 | Solution parts and steps | ✅ | 2026-10-05 17:42 | 2,001 parts · 7,814 steps |
| 3 | Semantic step dependencies (DAG, cycle-checked) | ✅ | 2026-10-05 17:42 | 7,309 edges, 0 self-loops, 0 cycles |
| 3b | Learning items (no-proof transformations), anchors, diagrams | ✅ | 2026-10-05 17:42 | 11,186 items (all auto-approved, Phase 10) · 10,378 anchors · 250 diagrams |
| 3c | Idempotent re-run | ✅ | 2026-10-05 17:43 | re-run: new=0 upd=0 for every entity |
| 4 | Graph projection (Neo4j/Aura: steps, skills, subconcepts) | ✅ | 2026-10-05 18:2x | 13/13 node/edge types reconcile; re-run pruned 0; survives `--pedagogy` replacement; re-projected after approval: 11,186 `LearningItem`, 11,186 `DERIVED_FROM`, 10,378 `ANCHORED_AT`, 6,475 `ASSESSES` |
| 5 | pgvector step / learning-item metadata | ✅ | 2026-10-05 | 7,814/7,814 steps embedded (0 failed); retrieval `db/step_search.py`; after auto-approval 11,186 × 2 learning-item vectors embedded (22,372, 0 failed; all OK) |
| 6 | Student attempt/event runtime | ✅ backend | 2026-10-05 | migration 012 + `step_runtime.py` + 9 REST routes; golden flows C/D/H/I pass live (rolled back) |
| 7 | Student web workspace | ✅ | 2026-10-05 | `/learn/solve/{code}` page + `/api/rest/solve/*` proxy; browser-verified (hint, graded step, retry, reload restore, diagrams, practice) |
| 8 | Step evaluation + hints | ✅ | 2026-10-05 | migration 013 + `step_tutor.py`; responses graded after commit; hint ladder 1–4 generated + cached, 5 = reference step; live tests pass (rolled back) |
| 9 | Gap diagnosis | ✅ | 2026-10-05 | migration 014 + `step_diagnosis.py` (deterministic `rules-v1`); auto-diagnosis after repeated failure; 4 REST routes; workspace "What's tripping you up?" card; live golden flow passes (rolled back); browser-verified |
| 9b | Phase 9 leftovers: learning-item probes, admin gap page, optional AI re-rank | ✅ | 2026-10-05 | migration 015 + `textbook-approve-learning-items-remote` (11,186 approved); `/admin/knowledge-gaps`; `DIAGNOSIS_LLM_RERANK` |
| 10 | Recovery plans | ✅ | 2026-10-05 | migration 015 + `step_recovery.py`; 8 REST routes; detour UI in `/learn/solve/{code}`; live flows pass (rolled back); browser-verified end to end |
| 10b | Pack audit, Prasolov re-verification, tutor walkthrough, transcripts, e2e | ✅ | 2026-10-05 | audit [21](21_V2_PACK_IMPLEMENTATION_AUDIT.md) (~66 %); migration 016 + transcripts [22](22_AGENT_SESSION_TRANSCRIPTS.md); Playwright [23](23_E2E_REGRESSION_SUITE.md) 23 + 2 `@llm` passed |
| 10c | Admin textbook corpus dashboard + store coverage audit | ✅ | 2026-10-05 | [24](24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md): 7 read-only admin routes, `/admin/textbooks` + problem detail; coverage OK except taxonomy vectors (0/501) and diagrams graph/vectors; pack-path diagram blocker NYI-ATB-3 |
| 10d | Events/outbox consumers, stale attempts, presented events (doc [26](26_GEOMETRY_RUNTIME_COMPLETION_PLAN.md) WP4) | ✅ | 2026-10-06 | migration 018 + `outbox_worker.py`; `make -C mathbank-rest outbox-status` → 0 unconsumed |
| 10e | Step → technique tags, rule tier (doc 26 WP1) | ✅ | 2026-10-06 | migration 017 + `derive_step_techniques.py`; 4,354 tags on 3,397/7,814 steps; graph `USES_TECHNIQUE`; paid tier not run |
| 11 | Google ADK agent tools (doc 26 WP2) | ✅ tools · ⏳ solve-page chat | 2026-10-06 | 9 tools in `step_runtime_tools.py`; agent owns no state; `mathbank-agent/tests/test_step_runtime_tools.py` |
| 12 | Admin import/reconciliation UI (doc 26 WP3) | ✅ | 2026-10-06 | migration 019; `/v1/admin/imports/*` (15 routes); `/admin/imports`, DAG-review tab, item Approve/Reject; reconciliation all green; e2e `admin.spec.mjs` 13 passed |
| 13 | Rich non-linear DAG enrichment | ⏳ | — | admin edge edit/retype/reject exists (WP3); model proposals = doc 26 WP7 (paid) |

## Import results (Neon, verified 2026-10-05)

`make -C mathbank-db textbook-import-status-remote` prints these tables live. `ok=yes` means the source, staging and database counts reconcile.

| Entity | Ch01_20 source → in DB | Ch21_30 source → in DB | Notes |
|---|---|---|---|
| problem | 1,424 → 1,423 | 274 → 274 | 13.39 duplicate (INTRO prose) rejected |
| solution | 1,274 → 1,272 | 274 → 274 | orphan SOL-3.61, SOL-5.79 rejected |
| problem_enrichment | 1,424 → 1,423 | 274 → 274 | duplicate 13.39 taxonomy row resolved by section |
| solution_part | 1,629 → 1,629 | 372 → 372 | repeated IDs kept as `#2` occurrences |
| solution_step | 6,095 → 6,095 | 1,719 → 1,719 | repeated IDs kept as `#2` occurrences |
| step_dependency | 5,699 → 5,658 | 1,677 → 1,651 | difference = duplicate rows merged |
| learning_item | 9,196 → 9,196 | 1,990 → 1,990 | all PENDING_REVIEW, `student_visible=false` |
| diagram | 167 → 167 | 83 → 83 | 40 problem diagrams → `core.problem_image`; 210 solution diagrams stay hidden |
| taxonomy_node / edge | 407 / 2,545 | 137 / 520 | 43 shared nodes unchanged; 501 distinct nodes bridged |

Totals in `core`: 30 chapter papers (`PRASOLOV_PGV1_CH01…CH30`), 1,697 problems and 1,546 solutions.
`ingest.import_conflict` holds 443 rows: 3 WARNING and the rest INFO.

## Graph projection results (Aura, verified 2026-10-05)

`make -C mathbank-db textbook-graph-status-remote` re-prints this table read-only. The script is [project_textbook_steps.py](../mathbank-graph/etl/project_textbook_steps.py).

| Type | Postgres | Aura | Notes |
|---|---|---|---|
| `SolutionPart` / `SolutionStep` nodes | 2,001 / 7,814 | 2,001 / 7,814 | metadata only; `step_text` stays in Postgres |
| `HAS_PART` / `HAS_STEP` | 2,001 / 7,814 | 2,001 / 7,814 | `(Solution)→(SolutionPart)→(SolutionStep)` |
| `NEXT` / `DEPENDS_ON` | 5,753 / 1,556 | 5,753 / 1,556 | carry confidence, source_type, review_status, logical_dependency |
| `USES_SKILL` / `USES_CONCEPT` / `USES_SUBCONCEPT` | 7,814 each | 7,814 each | `Concept` nodes for SUBCONCEPT taxonomy rows also get the `:Subconcept` label |
| `LearningItem` + `DERIVED_FROM` / `ANCHORED_AT` / `ASSESSES` | 0 | 0 | only APPROVED and `student_visible` items are projected; none are yet |

- Every node and edge carries `projection_kind='solution_steps'` and `projection_version='v2'`. Edges also carry a `projection_key`.
- The paper-batch `--pedagogy` replacement deletes only `projection_kind='pedagogy'`, so it never removes this layer. This was verified by running `--pedagogy` and then `--status`: 13/13 still reconcile.
- Stale `solution_steps` nodes and edges are pruned on every run.
- Each run writes a `pipeline.graph_projection` row (`graph_name='textbook_step_graph'`) and merges a `graph_projection` summary into `ingest.content_package.report`.
- The first run took 36 s.

## Vector results — Phase 5 (Neon, verified 2026-10-05)

`make -C mathbank-db textbook-vector-status-remote` re-prints this read-only.

| Representation kind | Eligible | Active representation | ACTIVE embedding | Status |
|---|---|---|---|---|
| `SOLUTION_STEP` | 7,814 | 7,814 | 7,814 | OK |
| `LEARNING_ITEM_QUESTION` / `_SKILL_SIGNATURE` | 0 | 0 | 0 | OK — only APPROVED + `student_visible` + no-proof items are eligible |

- Projector: `mathbank-db/etl/embed_textbook_steps.py` (profile `pedagogy_step_v2`, uuid5 surrogate ids, idempotent rebuild).
  The full backfill took 16 m 34 s, because inserts are one row per round trip over Neon (NYI-7).
- Retrieval: `mathbank-rest/src/mathbank_rest/db/step_search.py`. Filters are hard filters, the semantic side uses exact cosine distance, the lexical side uses `websearch_to_tsquery`, and the two are fused with RRF (k=60). Step text is dropped unless the caller opts in.
- Prasolov problem/solution statements are embedded through the existing corpus embedder (`textbook-problem-vector-remote`): 3,243 representations (1,697 problems + 1,546 solutions), 3,243 embedded, 0 failed, 14 m 55 s.

## Student step runtime — Phase 6 (Neon, verified 2026-10-05)

Migration `mathbank-db/sql/012_step_runtime.sql` (idempotent, applied twice) adds:

| Object | Purpose |
|---|---|
| `learner.solve_attempt` | Stateful solving session. A partial unique index allows only one `IN_PROGRESS` session per student and problem, so "start" resumes it |
| `learner.attempt_step_state` | Per-step state machine (spec 09). A CHECK forbids `independent_success` when `help_level_used > 0` |
| `learner.event` | Append-only event log (trigger `event_append_only` blocks UPDATE/DELETE) |
| `learner.idempotency_record` | Replays the response for a retried `Idempotency-Key`. Reusing the key with a different body is rejected (422) |
| `tutor.runtime_state` | Checkpoint with `current_mode` and `state_version` (optimistic concurrency → 409) |
| `pipeline.outbox_event` / `outbox_consumption` | Transactional outbox (ATTEMPT_STARTED, STEP_EVALUATED) |

The service is `mathbank-rest/src/mathbank_rest/step_runtime.py` (deterministic; the agent never owns state). Its routes are in `routers/step_runtime.py`:

| Method / path | Auth | Notes |
|---|---|---|
| `POST /v1/students/{student_id}/problems/{problem_ref}/attempts` | JWT (own id) | problem uuid or canonical code; resumes the open session |
| `GET /v1/attempts/{id}` · `/v1/attempts/{id}/runtime` | JWT (owner) | current step metadata, own responses, counts only — never `step_text` |
| `POST /v1/attempts/{id}/steps/{step_id}/responses` | JWT | stores the response, then grades it (Phase 8; `evaluate=false` keeps it PENDING) |
| `POST /v1/attempts/{id}/steps/{step_id}/hint` | JWT | help level +1 (max 5) and the hint text (Phase 8) |
| `POST /v1/attempts/{id}/steps/{step_id}/outcome` | `X-Admin-Api-Key` | human tutor override: applies SUCCESS/FAILED/SKIPPED and advances; the student cannot self-grade |
| `POST /v1/attempts/{id}/submit` | JWT | hand in early → `SUBMITTED`, mode `REVIEW` |
| `GET /v1/students/{student_id}/events` | JWT (own id) | event history |
| `GET /v1/solution-steps/{step_id}/practice` | JWT | same-skill steps from other problems; reuses the stored step vector (no paid call) |

- Step advance: the next step is the first in `global_step_index` order whose hard `DEPENDS_ON` prerequisites (not REJECTED) are done. A failed step stays current and is re-presented as `RETRY_PRESENTED`.
- Completion writes exactly one legacy `learner.attempt` row (`source='step_runtime'`; `is_correct` = every step succeeded; `hint_count` = HINT_REQUESTED events) and links it by `outcome_attempt_id`. The route then recomputes mastery (GOT-PG-18).
- Evidence:
  - `tests/test_step_runtime.py` has 12 offline tests and 2 live tests (`MATHBANK_LIVE_STEP_RUNTIME_TEST=1`). The live tests cover golden flows C, D, H and I plus retry, completion, outbox and append-only. All runtime tables were 0 rows after the rolled-back live run.
  - The full offline suite has 179 passing tests.
- Phases 7 and 8 are now delivered (sections below). Recovery (Phase 10) is delivered too — see the Phase 10 section and [20_NOT_YET_IMPLEMENTED.md](20_NOT_YET_IMPLEMENTED.md).

## Step evaluation and hints — Phase 8 (Neon, verified 2026-10-05)

Migration `mathbank-db/sql/013_step_hints.sql` (idempotent, applied twice) adds `pedagogy.step_hint`: generated hint text cached per (step, level 1–4, `prompt_version`). The service is `mathbank-rest/src/mathbank_rest/step_tutor.py`; the model is `STEP_TUTOR_MODEL` (default `gpt-4.1-mini`).

| Capability | Behaviour |
|---|---|
| Grader | Compares the response with the canonical step **server-side** (strict JSON schema, temperature 0): verdict CORRECT / PARTIALLY_CORRECT / INCORRECT / OFF_TOPIC, confidence, one of the pack-13 failure modes and a failure location. CORRECT with confidence ≥ 0.6 → SUCCESS; anything else → FAILED (the step is re-presented). |
| Lock rule | Submit commits (txn 1) → model call with no row lock → `record_step_outcome` with the saved `state_version` (txn 2). A concurrent change gives `evaluation_status=PENDING`; a model error gives `UNAVAILABLE`; the response is never lost. |
| Student view | Only result, verdict, feedback and `feedback_redacted`. Failure mode, evidence and confidence stay in `attempt_step_state.last_evaluation` and the `STEP_EVALUATED` event. |
| Hint ladder | 1 nudge · 2 concept · 3 strategy · 4 near-explicit · 5 reveal (returns the reference step). Levels 1–4 are generated once and cached; levels 1–3 pass a 7-word n-gram leak guard (one stricter retry, then a fixed template). |
| New routes | `GET /v1/attempts/{id}/steps/{step_id}/hints` (restore the ladder), `GET /v1/problems/by-code/{code}/diagrams`, `GET /v1/problem-images/{image_id}` (PNG, path-confined to the repo). |
| Runtime additions | `current_step.goal` (student-facing goal from `step_type`), `current_step.last_evaluation` (student view) and a `timeline` of all steps. Locked entries are opaque; completed entries carry `reference_text`. |
| Smoke check (paid, rolled back) | A correct response → SUCCESS 0.95; a wrong one → FAILED / NOT_RECOGNIZED with non-leaking feedback; the level-1 hint did not leak. |

- Evidence: `tests/test_step_tutor.py` (offline: leak guard, verdict mapping, redaction, route orchestration, model failure, 409 → PENDING, slash step IDs, image traversal; live: hint ladder, cache, reveal, evaluated outcome). Full offline suite: 198 passed.

## Student workspace — Phase 7 (browser-verified 2026-10-05)

| Piece | Location |
|---|---|
| Page | `mathbank-web/app/learn/solve/[code]/page.jsx` (server, redirects to `/login?next=…` without a student token) and `SolveWorkspace.jsx` (client) |
| Proxy | `app/api/rest/solve/[...path]/route.js` + `lib/solveProxy.mjs`: an allow-list of runtime routes; mutations must be same-origin; `student_id` comes from the token; forwards `Idempotency-Key`; **no outcome route** |
| Helpers | `lib/solveFlow.mjs` (hint ladder, timeline legend, labels, progress) |
| Entry points | "Solve step by step" on `/learn` and `/db` problem detail for Prasolov problems; `/login?next=` returns to the page |

The page shows a progress header; the problem with diagrams; an "Established so far" list (reference step + your response for done steps); the current step with goal, skill, feedback and a MathText preview; the hint ladder; the solution-path timeline (✓ / ✓💡 / ● / ! / ○); and same-skill practice links. Refresh restores the session, hints and last feedback; a 409 reloads the latest state.

Walkthrough (`PRASOLOV_PGV1_CH01_P001`, test student `phase7.walkthrough@example.com`): nudge hint → correct step graded "Solved with help" and advanced; a nonsense response → "Incorrect" + Try again; reload restored the attempt; `PRASOLOV_PGV1_CH21_P024` served its figure through the proxy and listed 5 practice steps. Web tests: 37 pass.

## Gap diagnosis — Phase 9 (Neon, verified 2026-10-05)

Migration `mathbank-db/sql/014_gap_diagnosis.sql` (idempotent, applied twice) adds:
- `pedagogy.gap_diagnosis`: one row per diagnosis run. It holds the trigger, the recommended action, the evidence fingerprint, the evidence and the probes. It is unique per (attempt, step, fingerprint).
- `pedagogy.knowledge_gap`: ranked hypotheses with a status lifecycle.
- `GAP_DIAGNOSED` and `GAP_HYPOTHESIS_RESOLVED` in the `learner.event` type CHECK.

The service is `mathbank-rest/src/mathbank_rest/step_diagnosis.py`. It is deterministic (`rules-v1`) and makes no model calls.

| Capability | Behaviour |
|---|---|
| Evidence | The current step (tries, help level, grader failure mode/location), its DEPENDS_ON predecessors in the same attempt, the student's history on the same skills in other attempts, and approved `knowledge.concept_relation` prerequisites. Prasolov skills have no skill-level prerequisite edges, so the **step DAG is the prerequisite source**. |
| Hypotheses | Up to 5, ranked. Kinds by `failure_location`: the step's own skill (`SKILL`, or the grader's `TECHNIQUE`/`REPRESENTATION`), a predecessor step's skill (`PREREQUISITE`), a subconcept pattern (`SUBCONCEPT`) and a concept prerequisite (`CONCEPT`). Confidence 0.05–0.95. |
| Recommended action | `RETRY_WITH_HINT` (careless slip, or a skill the student has shown independently) · `RECOVERY_DETOUR` (top confidence ≥ 0.6, consumed by Phase 10) · `DIAGNOSTIC_PROBE` otherwise. |
| Probes | Approved, student-visible no-proof learning items first, then unseen same-skill PUBLISHED steps from other problems. The student view contains no step text. |
| Triggers | `AUTO`: inside `record_step_outcome` when a step FAILS after ≥ 2 tries or help ≥ 3, in a savepoint so a diagnosis error can't lose a grade. `STUDENT_REQUEST`: `POST …/diagnose`. The same evidence reuses the previous diagnosis (`reused=true`). |
| Hypothesis lifecycle | A later FAILED outcome on the gap's skill → `CONFIRMED`. An independent success → `UNRESOLVED`→`REJECTED` or `CONFIRMED`→`RESOLVED`. Success with help or a skip changes nothing. This works across all of the student's attempts and emits `GAP_HYPOTHESIS_RESOLVED`. |
| Student view | Labels, likelihood (likely / possible / worth checking), status and probes. Failure modes, confidences and evidence are admin-only. |
| Routes | `POST /v1/attempts/{id}/steps/{step_id}/diagnose`, `GET /v1/attempts/{id}/diagnoses` (JWT); `GET /v1/admin/attempts/{id}/diagnoses`, `GET /v1/admin/students/{student_id}/knowledge-gaps` (admin key). `GET /v1/attempts/{id}/runtime` adds `current_step.diagnosis`. |
| Web | A "What's tripping you up?" card in `/learn/solve/{code}`, with an action badge, ranked hypotheses, status badges, probe links and a "Diagnose where I'm stuck" / "Re-check" button. The proxy allow-list gained the two student routes. |

- Evidence:
  - `tests/test_step_diagnosis.py` has 15 offline tests (scoring, action, fingerprint, transitions, auto trigger, student redaction, routes).
  - Its live golden flow covers: auto-diagnosis after the 2nd failure → reuse → CONFIRMED → RESOLVED/REJECTED, events written, no mastery writes.
  - Offline suite: 213 passed. Web tests: 39 passed.
- Browser walkthrough (`PRASOLOV_PGV1_CH01_P006`, student `phase7.walkthrough@example.com`):
  - The card asked for an attempt first.
  - After 2 hints and 2 wrong answers, the auto-diagnosis showed "Short detour suggested", the local skill "Recognize and use similar triangles" as *likely*, and 3 practice-step probes.
  - Re-check showed "Nothing new since the last check".
  - A reload restored the card.

## Phase 10 — recovery plans (and Phase 9 leftovers)

Migration `mathbank-db/sql/015_recovery_runtime.sql` (idempotent) adds:
- `pedagogy.learning_item.approval_method` (`automatic`/`human`) and `approved_at`, plus partial indexes on student-visible items by skill and subconcept.
- `pedagogy.gap_diagnosis.ai_rerank` (jsonb) for the optional model re-rank.
- `pedagogy.recovery_plan`: one row per detour, with origin attempt/step, gap, trigger (`DIAGNOSIS`/`STUDENT_REQUEST`/`TUTOR`/`BRANCH`), status (`ACTIVE`, `SUSPENDED`, `COMPLETED`, `EXHAUSTED`, `ABORTED`, `SUPERSEDED`), policy, mastery and outcome. At most one ACTIVE plan per attempt (partial unique index).
- `pedagogy.recovery_plan_item`: ordered items by stage (`FOUNDATION` → `RECOGNITION` → `ISOLATED_EXECUTION` → `GUIDED_APPLICATION` → `TRANSFER` → `RETURN_TO_STEP`), kind `LEARNING_ITEM`/`THEORY`/`RETURN`, tries, first-try result and the last response.
- 10 `RECOVERY_*` / `RETURNED_TO_*` event types. The `DETOURED` step state is now used.

Auto-approval (product-owner decision "everything auto approved for now") is an operator step, not part of the migration: `make -C mathbank-db textbook-approve-learning-items-remote` runs `sql/ops/approve_learning_items_auto.sql`. It approves `PENDING_REVIEW` no-proof items that pass a structural check (MCQ: ≥ 2 choices including the correct answer; SUBPROBLEM: a non-empty seed) and sets `approval_method='automatic'` and `student_visible=true`. All 11,186 items passed. The importer never overwrites a non-`PENDING_REVIEW` status, so a re-import keeps the approval.

The service is `mathbank-rest/src/mathbank_rest/step_recovery.py` (`recovery-rules-v1`).

| Capability | Behaviour |
|---|---|
| Plan builder | Picks approved, student-visible learning items on the gap's skill (then subconcept), one per stage, excluding the origin problem, cross-reference stubs and items the student already passed in an earlier plan. The worked example is a same-skill reference step from another problem. |
| Grading | MCQ by choice index; SUBPROBLEM by the Phase 8 LLM grader; THEORY by acknowledgement. 2 tries per item. |
| Adaptation | `ADVANCE`, `CONFIRM` (correct after a miss → one extra same-stage item), `RETRY`, `ALTERNATE` (swap the item), `BRANCH` (one level of prerequisite sub-detour). At most 3 added items. |
| Mastery policy | 2 first-try successes plus a passed transfer item → `COMPLETED`, gap → `RESOLVED`. Running out of items → `EXHAUSTED`, gap stays `CONFIRMED`. |
| Return | `resume` (plan must be COMPLETED/EXHAUSTED) moves the `DETOURED` origin step back to `RETRY_PRESENTED` ("Try again") or `PRESENTED`, keeps its tries and hints, and emits `RETURNED_TO_ORIGINAL_STEP`. `abort` ends the plan and any branch as `ABORTED` and returns the same way, without resolving the gap. Starting a detour while one is running returns the running one (`resumed`). A branch suspends its parent (`SUSPENDED`). |
| Student routes (JWT) | `POST/GET /v1/attempts/{id}/recovery-plans`, `GET /v1/recovery-plans/{id}`, `GET …/next`, `POST …/items/{item_id}/responses`, `POST …/resume`, `POST …/abort`. `GET /v1/attempts/{id}/runtime` adds `recovery`. |
| Admin routes (key) | `GET /v1/admin/recovery-plans`, `GET /v1/admin/recovery-plans/{id}` (teacher view with answers), `GET /v1/admin/knowledge-gaps` (totals, top open targets, gap list). |
| Probes (Phase 9 leftover) | `find_probes` now offers approved learning items first, then other problems' steps. |
| AI re-rank (Phase 9 leftover) | Off by default. With `DIAGNOSIS_LLM_RERANK=1` a model (`DIAGNOSIS_RERANK_MODEL` → `STEP_TUTOR_MODEL` → `gpt-4.1-mini`) may only **reorder** the rules-v1 hypotheses; stored in `ai_rerank`, shown as an "AI-ranked" badge. Failures fall back silently. |
| Web | Diagnosis card offers "Start a short detour" / "Strengthen this skill"; a recovery panel with a stage track, the source problem, theory/MCQ/subproblem items, finished items and Return/Leave. Admin page `/admin/knowledge-gaps` (status cards, gap table, top targets, plans table, plan detail). |

- Evidence:
  - `tests/test_step_recovery.py`: 16 offline tests plus live flows (complete → resume, exhausted, branch, cross-reference stubs never used). Offline suite: 229 passed. Web tests: 43 passed.
  - Browser walkthrough (`PRASOLOV_PGV1_CH01_P006`, `phase7.walkthrough@example.com`): detour → worked example → MCQ wrong then right (CONFIRM added an item) → MCQ → LLM-graded subproblem → transfer passed → "Skill strengthened" → Return to the exact step in "Try again"; gap RESOLVED; plan survives reload. The admin page shows the RESOLVED gap and the COMPLETED plan (7 items, 5/0, 1 adapted).

## Phase 10b — audit, walkthrough, transcripts, browser regression (2026-10-05)

**Prasolov Ch 1–30 import re-verified (Neon):** 30 chapter papers under `PRASOLOV_PGV1`, 1,697 problems,
1,546 with solutions, 0 unreconciled rows; all 1,697 problems chunked and embedded (31,883 embeddings).

**Student walkthrough: Power of a Point** (test learner Pia, browser):

| Step | Result | Fix applied |
|---|---|---|
| Home chat "power of a point" | First run: no Prasolov problems (tool timeout). | Graph leg rewritten tag-first (36 s → 2 s); agent timeout 30 s; docstring names `PRASOLOV_PGV1` (GOT-WALK-1). |
| Re-run | `search_problems` + `get_problem_learning_context` called; Prasolov radical-axis problem returned; KaTeX renders. | — (tagging gap recorded: GOT-WALK-2 / NYI-WALK-1) |
| Solve `PRASOLOV_PGV1_CH03_P050` | Nudge hint (LLM, KaTeX) → wrong answer "Partially correct" + feedback → diagnosis "Quick check suggested". | — |
| "Strengthen this skill" detour | Worked example → Recognise → Use it once → In context → Somewhere new → Back to problem. | Provenance description hidden; worked example and items ranked by topic closeness (GOT-WALK-4/5). |
| Images | `CH21_P024` diagram served via `/api/rest/solve/images/{id}` (naturalWidth 1094). | — |
| Transformed items | MCQ/subproblem/theory items render with KaTeX; template distractors, "Problem 17.30" references and PDF glyphs remain. | Recorded (GOT-WALK-6/7, NYI-WALK-2/3). |
| Conversations | `/learn/conversations` lists both chats; `/admin/conversations` shows linked + unlinked count with tool calls. | UTC timestamps fixed (GOT-WALK-3). |
| Nav | Header shows "Signed in · {first name}" (client-only fetch, no hydration mismatch). | — |

**Tests:** offline pytest 235 passed; web node tests 50 passed; agent 4 passed / 1 skipped;
Playwright default 23 passed, `@llm` 2 passed. Verify with `make -C mathbank-web e2e`.

## Admin corpus dashboard and coverage — Phase 10c (Neon + Aura, observed 2026-10-05)

Full matrix and explanations: [24 §3](24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md). Verify any time at `/admin/textbooks` (Coverage tab) or `GET /v1/admin/textbooks/coverage`.

| Check | Result |
|---|---|
| Problems / solutions / steps / learning items in PG = vectors = graph | ✅ 1,697 / 1,546 / 7,814 / 11,186 |
| Parts, dependencies, anchors, enrichment in graph | ✅ 2,001 / 7,309 / 10,378 / 1,697 |
| Taxonomy nodes in graph | ✅ 501/501 (keyed by core concept/skill/technique uuid) |
| Learning item → concept / subconcept edges | ✅ 11,186 / 11,186 each (`TARGETS_CONCEPT`, `TARGETS_SUBCONCEPT`; [25](25_LEARNING_ITEM_CONCEPT_EDGES.md)) |
| Taxonomy node vectors | ✅ 501/501 `TAXONOMY_NODE` (2026-10-05; `make -C mathbank-db textbook-vector-remote`) |
| Diagrams | ✅ 250 in PG and all files present; ❌ not in graph or vectors (NYI-ATB-2); ⚠️ files live inside the pack (NYI-ATB-3) |
| Source vs PG differences | All explained by de-duplication or conflicts (duplicate problem 1, orphan solutions 2, repeated sections 25, ambiguous dependencies 163 …) |

**Tests:**

- Offline pytest: 248 passed.
- Web node tests: 52 passed.
- Playwright: 26 passed by default.

## Fluid widgets, live classroom and student add-ons — Phase 11 (Neon, 2026-10-06)

Specs: [27](27_FLUID_WIDGET_LAYER.md) (fluid pack), [28](28_DISTRIBUTED_LIVE_PLATFORM.md) (distributed handoff pack),
[29](29_STUDENT_INPUT_ADDONS.md) (composer/voice/formatting). Both source packs are kept in the repo until audited.

| Item | Status | Evidence |
|---|---|---|
| Migration 020 (`authoring`, `live`, `activity`, `visual` schemas) | ✅ applied to Neon | `mathbank-db/sql/020_live_fluid_platform.sql` |
| REST: authoring, live sessions/commands, activities, widgets, tutor actions, format-math (47 new paths; OpenAPI 137 paths) | ✅ | `routers/fluid.py`, `routers/live.py`, [reference/openapi.json](reference/openapi.json) |
| Separate socket deployable `mathbank-live` (:5174) | ✅ | `make -C mathbank-live start|test|smoke` |
| Shared `mathbank-widgets` package (WidgetHost, MathComposer, voice) | ✅ | `make -C mathbank-web sync-widgets` |
| ElevenLabs voice + make targets | ✅ | `make sync-eleven-key`, `check-eleven [TTS=1]`, `sync-live-env`, `sync-keys` |
| Agent tools `propose_widget`, `format_math` (24 tools) | ✅ | `mathbank-agent/.../tools/widget_tools.py` |
| Admin widget gallery | ✅ | `/admin/widgets` |
| Admin authoring web UI, `/v1/content/*`, NATS/Redis, visual agent split, asset API, MCP, group UI | ⏳ | [20](20_NOT_YET_IMPLEMENTED.md) NYI-FW/LIVE/UXA |

**Tests (2026-10-06):**

- REST fluid/widget: 55 passed.
- Live DB integration (Neon): passed.
- `mathbank-live` unit: 10/10; smoke: PASS.
- `mathbank-widgets`: 10 passed; web widget blocks: 3 passed.
- Playwright `input-addons` (5) and `live-classroom`: pass.

**Paid calls:** two tiny ElevenLabs calls only (one TTS, one STT; both 200). No OpenAI calls.

## Spec → existing schema mapping

| Spec object | Implementation | Decision |
|---|---|---|
| `ingest.content_package` / staging / reconciliation | `ingest.content_package`, `package_file`, `package_status_event`, `staging_row`, `import_conflict`, `reconciliation` | new |
| Book / chapter | `core.competition` (`PRASOLOV_PGV1`, level TEXTBOOK) → edition (year NULL) → `core.paper` per chapter | extend (year now nullable) |
| Problem / solution | `core.problem` (`PRASOLOV_PGV1_CH01_P031`), `core.solution` (kind TEXTBOOK); source IDs in `pedagogy.problem_source_ref` / `solution_source_ref` | reuse |
| Taxonomy nodes | `pedagogy.taxonomy_node` bridged to `knowledge.concept` (DOMAIN `GEO` → existing `geo`; CONCEPT level 1, SUBCONCEPT level 2), `knowledge.skill`, `knowledge.technique` | reuse + bridge |
| Taxonomy edges | `pedagogy.taxonomy_edge`; SKILL PART_OF SUBCONCEPT → `knowledge.skill_concept`; concept PART_OF → `concept_relation` HAS_SUBCONCEPT | reuse |
| `taxonomy.problem_enrichment` | `pedagogy.problem_enrichment` + `knowledge.problem_concept/technique/skill/pedagogy` | new + reuse |
| SolutionPart / Step / Dependency | `pedagogy.solution_part`, `solution_step`, `solution_step_dependency` (legacy, empty `core.solution_step` untouched) | new |
| LearningItem (no-proof transformations) | `pedagogy.learning_item` (+ `learning_item_step_anchor`); review-gated | new |
| Diagrams | `pedagogy.diagram`; only `PROBLEM` usage linked to `core.problem_image` | new + reuse |

## Data quirks handled (not fatal)

- Duplicate problem 13.39: the chapter-intro copy is rejected (WARNING `DUPLICATE_PROBLEM_ID`).
- Orphan solutions SOL-3.61 and SOL-5.79 (WARNING `ORPHAN_SOLUTION`).
- Repeated part and step IDs (81 / 140) get occurrence suffixes. The step at occurrence k attaches to part occurrence k, and dependencies resolve to occurrence 1 (INFO).
- 47 parts whose `step_count` differs from the imported steps (INFO `STEP_COUNT_MISMATCH`).
- 7 duplicate transformation IDs, all on 13.39 (INFO, imported as `#2`).
- `solution_step_anchor_id` is pipe-delimited and is split into anchors.
- One taxonomy node has a different name in the two packages: the first name is kept (INFO `NAME_CONFLICT`).

## Safety invariants (re-check any time)

```sql
-- all must return 0
SELECT count(*) FROM pedagogy.learning_item WHERE student_visible;                     -- nothing visible before review
SELECT count(*) FROM pedagogy.diagram d JOIN core.problem_image i USING (problem_image_id)
 WHERE d.visibility = 'SOLUTION_HIDDEN';                                               -- no solution figure leaks
SELECT count(*) FROM pedagogy.solution_step_dependency WHERE from_step_id = to_step_id; -- no self-loops
SELECT count(*) FROM core.problem p WHERE canonical_code LIKE 'PRASOLOV_PGV1_%'
   AND (NOT EXISTS (SELECT 1 FROM knowledge.problem_skill s WHERE s.problem_id = p.problem_id)
     OR NOT EXISTS (SELECT 1 FROM knowledge.problem_pedagogy g WHERE g.problem_id = p.problem_id)); -- paid watcher skips them
-- reconciliation
SELECT p.package_name, r.scope, r.entity_type, r.reconciled FROM ingest.reconciliation r
  JOIN ingest.content_package p USING (content_package_id) ORDER BY 1, 3;
SELECT severity, conflict_type, count(*) FROM ingest.import_conflict GROUP BY 1, 2 ORDER BY 1, 2;
```

## Commands

```bash
make -C mathbank-db textbook-import-dry-run              # offline validation, no DB
make -C mathbank-db textbook-import-dry-run CHAPTER=1    # pilot scope
make -C mathbank-db migrate-textbook-import-remote       # migration 010 (idempotent)
make -C mathbank-db textbook-import-remote               # import both packages (idempotent)
make -C mathbank-db textbook-import-status-remote        # status + reconciliation tables
make -C mathbank-db textbook-graph-dry-run-remote       # planned graph counts, no writes
make -C mathbank-db textbook-graph-remote               # --pedagogy base layer + step layer (idempotent)
make -C mathbank-db textbook-graph-status-remote        # Postgres vs Aura reconciliation, read-only
make -C mathbank-db migrate-step-vector-remote          # migration 011 (Phase 5, idempotent)
make -C mathbank-db textbook-vector-remote              # build + embed step chunks (paid, idempotent)
make -C mathbank-db textbook-vector-status-remote       # eligible vs ACTIVE embeddings, read-only
make -C mathbank-db textbook-problem-vector-remote      # embed Prasolov problem/solution statements (paid)
make -C mathbank-db migrate-step-runtime-remote         # migration 012 (Phase 6, idempotent)
make -C mathbank-db migrate-step-hints-remote           # migration 013 (Phase 8 hint cache, idempotent)
make -C mathbank-db migrate-gap-diagnosis-remote        # migration 014 (Phase 9 gap diagnosis, idempotent)
MATHBANK_LIVE_STEP_RUNTIME_TEST=1 mathbank-rest/.venv/bin/python -m pytest -q mathbank-rest/tests/test_step_runtime.py  # live golden flows, rolled back
mathbank-rest/.venv/bin/python -m pytest -q mathbank-db/tests/test_textbook_import.py mathbank-graph/tests
```

## Operational notes

- The importer takes the same `LOCK TABLE … SHARE ROW EXCLUSIVE` set as `import_pedagogy`, in the same order. This prevents deadlocks with the running enrichment watcher; one deadlock was observed and fixed during the pilot.
- The watcher's `--relationships` mode will queue the newly bridged Prasolov skills and concepts for auto-approved relationship enrichment, which costs money. This is expected; monitor it in the pipeline job console.
- Hybrid search year filters exclude Prasolov problems, because the textbook edition has no year.
- Learning items stay `PENDING_REVIEW`. Re-imports never overwrite rows an admin has already reviewed.
- Two incidents followed the import, and both are fixed:
  - The enrichment watcher died as the pilot deadlock victim (GOT-RUN-12).
  - The bridged textbook catalog pushed the structured-output enum to 1,164, over the 1,000 limit (GOT-ENR-10). Contest enrichment now uses a scoped catalog of 866 slugs. The 55 affected jobs were re-queued, and the watcher was restarted and is auto-approving again.
- Verify the watcher with:
  - `ps -eo pid,etime,command | grep "[e]nrich_corpus.py --watch"` (exactly one Python process)
  - `tail logs/automatic-enrichment.log` in `mathbank-rest`

All pitfalls found so far are listed in [19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md](19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md).

## Change log

- 2026-10-06 (Phase 11, fluid + live + add-ons): migration 020 on Neon; REST fluid/live routers; `mathbank-live` socket deployable; `mathbank-widgets` package with MathComposer, ElevenLabs voice and agentic formatting; agent widget tools; docs 27–29; OpenAPI snapshot regenerated (137 paths / 63 schemas).

- 2026-10-06 (Doc 26 WP1–WP4, Prasolov-only): migrations 017 (step techniques), 018 (outbox consumers, analytics rollup, projection requests, `ATTEMPT_ABANDONED`), 019 (admin review audit, conflict decisions, `admin_edited_at`, `solution_dag_review`, `projection_request.requested_by`) applied to Neon. Agent step-runtime tools, admin import UI and projection-queue drain (`make -C mathbank-db projection-queue-status-remote | projection-queue-run-remote`). REST suite 280 passed / 18 skipped (live, rolled back); web 56 unit + 13 admin e2e passed. Non-Prasolov corpora intentionally empty (doc 26 §3).

- 2026-10-05 (NYI-ATB-7): Projected `LearningItem -[:TARGETS_CONCEPT|TARGETS_SUBCONCEPT]->` edges ([25](25_LEARNING_ITEM_CONCEPT_EDGES.md)). Reconciled at 11,186 each with 0 pruned. The 4,711 items without a skill now have a direct taxonomy link. Added the dashboard coverage row `learning_item_concept`; graph tests 3 and admin tests 14 pass.
- 2026-10-05 (Phase 10c follow-up): Embedded all 501 taxonomy nodes. `embed_textbook_steps.py` gained the `TAXONOMY_NODE` kind with 6 new offline tests (12 total), and the dashboard vector count is now book-scoped. Build-only re-run: 0 new / 0 superseded. All kinds reconcile. A live Aura audit against runtime_extension/06 is recorded as NYI-ATB-7…9.
- 2026-10-05 (Phase 10c): Added the admin textbook corpus dashboard ([24](24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md)) and audited source/PG/vector/graph coverage. Fixed the diagram image key: it is now `source_diagram_id`, because `diagram_id` is text, not a uuid. New tests: 13 pytest, 2 node and 3 e2e.

- 2026-10-05 (Phase 10b): Pack audit (21), Prasolov re-verification, Power-of-a-Point walkthrough with fixes (tag-first graph search, topic-aware recovery examples, provenance filter, UTC transcript timestamps, signed-in nav), migration 016 + agent-session transcripts (22), Playwright regression suite (23).

- 2026-10-05 (Phase 9):
  - Migration 014 (`pedagogy.gap_diagnosis`, `pedagogy.knowledge_gap`, extended event CHECK) applied to Neon twice.
  - Added `step_diagnosis.py`, the auto-diagnosis hook in `record_step_outcome` and `current_step.diagnosis`.
  - Added 4 REST routes, the proxy allow-list entries and the workspace diagnosis card.
  - 16 new tests (15 offline + 1 live); browser-verified.
  - Documented GOT-DIAG-1…6; narrowed NYI-P9 in doc 20.
- 2026-10-05 (Phases 7–8):
  - Migration 013 (`pedagogy.step_hint`) applied to Neon twice; added `step_tutor.py` (grader, hint writer, leak guard, step goals).
  - Responses are graded after commit; hints carry text; added the hints, diagrams and problem-image routes; `get_runtime` gained `goal`, `last_evaluation` and `timeline`.
  - Fixed: step IDs contain `/`, so every step route returned 404 over HTTP (GOT-WEB-13).
  - Added the `/learn/solve/{code}` workspace, its proxy and helpers; browser-verified.
- 2026-10-05 (Phase 6):
  - Added migration 012 (applied to Neon; re-applied after removing `learner.event.response` and adding `learner.idempotency_record`).
  - Added the deterministic `step_runtime.py` service and 9 REST routes; registered the router in `main.py`.
  - Added `similar_steps_for_step` (stored-vector practice retrieval).
  - 14 new tests. Documented GOT-PG-18…21, GOT-WEB-10…12 and GOT-TEST-5; updated doc 20.

- 2026-10-05 (Phase 5):
  - Added migration 011 and the `embed_textbook_steps.py` projector.
  - Backfilled 7,814/7,814 steps (16.5 min) and added `step_search.py` with 9 tests.
  - Added gotchas GOT-VEC-1…8 and the not-implemented register (doc 20).
  - Refreshed the architecture reference docs (`requirements/reference/`) with the docs skill.

- 2026-10-05 (operations):
  - Fixed the enrichment enum overflow caused by the textbook taxonomy (scoped catalog plus a pre-call guard and a unit test).
  - Re-queued 55 jobs and restarted the watcher.
  - Recorded GOT-ENR-10, GOT-RUN-12 and GOT-RUN-13.

- 2026-10-05 (Phase 4):
  - Added `mathbank-graph/etl/project_textbook_steps.py`.
  - Extracted the shared `pg_conninfo` and `graph_target` helpers in `project_from_postgres.py`.
  - Added Makefile targets `textbook-graph-*`.
  - Added 2 offline graph tests.
  - The Aura projection reconciled, and a re-run was idempotent.
  - Added doc 19 (gotchas).

- 2026-10-05:
  - Migration 010 applied to Neon.
  - Chapter-1 pilot import, then a full import of both packages, then an idempotent re-run (0 new / 0 updated).
  - 8 offline unit tests pass.
