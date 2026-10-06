# REST, OpenAPI, web proxy, and agent HTTP reference

## Evidence

- Evidence mode: source-derived only.
- Source revision: `43c3316d5b6f8a838874de4aa384cb28ef00aa1a`, with uncommitted worktree changes included (fluid/live refresh 2026-10-06).
- Sources: `mathbank-rest/src/mathbank_rest/main.py`, routers under `routers/` including `step_runtime.py`, DB modules under `db/`, `security.py`, `pedagogy.py`, `tutor.py`, `enrichment.py`, `relationship_enrichment.py`, `step_runtime.py`, `step_tutor.py`, `step_diagnosis.py`, `step_recovery.py`, `agent_transcripts.py`, `routers/agent_sessions.py`, `db/textbook_admin.py`, `routers/admin_textbooks.py`, `db/import_admin.py`, `routers/admin_imports.py`, `app/api/rest/admin/imports/[[...path]]/route.js`, `lib/adminImportsProxy.mjs`, `mathbank-agent/agents/mathbank_tutor/tools/step_runtime_tools.py`, `mathbank-web/app/api/**`, especially `app/api/rest/solve/[...path]/route.js`, `app/api/rest/admin/knowledge-gaps/route.js`, `app/api/agent/session/route.js`, `app/api/rest/learner/conversations/[[...path]]/route.js`, `app/api/rest/admin/conversations/route.js`, `app/api/rest/admin/textbooks/[...path]/route.js`, `lib/adminTextbooksProxy.mjs`, `lib/agentIdentity.mjs`, `lib/solveProxy.mjs`, `lib/adminGapsProxy.mjs`, `app/admin/(protected)/knowledge-gaps/page.jsx`, and `app/learn/solve/[code]`, `mathbank-agent/server.py`, `session_config.py`; 2026-10-06 additions: `routers/live.py`, `routers/fluid.py`, `live_runtime.py`, `authoring.py`, `widgets.py`, `math_format.py`, `mathbank-agent/agents/mathbank_tutor/tools/widget_tools.py`, `mathbank-widgets/src/server.mjs`, `mathbank-web/app/api/{voice,format-math}/**`, `mathbank-live/{server.mjs,lib/gateway.mjs,lib/events.mjs,app/api/**}`.
- OpenAPI snapshot: [openapi.json](openapi.json), generated from `app.openapi()` without starting a server. Snapshot validation observed OpenAPI `3.1.0`, 138 paths, and 65 component schemas. Generation observation: 2026-10-06 (UTC), after `POST /v1/search/concepts` (taxonomy concept search) was registered.
- No endpoint handlers were invoked and no running service drift was checked.

## Auth mechanisms

| Surface | Auth mechanism | Source |
|---|---|---|
| Public corpus/search/tutor scaffold routes | No auth dependency | `routers/v1.py`, `routers/tutor.py`, `routers/pedagogy.py` |
| Learner and step-runtime protected routes | HTTP bearer JWT via `HTTPBearer`; token subject is `student_id` | `security.get_current_student_id` |
| Learner register/login | No bearer required; returns access token | `routers/learner.py` |
| Admin routes and internal step outcome route | `X-Admin-Api-Key` header checked against configured admin key | `security.require_admin_api_key` |
| Live/fluid routes (`routers/live.py`) | `live_actor`: admin key → actor INSTRUCTOR `instructor:{X-Actor-Id}`, or student bearer → STUDENT `student:{uuid}`; `staff_actor` additionally requires INSTRUCTOR/ADMIN (403 otherwise). `/v1/tutor/sessions/*` with the admin key acts as AI_TUTOR. | `routers/live.py` (`live_actor`, `staff_actor`) |
| Widgets / format-math (`routers/fluid.py`) | `staff_or_student`: admin key or student bearer; registry is public; store/list/review are admin-key only; all `/v1/authoring/*` are admin-key only | `routers/fluid.py` |
| Web app proxies | Browser/session-level cookies for app auth wrappers; server-side proxies forward REST/agent calls | `mathbank-web/app/api/**` |
| ADK agent server | ADK FastAPI app manages its own app/user/session URL structure; MathBank server configures DB-backed sessions | `mathbank-agent/server.py` |

## FastAPI route inventory

OpenAPI operation IDs are in `openapi.json`. Status/error notes include implemented `HTTPException` paths and framework validation.

