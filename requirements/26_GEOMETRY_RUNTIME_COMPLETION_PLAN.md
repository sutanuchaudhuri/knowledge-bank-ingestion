# 26 — Geometry Runtime Completion Plan (Prasolov-only scope)

Closes the 🟡/⏳ rows of the v2 runtime extension for **Prasolov geometry** (`book_code = PRASOLOV_PGV1`,
chapters 1–30). Everything else (non-textbook corpora: olympiad papers, past exams, generated items)
stays **NULL / empty by design** and is populated at runtime by the plan in §3.

Related: tracker [18](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md) · gotchas
[19](19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md) §14 · register [20](20_NOT_YET_IMPLEMENTED.md) ·
pack audit [21](21_V2_PACK_IMPLEMENTATION_AUDIT.md) · schema/API references in [reference/](reference/README.md).

Policies (product owner, 2026-10-05): additive and idempotent migrations only; everything is
**auto-approved** for now (`approval_method = 'automatic'`); human decisions (`approval_method = 'human'`,
`source_type = 'HUMAN'`) are never overwritten by re-import or re-derivation; paid model calls are opt-in.

## 1. Work packages

| WP | Spec (runtime_extension) | Status | Delivered |
|---|---|---|---|
| WP1 Step → Technique | 06 `(:SolutionStep)-[:USES_TECHNIQUE]->`, 07 `technique_ids` | ✅ rule tier · ⏸ paid tier | Migration `017_step_techniques.sql` (`pedagogy.solution_step_technique`, `…_run`); ETL `mathbank-db/etl/derive_step_techniques.py` (rules-v1); projector edge in `mathbank-graph/etl/project_textbook_steps.py`; diagnosis reads it (`step_diagnosis.py`). |
| WP2 Agent step-runtime tools | 12, 13 | ✅ | `mathbank-agent/agents/mathbank_tutor/tools/step_runtime_tools.py`: 9 tools over the deterministic REST runtime; token passed as ADK temp state. |
| WP3 Admin import / reconciliation UI | 15, 05 | ✅ | Migration `019_admin_import_review.sql`; `mathbank-rest/.../db/import_admin.py` + `routers/admin_imports.py` (`/v1/admin/imports/*`); web `/admin/imports`, DAG-review tab and learning-item Approve/Reject on `/admin/textbooks/problems/{code}`; queue drain `mathbank-db/etl/run_projection_requests.py`. |
| WP4 Events, outbox, lifecycle | 08, 16, 03 | ✅ | Migration `018_outbox_consumers.sql`; `mathbank-rest/src/mathbank_rest/outbox_worker.py` (consumers `learner_analytics`, `projection_requests`; stale-attempt abandonment); `PROBLEM_VIEWED`, `STEP_PRESENTED`, `HINT_PRESENTED`, `RECOVERY_ITEM_PRESENTED` emitted. |
| WP5 Diagnosis / recovery remainders | 10, 11 | 🟡 | Remaining: gap → mastery/strength rollup, teacher-assigned detour route, spaced review (NYI-P9, NYI-P10). |
| WP6 Embedded tutor chat in the solve workspace | 12, 14 | ⏳ | Tools exist (WP2); the `/learn/solve/{code}` page still has no chat panel bound to the current attempt. |
| WP7 Rich semantic DAG (paid) | 02 | ⏳ | Schema accepts the full vocabulary; admins can now add/retype/reject edges (WP3). Model-proposed edges with independent verification remain (NYI-P13). |
| WP8 Golden flows A–J | 18 | 🟡 | REST/web/e2e suites cover A–I; J (semantic branch) waits for WP7. |

### WP1 — Step → Technique (detail)

The packages tag techniques per **problem** (`problem_enrichment.technique_ids`); there is no step column.
Tiers, each row carrying `source_type`, `confidence`, `rule_version`:

| Tier | `source_type` | Confidence | Rule |
|---|---|---:|---|
| 1 | `RULE_STEP_TEXT_IN_PROBLEM` | 0.85 | step text names one of the problem's own techniques |
| 1 | `RULE_STEP_TEXT_NAMED` | 0.80 | step names a specific theorem/method (Menelaus, inversion, …) |
| 1 | `RULE_STEP_FORMULA` | 0.90 / 0.70 | formula signature (e.g. `R² − OX²` → power of a point) |
| 2 (paid, opt-in) | `LLM` | model | one call per solution for untagged steps, closed candidate list; `--llm --max-calls N` |
| 3 (planned) | `RUNTIME` | — | tutor-observed technique use on non-textbook corpora (§3) |
| — | `HUMAN` | 1.0 | admin decision; never overwritten |

Observed on Neon 2026-10-06 UTC (read-only `derive_step_techniques.py --status`): 7,814 steps, **3,397 tagged**,
4,354 tags, 52 techniques; outcomes `TAGGED` 3,397 · `NO_MATCH` 3,490 · `NO_PROBLEM_TECHNIQUE` 927.
Rejected designs: "technique supports the step's subconcept" (~12k noisy tags) and "single-technique
problem ⇒ every step uses it" (most steps are setup/algebra).

Commands: `make -C mathbank-db migrate-step-technique-remote`, `textbook-step-techniques-remote`, then
`make -C mathbank-db textbook-graph-remote` (free). The paid tier has **not** been run.

### WP2 — Agent tools (detail)