| Method | Path | Auth | Request model/params | Success | Errors/side effects |
|---|---|---|---|---|---|
| GET | `/health` | none | none | DB health object | 503 if Postgres or Neo4j check fails; performs read-only connectivity queries. |
| GET | `/health/postgres` | none | none | Postgres health | 503 on failure. |
| GET | `/health/neo4j` | none | none | Neo4j health | 503 on failure. |
| GET | `/v1/competitions` | none | none | list of competition dicts | Read-only. |
| GET | `/v1/problems` | none | query: `competition`, `year_min`, `year_max`, `concept`, `technique`, `limit<=200`, `offset>=0` | list of problem summaries | Read-only. |
| GET | `/v1/problems/by-code/{canonical_code}` | none | path code | problem detail | 404 if not found. |
| GET | `/v1/concepts` | none | `domain`, `limit<=200`, `offset>=0` | list | Read-only. |
| GET | `/v1/concepts/{slug}/problems` | none | `limit<=200`, `offset>=0` | list of problems | Read-only. |
| GET | `/v1/concepts/{slug}/neighbors` | none | slug | graph-like concept neighbors | Read-only Postgres query. |
| GET | `/v1/techniques` | none | `limit<=200`, `offset>=0` | list | Read-only. |
| GET | `/v1/techniques/{slug}/problems` | none | `limit<=200`, `offset>=0` | list | Read-only. |
| GET | `/v1/corpus/coverage` | none | none | coverage rows | Read-only. |
| GET | `/v1/analytics/weak-concepts` | none | `min_students>=1`, `limit<=100` | aggregate concept weakness rows | Cohort aggregate only; no PII fields returned by query. |
| POST | `/v1/search/concepts` | none | `ConceptSearchRequest` (`query` 1..500, `node_types` ⊆ DOMAIN/CONCEPT/SUBCONCEPT/SKILL/TECHNIQUE, `chapter_number 1..100`, `retrieval.{semantic,lexical}`, `limit 1..50`) | `{query, results[{taxonomy_node_id,node_type,name,parent_node_id,parent_name,chapter_number,section_number,slug,slug_kind,problem_count,example_problem_codes,rrf_score,semantic_rank,lexical_rank}], retrieval, warnings}` | 422 blank query/unknown node type; 400 if both sources disabled; semantic ranking calls the embedding provider and falls back to lexical with a warning on failure. Read-only. |
| POST | `/v1/search/problems` | none | `ProblemSearchRequest` (`query`, filters, retrieval booleans, order, `limit 1..100`) | hybrid search result dict | 422 blank query; 400 if all retrieval sources disabled; semantic search can call embedding provider when enabled. |
| POST | `/v1/learner/register` | none | `RegisterRequest` email, password 8..200, first/last name | `AuthResponse`, status 201 | 409 duplicate email; writes student profile; hashes password; returns JWT. |
| POST | `/v1/learner/login` | none | `LoginRequest` | `AuthResponse` | 401 invalid credentials; 403 inactive account; updates last login; returns JWT. |
| GET | `/v1/learner/me` | bearer | none | profile dict | 401 auth errors; 404 missing student. |
| POST | `/v1/learner/attempts` | bearer | `AttemptRequest` | status 201, attempt + updated mastery | 404 unknown problem; writes attempt and recomputes mastery caches. |
| GET | `/v1/learner/attempts` | bearer | `limit`, `offset` | recent attempts list | Limits clamp to max 200 and offset nonnegative in implementation. |
| GET | `/v1/learner/mastery` | bearer | none | concepts/techniques mastery summary | Read-only. |
| GET | `/v1/learner/mastery/improvement-plan` | bearer | `max_focus_areas` default 5 | focus plan | Read-only recommendations from mastery + problem lookups. |
| POST | `/v1/students/{student_id}/problems/{problem_ref}/attempts` | bearer + matching path student | path student UUID, problem UUID or canonical code, optional `Idempotency-Key` | status 201, solve attempt id/resume flag + safe runtime view | 403 if path student differs from token; 404 unknown problem; 409 invalid transition/no published steps; writes solve attempt/runtime state/events/outbox/idempotency. |
| GET | `/v1/attempts/{attempt_id}` | bearer | attempt UUID | safe runtime view | 404 if missing/not owner; never returns canonical step text. |
| GET | `/v1/attempts/{attempt_id}/runtime` | bearer | attempt UUID | same as above | Alias of runtime view. |
| POST | `/v1/attempts/{attempt_id}/steps/{step_id:path}/responses` | bearer | `StepResponseRequest(response_text, state_version, evaluate=true)`, optional `Idempotency-Key` | saved response fields plus `evaluation_status`; when evaluated, redacted student evaluation and possibly advanced state/mastery | Route uses `{step_id:path}` because step IDs contain `/`. First commits response, then grades outside the row lock. `evaluation_status`: `EVALUATED`, `PENDING` if superseded/stale on apply, `UNAVAILABLE` if grading failed after save. 409/422 runtime errors as above. |
| POST | `/v1/attempts/{attempt_id}/steps/{step_id:path}/hint` | bearer | `VersionedRequest(state_version)`, optional `Idempotency-Key` | help level/kind, `hint_text`, `hint_source`, new state version | Route uses `{step_id:path}`. Increments help level to max 5, writes event, then returns generated/cached/fallback hint text; level 5 returns reference step. 409/422 as above. |
| GET | `/v1/attempts/{attempt_id}/steps/{step_id:path}/hints` | bearer | path attempt/step | revealed hints for levels `1..help_level_used` | Route uses `{step_id:path}`. 404 if step not in attempt; may fill missing cached levels via hint writer. |
| POST | `/v1/attempts/{attempt_id}/steps/{step_id:path}/outcome` | admin key | `StepOutcomeRequest(result, state_version, actor_type, evaluation)`, optional `Idempotency-Key` | applied state, next current step or completion, state version; on completion updated mastery | Internal evaluated-result route; students cannot self-grade. Stores full evaluator evidence server-side; student view is redacted. Phase 9 hooks update open gap statuses and may auto-diagnose repeated failures inside a savepoint. 409 stale/invalid transition; may write legacy `learner.attempt` and recompute mastery. |
| POST | `/v1/attempts/{attempt_id}/steps/{step_id:path}/diagnose` | bearer | optional `DiagnoseRequest(trigger='STUDENT_REQUEST')` | redacted diagnosis view plus `reused` flag | Route uses `{step_id:path}`. Ranks deterministic gap hypotheses for a presented step, reuses existing diagnosis for identical evidence, writes diagnosis/hypothesis rows/events/outbox, and does not change runtime mode, mastery or `state_version`. |
| GET | `/v1/attempts/{attempt_id}/diagnoses` | bearer | attempt UUID | redacted diagnosis views newest first | 404 if missing/not owner. Student view hides failure modes, raw confidence and evidence. |
| GET | `/v1/admin/attempts/{attempt_id}/diagnoses` | admin key | attempt UUID | full diagnosis rows | Internal view includes failure modes, confidence and evidence; 404 if attempt missing. |
| GET | `/v1/admin/students/{student_id}/knowledge-gaps` | admin key | `status` optional enum, `limit 1..500` | full knowledge-gap hypothesis rows | Internal cross-attempt view for one student; optional exact status filter. |
| GET | `/v1/admin/knowledge-gaps` | admin key | `status` optional enum, `student` email substring or UUID, `limit 1..500` | totals, common open targets, recent gap rows with latest recovery plan id/status | Read-only Phase 10 admin overview; includes whether a diagnosis was AI re-ranked but not private model payloads. |
| POST | `/v1/attempts/{attempt_id}/recovery-plans` | bearer | `RecoveryCreateRequest(state_version, trigger=STUDENT_REQUEST|DIAGNOSIS, gap_diagnosis_id?)`, optional `Idempotency-Key` | status 201, plan view + `resumed` + state version | Starts a persisted detour from the current step, writes plan/items/events/outbox, marks the origin step DETOURED, enters `RECOVERY`; 409 stale/invalid/no material. |
| GET | `/v1/attempts/{attempt_id}/recovery-plans` | bearer | attempt UUID | recovery plan views newest first | Student-owned list; item content follows safe plan-view rules. |
| GET | `/v1/recovery-plans/{plan_id}` | bearer | plan UUID | recovery plan view | 404 if not owned; current/finished item content only, answers only after an item is finished. |
| GET | `/v1/recovery-plans/{plan_id}/next` | bearer | plan UUID | current item, mastery progress, return flag | Read-only pointer for the active/current recovery item. |
| POST | `/v1/recovery-plans/{plan_id}/items/{item_id}/responses` | bearer | `RecoveryItemResponse(state_version, choice_index?, response_text?, acknowledged?)`, optional `Idempotency-Key` | graded result, adaptation transition, state version, plan view | MCQs grade deterministically; subproblems use the step evaluator outside the lock; worked examples acknowledge. May retry, add confirmation/alternate items, branch to a child plan, complete or exhaust. |
| POST | `/v1/recovery-plans/{plan_id}/resume` | bearer | `VersionedRequest`, optional `Idempotency-Key` | returned origin step id, plan status, state version | Requires a completed/exhausted detour; returns to the exact origin step and mode `SOLVING`. |
| POST | `/v1/recovery-plans/{plan_id}/abort` | bearer | `VersionedRequest`, optional `Idempotency-Key` | returned origin step id, aborted plan status, state version | Ends open plan family as `ABORTED`, skips remaining items, returns to origin step. |
| GET | `/v1/admin/recovery-plans` | admin key | optional `student_id`, `status`, `limit 1..500` | plan summaries with counts | Read-only teacher list across recovery plans. |
| GET | `/v1/admin/recovery-plans/{plan_id}` | admin key | plan UUID | one plan plus `items_teacher` evidence | Internal teacher view includes grader evidence, responses and item outcomes. |
| POST | `/v1/learner/agent-sessions` | bearer | `AgentSessionLinkRequest(agent_session_id 1..200, surface=HOME_CHAT|SOLVE_WORKSPACE|OTHER, context dict)` | `{agent_session_link_id, created, agent_session_id, agent_app_name, surface}` | Idempotent link of an ADK session created under this student's id. 404 `NOT_FOUND` if the ADK session does not exist for this student or the agent store is absent; 409 `SESSION_OWNED_BY_ANOTHER_STUDENT`; 400 bad surface. Writes `learner.agent_session_link`. |
| GET | `/v1/learner/agent-sessions` | bearer | `limit 1..200` default 50 | list of linked sessions (counts, first message, UTC timestamps) | Read-only; own sessions only, newest first. |
| GET | `/v1/learner/agent-sessions/{agent_session_id}/transcript` | bearer | session id | `{agent_session_id, agent_app_name, student_id, surface, context, created_at, updated_at, messages[]}` | Own linked sessions only, else 404. Messages are user text and tutor replies only. |
| GET | `/v1/admin/agent-sessions` | admin key | `student` (e-mail substring or UUID, ≤200), `limit 1..500` default 100 | `{linked[], unlinked_count}` | Read-only list across students plus count of unlinked (anonymous) ADK sessions. |
| GET | `/v1/admin/agent-sessions/{agent_session_id}/transcript` | admin key | session id | transcript plus `email`, `agent_user_id`, `linked`; messages include thinking, tool calls and tool results truncated to 2,000 chars | Works for unlinked sessions; 400 if an unlinked id is ambiguous across ADK users; 404 if absent. |
| GET | `/v1/admin/textbooks/coverage` | admin key | `book` (`^[A-Z0-9_]+$`, default `PRASOLOV_PGV1`), `graph` bool default true | `{book_code, packages[], files[], matrix[], conflicts[], graph_ok, graph_error, chapters[]}` | Read-only. Matrix rows: `entity, source_rows, postgres, vector, graph, expected[], gaps[], status (OK, GAP, UNKNOWN, PROVENANCE), note`. Neo4j failure is non-fatal (`graph_ok=false`). See [24](../24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md). |
| GET | `/v1/admin/textbooks/problems` | admin key | `book`, `chapter 1..99`, `q ≤200`, `node ≤200`, `has_diagram`, `has_solution`, `limit 1..200` default 50, `offset ≥0` | `{total, limit, offset, items[]}` | Read-only problem list with solution/step/item/diagram counts and an `embedded` flag. |
| GET | `/v1/admin/textbooks/problems/{code}` | admin key | canonical code | head + `enrichment`, `taxonomy_names`, `solutions[]`, `parts[].steps[]`, `unassigned_steps[]`, `dependencies[]`, `learning_items[]`, `diagrams[]`, `vector`, `graph` | 404 if unknown. Includes official answers, correct answers and `SOLUTION_HIDDEN` diagrams (admin only). |
| GET | `/v1/admin/textbooks/learning-items` | admin key | `book`, `transformation_type`, `chapter`, `q`, `limit 1..200`, `offset` | `{total, limit, offset, types[], items[]}` | Read-only. |
| GET | `/v1/admin/textbooks/taxonomy` | admin key | `book`, `node_type` ∈ DOMAIN/CONCEPT/SUBCONCEPT/SKILL/TECHNIQUE, `q`, `limit 1..500` default 100, `offset` | `{total, limit, offset, types[], items[]}` | Per-node problem/step/edge counts. |
| GET | `/v1/admin/textbooks/taxonomy/{node_id}` | admin key | node id ≤200 | node + `children[]`, `edges[]` (≤500), `problems[]` (≤50) | 404 if unknown. |
| GET | `/v1/admin/textbooks/diagrams/{source_diagram_id}/image` | admin key | `source_diagram_id` `^[A-Za-z0-9_.-]+$` ≤100, `book` | PNG `FileResponse`, `Cache-Control: private, max-age=3600` | 404 if the row or file is missing, or the path resolves outside the repository root. `diagram_id` itself is text containing `/`, so it is never used in the URL. |
| POST | `/v1/attempts/{attempt_id}/submit` | bearer | `VersionedRequest`, optional `Idempotency-Key` | `SUBMITTED`, new state version | Early hand-in; writes event/runtime mode but does not create mastery outcome. |
| GET | `/v1/students/{student_id}/events` | bearer + matching path student | optional `attempt_id`, `limit 1..500` | append-only event list | 403 if path student differs from token. |
| GET | `/v1/solution-steps/{step_id:path}/practice` | bearer | `limit 1..20`, `same_skill` bool | similar step-practice candidates from other problems; `embedding_available` flag | Route uses `{step_id:path}`. 404 if step missing/unpublished; uses stored anchor embedding when available and never returns step text. |
| GET | `/v1/problems/by-code/{code}/diagrams` | none | canonical problem code | list of `problem_image_id`, `ordinal` | Read-only problem-statement diagrams for solve workspace; solution-hidden diagrams are not returned. |
| GET | `/v1/problem-images/{image_id}` | none | image UUID | file response with cache header | 404 if DB row/path missing, path is outside repository root, or file absent. |
| POST | `/v1/admin/competitions` | admin key | `CompetitionRequest` | competition dict | Upserts `core.competition`. |
| POST | `/v1/admin/papers` | admin key | `PaperRequest` | status 201 | Validates paper code and source kind; upserts `pipeline.pdf_source`; does not run ingestion. |
| POST | `/v1/admin/papers/batch` | admin key | `PapersBatchRequest` | status 201 | Registers each paper as above. |
| GET | `/v1/admin/papers` | admin key | `competition`, `status`, `limit<=500`, `offset>=0` | paper/source rows | Read-only status. |
| POST | `/v1/admin/papers/{paper_external_code}/retry` | admin key | path code | reset status dict | 404 unknown; resets failed stage columns to PENDING. |
| GET | `/v1/admin/pipeline/runs` | admin key | `limit<=200` | runs and graph projections | Read-only. |
| GET | `/v1/admin/pipeline/jobs` | admin key | `competition`, `paper`, `limit 1..100`, `offset>=0` | detailed job status | Read-only rollup. |
| POST | `/v1/tutor/decompose` | none | `DecomposeRequest(problem_code, max_steps 1..5)` | decomposition dict | 404 for unknown problem; may invoke tutor logic/model depending implementation path. |
| POST | `/v1/tutor/check-subproblem` | none | `CheckSubproblemRequest` | check dict | May invoke tutor logic/model. |
| GET | `/v1/tutor/learning-context/{problem_code}` | none | path code | teaching context | Calls `ensure_learning_metadata`; can trigger automatic enrichment and publish if metadata is missing/unpublished; 404/502/503 handled. |
| GET | `/v1/tutor/prerequisites/{skill_slug}` | none | `max_depth 1..8` | prerequisite path | 404 unknown; 503 data unavailable. |
| GET | `/v1/tutor/practice/{problem_code}` | none | `limit 1..20` | easier practice | 404/503 as above. |
| POST | `/v1/tutor/coach` | none | `CoachRequest` in `mathbank_rest.pedagogy` | coaching response | Ensures learning metadata; can trigger enrichment/model path; 502 for coaching/enrichment failures. |
| GET | `/v1/admin/pedagogy/queue` | admin key | `kind`, `status`, `limit 1..100`, `offset>=0` | queue + counts/fingerprint | Read-only; status defaults PENDING. |
| POST | `/v1/admin/pedagogy/review` | admin key | `ReviewRequest` | status/revision/message | 404 missing, 409 stale/conflict, 422 invalid; writes decision/audit. |
| POST | `/v1/admin/pedagogy/history` | admin key | `EntityRequest` | review history | 404/422 via validation helpers. |
| POST | `/v1/admin/pedagogy/publish` | admin key | `PublishRequest` expected fingerprint | publication result | Writes Neo4j and Postgres publication rows; 409 stale fingerprint; 503 DB/graph failure. |
| POST | `/v1/admin/pedagogy/bulk-review` | admin key | `BulkReviewRequest` | bulk result | Atomic DB review decisions; same conflicts. |
| POST | `/v1/admin/pedagogy/approve-starter` | admin key | `StarterReviewRequest` | bulk approval result | Approves starter manifest items if fingerprint matches. |
| POST | `/v1/admin/pedagogy/edit` | admin key | `EditRequest` | edit result | Validates editable fields; writes audit; publish required for graph update. |
| POST | `/v1/admin/pedagogy/reclassify` | admin key | `ReclassifyRequest(problem_code)` | enrichment result | Calls automatic enrichment with `force=True`; can call paid model when invoked. |
| GET | `/v1/admin/imports/packages` | admin key | `book?` | package list with status, open conflicts, reconciled flag | Read-only. |
| GET | `/v1/admin/imports/packages/{package_id}` | admin key | uuid | package + status events, files, conflict summary, reconciliation | 404 unknown. |
| GET | `/v1/admin/imports/packages/{package_id}/issues` | admin key | `entity_type?`, `kind ALL|REJECTED|WARNINGS`, `limit 1..500`, `offset` | rejected/warning staging rows | Read-only. |
| GET | `/v1/admin/imports/packages/{package_id}/conflicts` | admin key | `entity_type?`, `resolution_status?`, `limit`, `offset` | paged conflicts | Read-only. |
| POST | `/v1/admin/imports/conflicts/{conflict_id}/decision` | admin key | `{decision: KEEP_EXISTING|ACCEPT_INCOMING|MERGE_MANUALLY, note?}` | updated conflict | 404/422; records decision + audit row (data applied on re-import). |
| GET | `/v1/admin/imports/reconciliation` | admin key | `book` (default Prasolov), `graph=true` | Postgres ↔ graph ↔ vector counts, model profile, queue | Reads Neo4j when `graph=true`; 503 if graph unavailable. |
| GET | `/v1/admin/imports/projection-requests` | admin key | `status?`, `limit` | queue rows | Read-only. |
| POST | `/v1/admin/imports/projection-requests` | admin key | `{target, scope_type, scope_id, note?}` | **202** request row | Queues only; never runs a projector or paid embeddings; coalesces open duplicates. |
| POST | `/v1/admin/imports/learning-items/{learning_item_id}/review` | admin key | `{decision: APPROVE|REJECT|NEEDS_REVISION, note?}` | updated item | 404/422; `approval_method='human'`; audit + `LEARNING_ITEM_PUBLISHED/WITHDRAWN` outbox on change. |
| GET | `/v1/admin/imports/problems/{code}/dag` | admin key | problem canonical code | steps, dependencies, review, recent actions | 404 unknown problem. Returns step text (admin-only). |
| PATCH | `/v1/admin/imports/steps/{step_id:path}` | admin key | `{skill_node_id?, is_checkpoint?, note?}`; step id may contain `/` and `#` (URL-encode) | updated step | 404; 422 "nothing to change"; sets `admin_edited_at`; audit + `SOLUTION_STEP_CHANGED`. |
| PUT | `/v1/admin/imports/dependencies` | admin key | `{from_step_id, to_step_id, relationship_type, previous_type?, note?}` | upserted edge | 404/422; **409** if a `DEPENDS_ON` edge would create a cycle; human-protected. |
| POST | `/v1/admin/imports/dependencies/reject` | admin key | `{from_step_id, to_step_id, relationship_type, note?}` | rejected edge | 404; graph projector prunes it. |
| POST | `/v1/admin/imports/problems/{code}/dag/review` | admin key | `{status: APPROVED|NEEDS_REVISION, note?}` | DAG review row | 404/422; upsert + audit. |
| GET | `/v1/admin/imports/actions` | admin key | `target_type?`, `limit` | append-only audit trail | Read-only. |

## Fluid widget, authoring and live session routes (migration 020; docs 27/28/29)

Auth codes: **A** = admin key only; **S** = `staff_actor` (admin key as INSTRUCTOR); **L** = `live_actor` (admin key or student bearer; students must be participants); **SS** = `staff_or_student`; **T** = admin key acting as `AI_TUTOR`; **P** = public.
Mutating live routes accept `client_command_id` (idempotent via `live.command_receipt`, a repeat returns the stored result with `duplicate: true`) and, for staff/AI, `expected_session_version` (409 `STALE_VERSION`). Every accepted live mutation appends `live.session_event` rows and `pipeline.outbox_event` rows in the same transaction. OpenAPI documents only 2xx/422 for these routes; the codes in the last column are raised by `LiveError`/`AuthoringError`/`HTTPException` and are **not** declared in the snapshot (contract gap).

| Method | Path | Auth | Request | Notes / errors |
|---|---|---|---|---|
| GET | `/v1/authoring/presentation-plans` | A | `limit` | Plan list. |
| POST | `/v1/authoring/presentation-plans` | A | `PlanIn` (plan_key, title, limits, topics) | **201** DRAFT plan; 422 `INVALID_PLAN`. |
| GET | `/v1/authoring/presentation-plans/{plan_id}` | A | — | Plan + topics; 404 `NOT_FOUND`. |
| PUT | `/v1/authoring/presentation-plans/{plan_id}/topics` | A | `TopicsIn` | Replaces topics (delete + insert); 409 `PLAN_IMMUTABLE` when PUBLISHED. |
| PATCH | `/v1/authoring/presentation-plans/{plan_id}/timing` | A | `TimingIn` | Course limit/buffer/hard limit; 409 `PLAN_IMMUTABLE`. |
| POST | `/v1/authoring/presentation-plans/{plan_id}/validate` | A | — | Validation report (time budget vs limit, ordinals). |
| POST | `/v1/authoring/presentation-plans/{plan_id}/approve` | A | — | DRAFT → APPROVED; 422 `INVALID_PLAN`. |
| POST | `/v1/authoring/presentation-plans/{plan_id}/publish` | A | — | APPROVED → PUBLISHED; supersedes the previous PUBLISHED plan with the same key; 409 `NOT_APPROVED`. |
| POST | `/v1/authoring/presentation-plans/{plan_id}/new-version` | A | — | **201** DRAFT copy with version+1 and `parent_plan_id`. |
| POST | `/v1/authoring/chat/sessions` | A | `ChatIn` (plan_id) | **201** admin chat bound to a plan. |
| GET | `/v1/authoring/chat/sessions/{chat_id}` | A | — | Chat + messages. |
| POST | `/v1/authoring/chat/sessions/{chat_id}/messages` | A | `MessageIn` (text) | Deterministic intent parse → PROPOSED patch with operations + impact; nothing applied. |
| GET | `/v1/authoring/chat/sessions/{chat_id}/proposed-patches` | A | — | Patch list. |
| POST | `/v1/authoring/chat/sessions/{chat_id}/proposed-patches/{patch_id}/apply` | A | `PatchDecision` (`APPLY`/`REJECT`/`MODIFY`/`ASK_FOR_ALTERNATIVE`, operations?) | APPLY validates all operations atomically; 409 `PATCH_DECIDED`/`PLAN_IMMUTABLE`; 422 `INVALID_PATCH`/`INVALID_ACTION`. |
| GET | `/v1/live/sessions` | S | `limit` | Session list. |
| POST | `/v1/live/sessions` | S | `SessionIn` (plan_id, title?) | **201** SCHEDULED session with join code; 404 `PLAN_NOT_FOUND`; 409 `PLAN_NOT_APPROVED`. |
| POST | `/v1/live/sessions/join` | L | `JoinIn` (join_code, display_name?) | Upserts participant; 404 `JOIN_CODE_NOT_FOUND`; 409 `SESSION_ENDED`. |
| GET | `/v1/live/sessions/{sid}/state` | L | — | Role-filtered state (students never get recommendations/handoff/correct answers before reveal); 403 `NOT_A_PARTICIPANT`. |
| GET | `/v1/live/sessions/{sid}/events` | L | `after_sequence`, `limit` | Ordered replay filtered by audience. |
| POST | `/v1/live/sessions/{sid}/commands` | L | `CommandIn` (command_type, payload, client_command_id, expected_session_version?) | Generic command (students: `RESPONSE_SUBMIT`, `HINT_REQUEST`, `QUESTION_ASK`, `MARK_CONFUSED`, `WIDGET_INTERACT`); 403 `FORBIDDEN_COMMAND`; 400 `UNKNOWN_COMMAND`; 409 `STALE_VERSION` etc. |
| POST | `/v1/live/sessions/{sid}/transition` | S | `TransitionIn` (START/NEXT/BACK/SKIP/GOTO/COMPLETE/…) | 409 `ALREADY_STARTED`/`NOT_STARTED`/`LAST_TOPIC`/`FIRST_TOPIC`/`NO_SUCH_TOPIC`/`HARD_LIMIT`. |
| POST | `/v1/live/sessions/{sid}/pause` | S | `VersionedIn` | 409 `ALREADY_PAUSED`; stops the clock. |
| POST | `/v1/live/sessions/{sid}/resume` | S | `VersionedIn` | 409 `NOT_PAUSED`; adds paused time to `paused_total_seconds`. |
| GET | `/v1/live/sessions/{sid}/time` | S | — | Server-authoritative time state (elapsed, remaining, variance, optional topics, recommendations). |
| POST | `/v1/activities/definitions` | S | `ActivityIn` | **201** definition; 422 `ACTIVITY_INVALID` (unknown `activity_type`). |
| POST | `/v1/live/sessions/{sid}/activities` | S | `ActivityIn` (definition_id or inline) | Opens an instance; 404 `ACTIVITY_DEFINITION_NOT_FOUND`. |
| POST | `/v1/live/sessions/{sid}/activities/{aid}/responses` | L | `ResponseIn` (option/value, confidence 1–5) | One response per participant, resubmission replaces while OPEN; 409 `ACTIVITY_CLOSED`. |
| GET | `/v1/live/sessions/{sid}/activities/{aid}/aggregate` | L | — | Counts/percentages; students get it only after reveal (403 `NOT_REVEALED`). |
| POST | `/v1/live/sessions/{sid}/activities/{aid}/close` | S | `VersionedIn` | Stops responses; 409 `NO_OPEN_ACTIVITY`. |
| POST | `/v1/live/sessions/{sid}/activities/{aid}/reveal` | S | `VersionedIn` | Reveals the aggregate to students, emits a `POLL_RESULT` widget and a `POLL_BRANCH` recommendation. |
| POST | `/v1/live/sessions/{sid}/widgets` | S | `WidgetIn` (spec or intent, persistence) | Validates then shows; 422 `WIDGET_INVALID`/`WIDGET_OPERATIONS_INVALID`. |
| PATCH | `/v1/live/sessions/{sid}/widgets/{wid}/state` | S | `WidgetStateIn` (operations) | 404 `WIDGET_INSTANCE_NOT_FOUND`. |
| DELETE | `/v1/live/sessions/{sid}/widgets/{wid}` | S | query `expected_session_version`, `client_command_id` | Hides widget. |
| POST | `/v1/instructor/live/{sid}/overrides` | S | `OverrideIn` (TAKEOVER/RELEASE/LOCK_AGENT/UNLOCK_AGENT/EXTEND/SHORTEN/…) | 409 `ALREADY_TAKEN_OVER`/`NO_ACTIVE_TAKEOVER`; 422 `INVALID_SECONDS`. Takeover/lock mark PROPOSED recommendations STALE. |
| POST | `/v1/instructor/live/{sid}/commands` | S | `NLIn` (text) | Regex NL compiler → AUTO_APPLY commands execute, others become INSTRUCTOR_NL recommendations; 422 `EMPTY_MESSAGE`. |
| GET | `/v1/instructor/live/{sid}/recommendations` | S | `status` | Recommendation list. |
| POST | `/v1/instructor/live/{sid}/recommendations/{rid}` | S | `DecisionIn` (ACCEPT/REJECT) | 404 `RECOMMENDATION_NOT_FOUND`; 409 `RECOMMENDATION_DECIDED`. |
| GET | `/v1/instructor/live/{sid}/handoff` | S | `scope`, `scope_id` | Handoff packet (recent questions/confusion/responses); also emitted as `instructor.handoff_packet`. |
| GET | `/v1/realtime/sessions/{sid}` | L | — | Socket URL/rooms hint for clients. |
| GET | `/v1/tutor/sessions/{sid}/context` | T | `participant_id` | Context for the AI tutor (state, time, recent events). |
| POST | `/v1/tutor/sessions/{sid}/actions` | T | `TutorActionIn` | Proposal only → `live.recommendation`; auto-applied for the AUTO_APPLY set when AI_ACTIVE; 403 `AI_PROPOSES_ONLY`; 422 `UNKNOWN_ACTION`. |
| POST | `/v1/tutor/sessions/{sid}/messages` | T | `TutorMessageIn` | `tutor.message` event; **409 `AI_NOT_IN_CONTROL`** during takeover/lock. Responder may call the paid OpenAI model. |
| GET | `/v1/widgets/registry` | P | — | 13 widget types, version, limits, templates. |
| POST | `/v1/widgets/validate` | SS | `SpecBody` | `{valid, errors}`; no persistence. |
| POST | `/v1/widgets/generate` | SS | `GenerateBody` (intent, context) | Deterministic template/compose, validated; no model call. |
| POST | `/v1/widgets/specs` | A | `StoreBody` | **201** stored spec with `content_hash`; 422 invalid. |
| GET | `/v1/widgets/specs` | A | `lifecycle`, `persistence`, `limit` | Spec list (admin gallery). |
| GET | `/v1/widgets/specs/{spec_id}` | SS | — | 404 `WIDGET_NOT_FOUND`. |
| POST | `/v1/widgets/specs/{spec_id}/review` | A | `ReviewBody` (NOMINATE/PROMOTE/REJECT) | NOMINATE → `PROMOTION_CANDIDATE`; PROMOTE → `PROMOTED_TO_TEMPLATE` + STATIC (409 `NOT_A_CANDIDATE`). |
| POST | `/v1/tutor/format-math` | SS | `FormatBody` (text ≤4000, mode deterministic/agentic) | `{input, formatted, engine, model?, warnings}`; agentic mode is a small paid model call with deterministic fallback. |