`start_step_attempt`, `get_attempt_runtime`, `submit_step_response`, `request_step_hint`,
`diagnose_step_gap`, `start_recovery_plan`, `get_next_recovery_item`, `answer_recovery_item`,
`resume_original_step`. The agent owns no state: every mutation calls REST with the server
`state_version` and an idempotency key derived from the ADK function-call id. The student REST token is
put in `temp:student_token` by the web proxy (`lib/agentRunProxy.mjs`) and is stripped before the session
is persisted; anonymous chats get `SIGN_IN_REQUIRED`. Tests: `mathbank-agent/tests/test_step_runtime_tools.py`.

### WP3 — Admin import UI (detail)

| Spec 15 capability | Implementation |
|---|---|
| Package list/status, files, history | `GET packages`, `packages/{id}` → `/admin/imports` Packages tab |
| Validation issues, conflicts + Keep/Accept/Merge | `GET packages/{id}/issues|conflicts`, `POST conflicts/{id}/decision` (decision **recorded**, applied by the next re-import or a DAG edit) |
| Postgres ↔ graph ↔ pgvector reconciliation | `GET reconciliation` (graph optional via `?graph=false`) → Graph & embeddings tab |
| Re-project missing | `POST projection-requests` (202) → `pipeline.projection_request`; drained by `make -C mathbank-db projection-queue-run-remote` (graph, free) / `projection-queue-run-paid-remote` (embeddings, paid) |
| Learning-item review | `POST learning-items/{id}/review` (APPROVE/REJECT/NEEDS_REVISION) → Approve/Reject on the problem's Transformations tab |
| Semantic DAG review | `GET problems/{code}/dag`, `PATCH steps/{id}`, `PUT dependencies`, `POST dependencies/reject`, `POST problems/{code}/dag/review` → DAG review tab |
| Audit | `GET actions` → Audit trail tab; `ingest.admin_review_action` is append-only (trigger) |

All routes require `X-Admin-Api-Key`; the Next.js proxy (`lib/adminImportsProxy.mjs`) allowlists paths and
actions and requires an admin session + same-origin for writes.

### WP4 — Events and outbox (detail)

- Consumers are idempotent through `pipeline.outbox_consumption (outbox_event_id, consumer)` written in the
  same transaction as the side effect.
- `learner_analytics` → `analytics.learner_daily_activity` (rebuildable cache; `learner.event` is the truth).
- `projection_requests` → `pipeline.projection_request` (one open request per target+scope; coalesces).
- Stale attempts: `make -C mathbank-rest abandon-stale-attempts DAYS=30` emits `ATTEMPT_ABANDONED`.
- Retention policy (current): `learner.event` and `ingest.admin_review_action` are append-only and kept
  indefinitely; derived caches may be truncated and rebuilt. Erasure on request is **not implemented**
  (NYI-P6 remainder) and must delete by `student_id` across learner/analytics tables in one transaction.

## 2. Remaining work (ordered)

1. **WP6** chat panel in `SolveWorkspace.jsx` bound to the current `solve_attempt_id` (agent tools already
   enforce state_version/idempotency). Free except for normal tutor model calls.
2. **WP5** gap → mastery rollup (`learner.mastery` update from confirmed/resolved hypotheses), teacher route
   `POST /v1/admin/recovery-plans` with `trigger = 'TUTOR'`, spaced-review scheduling after a completed detour.
3. **WP1 tier 2** (paid) for the 3,490 `NO_MATCH` steps, only after explicit approval and a cost cap.
4. **WP7** model-proposed rich edges, written as `approval_method = 'automatic'` with a verifier, reviewable in
   the DAG-review tab; then golden flow J (WP8).
5. Erasure endpoint for learner data (WP4 remainder).

## 3. Non-Prasolov corpora: NULL policy and runtime population plan

Today only the Prasolov packages have `pedagogy.solution_part/step/dependency`, step techniques, learning
items, DAG reviews and step vectors. Other corpora (`core.problem` rows from papers/exams) have **no rows**
in these tables — this is intended, not a defect; readers must treat absence as "not yet decomposed".

Population at runtime, in order:

1. **Decompose on first use** — when a student opens a non-textbook problem in the solve workspace, a job
   proposes parts/steps from the stored solution (model-assisted, paid; cached per problem) into the same
   `pedagogy.solution_*` tables with `approval_method = 'automatic'` and a synthetic package
   (`ingest.content_package` row marked as runtime-generated — a planned column, not in the schema yet), so reconciliation/admin review work unchanged.
2. **Techniques** — run `derive_step_techniques.py --book <code>` rules on the new steps; tutor-observed uses
   are written as `source_type = 'RUNTIME'`.
3. **Projection** — the step-change outbox events already raise projection requests; drain them (graph free,
   embeddings paid).
4. **Learning items** — generated practice follows the content-engine lifecycle (NYI-AUD-1…5) before it can
   be shown.
5. **Review** — everything appears in `/admin/imports` and the problem DAG tab like Prasolov content.

Until step 1 exists, non-textbook problems use the legacy whole-problem tutor flow.

## 4. Verification

| Check | Command | Last result |
|---|---|---|
| REST unit + live (rolled back) | `cd mathbank-rest && MATHBANK_LIVE_STEP_RUNTIME_TEST=1 .venv/bin/python -m pytest -q tests` | 280 passed, 18 skipped |
| Web unit | `cd mathbank-web && node --test tests/*.test.mjs` | 56 passed |
| Admin e2e (read-only) | `cd mathbank-web && npx playwright test e2e/admin.spec.mjs` | 13 passed |
| Reconciliation | `GET /v1/admin/imports/reconciliation?book=PRASOLOV_PGV1` | graph ok; 0 missing embeddings |
| Outbox | `make -C mathbank-rest outbox-status` | 0 unconsumed |
| Step techniques | `make -C mathbank-db textbook-step-techniques-remote` then `--status` | 3,397 / 7,814 steps tagged |