## OpenAPI and Swagger guidance

- FastAPI serves live `/docs`, `/redoc`, and `/openapi.json` when a server is running. Those reflect the running process, not necessarily this source revision.
- The committed [openapi.json](openapi.json) is a source-generated snapshot and must be regenerated when FastAPI source changes.
- OpenAPI captures Pydantic validation and declared response models where present. Many endpoints return plain `dict`/`list[dict]`, so response schemas are intentionally generic. Implementation-specific errors (for example 409 review conflict or 503 graph failure) are not exhaustively declared in OpenAPI and are documented in the table above.

## Step runtime evaluator and hint behavior

`mathbank-rest/src/mathbank_rest/step_tutor.py` owns Phase 8 grading and hints. It loads hidden step context server-side, calls the configured evaluator/hint writer only from route code after the response or hint event commits, and applies leak checks before any failed-step feedback or hint text reaches the browser. The OpenAI client is imported lazily inside model-call helpers; documentation generation imported the app only and did not call these helpers.

Student-safe runtime views now include current-step `goal`, redacted `last_evaluation`, a timeline, and completed-step `reference_text`; future locked steps remain opaque. `StepResponseRequest.evaluate` defaults to `true`; callers can set it false to save without immediate grading, yielding `PENDING`.

## Step gap diagnosis

`mathbank-rest/src/mathbank_rest/step_diagnosis.py` implements Phase 9 deterministic diagnosis without model calls. `POST /v1/attempts/{attempt_id}/steps/{step_id:path}/diagnose` returns a learner-safe view containing focus areas, likelihood labels, recommended action and probe metadata, never raw failure modes, confidence scores, evidence or canonical step text. `get_runtime` includes `current_step.diagnosis` for the latest diagnosis on the current step. Admin routes expose full diagnosis and knowledge-gap evidence behind `X-Admin-Api-Key`.

## Step-level retrieval exposure

`mathbank-rest/src/mathbank_rest/db/step_search.py` implements hard-filtered step and learning-item hybrid retrieval. `similar_steps_for_step` is now exposed through `GET /v1/solution-steps/{step_id:path}/practice` in `routers/step_runtime.py` (OpenAPI renders it as `{step_id}`). General helpers `search_solution_steps(...)` and `search_learning_items(...)` remain internal.

Safety rules from source:

- Hard filters are allow-listed and parameterized before ranking.
- Learning items are rechecked live for `APPROVED`, `student_visible`, and `no_proof`.
- Solution step text is removed from results unless callers explicitly set `include_step_text=True`; the exposed practice endpoint never requests it.
- The exposed practice endpoint uses the anchor step's stored active embedding as `query_vector`, so it does not make a paid query-embedding call. General semantic helper calls can still import `vector_search` lazily and call the embedding provider when no query vector is supplied.

## Web proxy/API routes (`mathbank-web/app/api/**`)

These are Next.js server routes, not FastAPI-owned OpenAPI paths.

| Route family | Purpose |
|---|---|
| `/api/rest/competitions`, `/problems`, `/concepts`, `/techniques`, `/search` | Proxies to FastAPI `/v1/*` corpus/search endpoints. |
| `/api/rest/learner/*` | Proxies learner profile/attempt/mastery endpoints, using web session cookies/tokens. |
| `/api/agent/session` (POST) | Creates the ADK session server-side with a **server-derived** user id (student UUID from the httpOnly cookie, else `anonymous`; client `userId` ignored), treats ADK 409 as idempotent, then links signed-in sessions via `POST /v1/learner/agent-sessions`. Returns `{id, appName, alreadyExists, signedIn, linked}`; same-origin only. |
| `/api/rest/learner/conversations[/{id}]` | Student cookie → `GET /v1/learner/agent-sessions` or `…/{id}/transcript`. Read-only. |
| `/api/rest/admin/conversations[?student=…][?id=…]` | Admin session → `GET /v1/admin/agent-sessions` or `…/{id}/transcript` with the server-held admin key. Read-only. |
| `/api/rest/admin/textbooks/<path>` | Admin session → `GET /v1/admin/textbooks/<path>` with the server-held admin key. Allow-list: `coverage`, `problems`, `problems/{code}`, `learning-items`, `taxonomy`, `taxonomy/{id}`, `diagrams/{source_diagram_id}/image` (streamed). Clamps limits, validates ids/enums/booleans; 401 without a session, 400 for other paths. |
| `/api/rest/admin/*` | Proxies admin competition/paper/pipeline/pedagogy endpoints. |
| `/api/rest/admin/imports/[[...path]]` | Admin session → `/v1/admin/imports/*` with the server-held admin key (`lib/adminImportsProxy.mjs`). GETs are allow-listed (`packages`, `packages/{id}[/issues|/conflicts]`, `reconciliation`, `projection-requests`, `problems/{code}/dag`, `actions`); writes are a single same-origin `POST` with `{action, ...payload}` mapped to `conflict-decision`, `request-projection`, `review-learning-item`, `edit-step`, `upsert-dependency`, `reject-dependency`, `review-dag`. 401 without a session, 400 for unknown paths/actions. Used by `/admin/imports` and the problem page "DAG review" tab. |
| `/api/rest/admin/knowledge-gaps` | Read-only admin-session proxy to FastAPI `/v1/admin/knowledge-gaps`, `/v1/admin/recovery-plans`, and `/v1/admin/recovery-plans/{plan_id}` via an explicit `view=gaps|plans|plan` allow-list; validates statuses, UUIDs and limit. |
| `/api/rest/solve/[...path]` | Allow-listed Next.js proxy for the student solve workspace. It maps friendly paths to FastAPI step-runtime/practice/diagram/image/diagnosis routes, keeps the student JWT in an httpOnly cookie, requires same-origin POST mutations, forwards a bounded `Idempotency-Key`, encodes slash-bearing step IDs as a single upstream path parameter, and deliberately exposes no admin outcome or admin diagnosis routes. The Phase 9 additions are `GET attempts/{id}/diagnoses` and `POST attempts/{id}/diagnose/{step}` in the friendly proxy namespace. Phase 10 adds `GET attempts/{id}/recovery-plans`, `POST attempts/{id}/recovery-plans`, `GET recovery-plans/{id}`, `GET recovery-plans/{id}/next`, `POST recovery-plans/{id}/items/{item}/responses`, and `POST recovery-plans/{id}/resume|abort`. |
| `/api/tutor/[...path]` | Generic proxy to tutor REST paths. |
| `/learn/solve/[code]` | Auth-gated Next.js solve page. It starts/resumes a step attempt, shows timeline/current goal/diagrams, submits responses, displays evaluation feedback, restores revealed hints, links to same-skill practice, and follows the runtime `recovery` pointer through `/api/rest/solve`. |
| `/admin/knowledge-gaps` | Admin protected page for Phase 9/10: shows gap status totals/recent hypotheses, recovery plan summaries, and a selected plan detail table using `/api/rest/admin/knowledge-gaps`. |
| `/api/auth/student-login`, `/student-register`, `/student-logout` | Web session wrappers around learner register/login/logout. |
| `/api/auth/admin-login`, `/admin-logout` | Web admin session wrapper. |
| `/api/graph/overview`, `/api/graph/relationship/[rel]` | Server-side Neo4j graph metadata/relationship views using whitelisted relationships from `graphConfig.js`; not in FastAPI OpenAPI. |
| `/api/agent/session`, `/api/agent/run` | Proxies to ADK agent app/session/run endpoints. |
| `/api/voice/health` (GET), `/api/voice/tts` (POST `{text}` ≤1,200 chars → `audio/mpeg`), `/api/voice/stt` (POST multipart `file` ≤10 MB → `{text}`) | Server-side ElevenLabs proxy (`mathbank-widgets/src/server.mjs` `createVoiceHandlers`; models `eleven_flash_v2_5` / `scribe_v1`). Same-origin only (403), 30 requests/min per caller (429), 503 when `ELEVEN_API_KEY` is unset. TTS/STT are paid; health uses the free models list. |
| `/api/format-math` (POST `{text, mode}`) | `createFormatHandler` → FastAPI `POST /v1/tutor/format-math` with the caller's student/live token; without a token answers deterministically. Same-origin only. |
| `/admin/widgets` | Admin page: widget gallery from `GET /v1/widgets/specs` and the registry, server-side with the admin key. |

### `mathbank-live` (:5174) Next.js routes and Socket.IO surface

Separate deployable (doc [28](../28_DISTRIBUTED_LIVE_PLATFORM.md)); not part of the FastAPI OpenAPI.

| Route | Purpose |
|---|---|
| `/api/auth/student-login`, `/api/auth/admin-login`, `/api/auth/logout` | Same cookie names as `mathbank-web` (`mb_student_token`, `mb_admin_session`). |
| `/api/me` | Current role/identity from cookies. |
| `/api/sessions` | Instructor: list/create live sessions (admin key server-side). |
| `/api/join` | Join by code → `POST /v1/live/sessions/join`. |
| `/api/format-math`, `/api/voice/{health,tts,stt}` | Same shared handlers as `mathbank-web`. |
| Pages `/`, `/login`, `/s/[sid]` (student classroom), `/i/[sid]` (instructor console) | UI. |
| Socket.IO `ws://<host>:5174/socket.io` | `live:join {session_id, last_sequence}` → ack `{ok, role, participant_id, state, events}`; `live:op {session_id, op, args}` → ack `{ok, data}` or `{ok:false, status, error, code}` (ops: `state`, `command`, `respond`, `ask_tutor` [6/min], staff `transition`, `pause`, `resume`, `open_activity`, `close_activity`, `reveal_activity`, `show_widget`, `hide_widget`, `override`, `instructor_nl`, `decide`); server pushes `live:event` (one envelope) to rooms `${sid}|session`, `|student:<id>`, `|group:<id>`, `|instructor`, pumped from `GET /v1/live/sessions/{sid}/events` every 700 ms. Anonymous sockets get `connect_error` `UNAUTHENTICATED`. |

## Agent HTTP surface

`mathbank-agent/server.py` builds the ADK FastAPI app using `google.adk.cli.fast_api.get_fast_api_app` with:

- `agents_dir = mathbank-agent/agents`
- `session_service_uri = mathbank-postgres://sessions`
- database-backed session service registered against the `agent_sessions` schema
- default port 8001 when launched by the operator

The web proxy calls ADK endpoints such as:

- `POST /apps/{app_name}/users/{user_id}/sessions/{session_id}` for session creation.
- `POST /run` or `/run_sse` for agent runs.

Agent step-runtime tools (`tools/step_runtime_tools.py`) call FastAPI with the **student's** bearer token taken from session state `temp:student_token` (set by `lib/agentRunProxy.mjs`); without it they return a sign-in error instead of acting. Tools → routes: `start_step_attempt` → `POST /v1/students/{id}/problems/{code}/attempts`; `get_attempt_runtime` → `GET /v1/attempts/{id}/runtime`; `submit_step_response` → `POST …/steps/{step}/responses`; `request_step_hint` → `POST …/steps/{step}/hint`; `diagnose_step_gap` → `POST …/steps/{step}/diagnose`; `start_recovery_plan` → `POST /v1/attempts/{id}/recovery-plans`; `get_next_recovery_item` → `GET /v1/recovery-plans/{id}/next`; `answer_recovery_item` → `POST /v1/recovery-plans/{id}/items/{item}/responses`; `resume_original_step` → `POST /v1/recovery-plans/{id}/resume`. Mutations send a deterministic `Idempotency-Key`; no admin routes are reachable from the agent.

Concept tools (`tools/rest_tools.py`, 2026-10-06): `search_concepts(query, node_types, chapter_number, limit)` → `POST /v1/search/concepts`; `get_problems_for_technique(technique_slug)` → `GET /v1/techniques/{slug}/problems`. No auth.

Widget tools (`tools/widget_tools.py`, 2026-10-06): `propose_widget(intent, context_json)` → `POST /v1/widgets/generate` (returns a validated spec, or `WIDGET_INVALID` / `SIGN_IN_REQUIRED` for anonymous chats); `format_math(text)` → `POST /v1/tutor/format-math` in deterministic mode only. The agent has 24 tools in total.

The exact ADK OpenAPI/schema is framework-owned and is not generated by `mathbank-rest`.
