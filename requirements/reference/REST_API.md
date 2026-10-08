# REST, OpenAPI, web proxy, and agent HTTP reference

## Evidence

### Tutoring-route deployment follow-up

The user-authorized REST reload exposes staff preview/edit/review/publication/
graph refresh and JWT-owned attempt start/read/assistance. A read-only
deployment check observed **218 mounted paths**; normalized running OpenAPI
matches [the committed snapshot](openapi.json). Unauthenticated access to
`GET /v1/admin/tutoring-routes` returns 401. Bulk operator review remains
separate from student publication. See
[requirement 39](../39_PRECOMPILED_TUTORING_ROUTES.md) for the exact deployment,
approval and active ingestion observations. Older evidence sections below are
historical.

### Geometry scene system

Incremental source revision `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`
with geometry worktree changes. Fresh screened OpenAPI and registered handler
inventory cover **209 paths / 220 operations / 116 schemas**; the complete
catalog numbers below retain their prior dated evidence.

All geometry routes use existing learner JWT or shared staff-key authorization.
Learner owner identities are server-derived; staff core operations use `admin`.
Reads are owner-scoped and private/no-store. Staff diagnostics can explicitly
select another owner; ordinary scene reads cannot.

| Method/path (base `/v1/geometry-scenes`) | Contract/effects |
|---|---|
| POST base | Structured `SceneInput`; 201 accepted version zero; private state/SVG, optional receipt |
| POST `/{scene_id}/deltas` | `StateDelta`; explicit expected version, cumulative immutable update |
| GET `/{scene_id}` | Current owned accepted version |
| GET `/{scene_id}/versions/{version}` | Pinned owned accepted version |
| GET `/{scene_id}/versions/{version}/render` | Private hash-verified SVG with sandbox/nosniff headers |
| POST `/{scene_id}/versions/{version}/validate` | Read-only mathematical/visual validation |
| GET `/{scene_id}/frames` | Owned immutable history metadata |
| POST `/interpret` | `GeometryRequest`; required configured-model reasoning/presentation/review, bounded revision, final CAS |
| GET `/debug/runs?owner=...` | Staff only; optional `limit` 1-100, default 50 |
| GET `/debug/runs/{run_id}?owner=...` | Staff only; source/plans/candidates/validation/provider records |
| POST `/debug/runs/{run_id}/review?owner=...` | Staff decision/note only; never publishes or alters a frame |

Interpretation preserves source text and accepted scene identity. Paired
`scene_id`/`expected_version` are mandatory on updates. `solve_attempt_id`
requires the owning learner and binds canonical problem/current visible step;
geometry never completes/grades that step. Learners cannot supply authoritative
`trusted_facts` or raw PROVEN/DISPROVEN mutations. Givens cannot be demoted.
Source quotes alone cannot turn a target into a proof or disproof.

`Idempotency-Key` is optional, bounded to 200 characters. Accepted retries
reuse the exact receipt and skip paid interpretation. Concurrent first attempts
can both call the model; publication is serialized by final CAS/receipt locks.
Scene/version/caption/current-step/validation/replayed/run-reference and concise
operation statuses are returned by interpretation. Rejected candidates are not
published; exhausted runs provide a safe error/run reference, not private
provider bodies or chain-of-thought.

Important implementation errors: 401 authorization, 403 staff-only diagnostics,
404 ownership-safe not found, 409 stale version/key-body conflict, 422 typed
input/evidence/validation/bounded-plan rejection, 503 private-storage failure.
OpenAPI's untyped dict success responses and documented errors are incomplete
descriptions of these handler rules.

The web uses same-origin `/api/rest/geometry-scenes/...` allowlisted routes.
It fetches accepted SVG as an image, never injects raw SVG or puts tokens in
URLs, and caps navigation at the tutor's pinned version. The registered
`generate_geometry_scene` tool uses invocation-temp learner credentials and
returns a `geometry-scene` fence. Protected staff UI:
`/admin/geometry-scenes?run=RUN_ID&owner=OWNER`.

See [full storage/access semantics](postgres/geometry_scene.md),
[engine README](../../geometry-scene-engine/README.md) and
[requirement 37](../37_GEOMETRY_SCENE_ENGINE.md). Theorem consultation is the
versioned executable geometry catalog, not a general symbolic prover or an
automatic Neo4j publication job.

### Complete operation inventory before geometry integration

Source `375f3743357cef814c50e3c8752f7f4ce2d6ebe5`, clean source tree before docs
changes. [Complete registered endpoint inventory](REST_ENDPOINTS.md) covers
**198 paths / 209 HTTP operations / 102 schemas**, with actual handler links,
authentication dependencies, exact parameters/defaults/validation and documented
request/response/status schemas. [Screened OpenAPI](openapi.json) was regenerated
without starting a service or invoking endpoint handlers.

Separate read-only observation, **2026-10-07 14:50:10 UTC**: running
`http://127.0.0.1:8000/openapi.json` exactly matched source. This is API deployment
parity, not corpus/graph/vector correctness or a paid-provider acceptance test.
No restart or mutation was performed.

Swagger: `http://127.0.0.1:8000/docs`; ReDoc:
`http://127.0.0.1:8000/redoc`; machine contract:
`http://127.0.0.1:8000/openapi.json`. Swagger follows the running service
automatically; the committed source snapshot needs an explicit screened refresh.
Replace the localhost base with the actual configured deployment, not credentials.

Step generation/admin preview/editing/hints/widgets/artifacts request examples
and UI/persistence boundaries:
[complete step-generator workflow/specification](../36_STEP_GENERATOR_AND_AUTHORING.md).
**No universal atomic-step-generation, canonical prose/split/merge/reorder,
video-widget or canonical step-attachment endpoints are implemented.**
The proposed resources in that document are intentionally absent from OpenAPI.

OpenAPI response lists omit many handler-level ownership, provider/storage and
state-conflict errors; untyped dict responses are not contractual Pydantic
response guarantees. Shared-key and staff-or-student dependencies also are not
fully represented as OpenAPI security schemes. Use the mounted-handler inventory
and implementation notes together.

The following incremental evidence sections are historical unless explicitly
reaffirmed by the current complete inventory.

### Admin corpus authoring

Incremental source revision `77eb6784a000a9cc6077526fa4accc7c4111afac` with
relevant worktree changes; inspected `routers/admin_corpus.py`,
`corpus_authoring.py`, admin security, `main.py`, image metadata/serving,
browser corpus proxy and its consumers/tests. Screened source OpenAPI has
**198 paths / 102 schemas**; earlier inventory counts below are historical.

All routes below have prefix `/v1/admin/corpus` and require the shared
`X-Admin-Api-Key` (401 otherwise). Storage failure is not success-shaped;
missing authoring schema is 503, validation is 422, missing problem/draft
is 404, and source/content/review conflicts are 409.

| Method / suffix | Input | Success / effects |
|---|---|---|
| GET `/problems` | Optional exact competition/year/paper/number, code-fragment `q`; `missing_only=true`, limit 1–100 default 20, offset >=0 default 0 | `{items,hasMore,warnings}`; safe-diagram counts and heuristic missing requirement, no mutations |
| GET `/problems/{code}` | Canonical code | Canonical question fields plus SHA-256 `expected_hash`, no mutation |
| GET `/drafts` | state DRAFT/APPROVED/REJECTED default DRAFT, limit/offset as above | `{items,hasMore}` with payload, provenance, revision and review metadata; private admin content |
| POST `/drafts` | Strict DraftRequest: kind TEXT_EDIT/NEW_PROBLEM, statement 10–20,000, solution <=30,000, answer <=500, diagram_required, note 3–2,000; text edits require problem_code and matching expected_hash | 201, private durable draft. New practice rejects supplied official problem identity |
| PUT `/drafts/{uuid}` | Strict DraftUpdate: problem-body fields, note and expected_revision >=1 | Pending NEW_PROBLEM only; increments revision while preserving origin and creation provenance |
| POST `/images` | Strict ImageRequest: canonical code and expected_hash, problem/solution side, PNG/JPEG MIME, bounded base64, source note and rights_confirmed=true | 201 private IMAGE draft. 409 changed source, 415 type/signature, 413 size/dimensions, 422 decoding. Native-resolution normalized PNG stored privately |
| POST `/generate` | Strict GenerateRequest: theme 5–2,000, confirm_paid=true | 201 private AI draft; one configured paid request, never automatic approval. Invalid provider result/provider failure 502; solution required and self-contained visual constraint |
| GET `/drafts/{uuid}/image` | Admin-only draft UUID | PNG bytes; private/no-store and nosniff; object storage failure 503 |
| POST `/drafts/{uuid}/review` | Strict ReviewRequest: APPROVED/REJECTED, note 3–2,000, expected_revision >=1 | `{draft_id,state,canonical_code,warning}`; transactional review/publication or no-op repeated identical decision |

Approval publishes PostgreSQL canonical content, not vector or graph
projections. New practice receives a GENERATED identity and nonofficial paper;
its worked solution remains UNVERIFIED. Solution-image approval does not make
it a student question figure or automatically insert it into solution Markdown.
Text correction preserves source identity/solutions and marks statement vector
representations STALE.

`GET /v1/problem-images/{uuid}` retains the existing student-visibility check.
Approved private-store source figures return normalized PNG; solution figures
remain 404. Private-store failures return 503, never a local-path fallback.

Next.js `GET|POST|PUT /api/rest/admin/corpus/[...path]` is a separate
allowlisted proxy, not a FastAPI endpoint. It requires a signed admin session,
same-origin mutations, attaches the shared key only server-side, preserves
upstream failures and proxies private image bytes with no-store/nosniff.

OpenAPI lists request schemas but these new JSON responses are not typed
response models; their exact shapes above are derived from implementation.
Shared-key security and application-specific 409/413/415/503 behavior are
enforced by code, not fully enumerated in generated OpenAPI responses.
Separate deployment observation on 2026-10-07 UTC: after user-authorized
activation, source and running OpenAPI matched exactly; authenticated reads
returned 200 and anonymous inventory returned 401. No paid request or draft
publication accompanied that verification.

### Profile practice-coverage incremental contract

Source-derived from `db/learner.py`, shared technique evidence in `db/queries.py`,
`routers/learner.py` and profile/proxy callers, including current worktree changes.
Source revision `77eb6784a000a9cc6077526fa4accc7c4111afac`; screened source OpenAPI
has 190 paths / 97 schemas. Earlier inventory counts are historical.
`GET /v1/learner/practice-progress` requires the learner bearer token and returns
`{items: [{kind, slug, name, available, attempted, remaining}]}`. Kind is
`concept|technique`; counts are nonnegative integers, over distinct problems.
No request parameters; the full theme catalogue is returned for client search
and pagination. Authentication failure is 401; storage failure is not masked.
Next.js `GET /api/rest/learner/practice-progress` forwards the httpOnly student
token server-side, preserves upstream errors and returns 401 without a cookie.
No learner ID supplied by the browser, answer bodies, enrichment or mutations.

Availability matches the exact `/v1/problems?concept=slug` or `technique=slug`
filter (including the corpus paper/edition/competition joins). It does not use
the broader concept-descendant endpoint. Attempted counts all distinct recorded
learner attempts, including ungraded ones, over the entire history—not the
profile's last 50 rows. Remaining = available minus attempted; coverage is not
mastery, correctness, or the completion of temporary guided drafts.

- Latest guided-workspace incremental source revision:
  `1582f808a731e571e79b588d4c73e717eefc7956` plus related worktree changes.
  Inspected `guided_orientation.py`, `guided_visuals.py`, `pedagogy.py`, `routers/pedagogy.py`,
  web tutor proxy and orientation tests. Source-generated, screened OpenAPI
  is now **189 paths / 95 schemas**, including `solution_guidance.py` and
  its coaching/agent callers; earlier counts below are historical.
  No endpoint call, live schema check or paid inference accompanied generation.

### Guided-workspace orientation contract

| Route | Input/auth | Behavior/errors |
|---|---|---|
| `GET /v1/tutor/workspace/{problem_code}` | Public canonical code | Canonical statement/safe-figure read plus authored orientation and optional visual intent. No graph, enrichment/publication, provider, session or mastery write. Unknown 404; storage 503. Initial workspace is independent of full teaching-context latency. |
| `GET /v1/tutor/learning-context/{problem_code}` | Public canonical code | Existing teaching context plus `pedagogy_session` with journey, current action, response type, goal, choices, orientation counts, temporary status and provenance. Existing missing-metadata enrichment/publication remains possible. Unknown 404; enrichment 502; data unavailable 503. No newly added orientation model call. |
| `POST /v1/tutor/micro-check` | Public `MicroCheckRequest`; extras forbidden; code/response 1–200 chars; strict integer index 0–20 | Canonical statement/safe-diagram read, stateless authored checks for Q31 and AIME 1985 Q1. Correct response returns explanation and next prompt; wrong response stays at current index without key; `"hint"` gives a nudge without advancing. Invalid authored index/choice 422, unknown problem 404, storage 503. No solution read, enrichment, model, mastery or session write. |
| `POST /v1/tutor/guidance-plan` | Public explicit `GuidancePlanRequest`; code 1–200 characters with no whitespace; extras forbidden | Read up to six nonempty stored solutions, at most 12,000 characters each. Return safe rationale, 3–5 stages, one checkpoint, selected reference ID and source-status/counts. AIME authored source-gated route has no model call; other plans may use the existing model with a 45-second timeout/no retries. No references returns explicit `status=unavailable`; no raw solution/answer fields. Unknown 404, validation 422, provider/refusal/invalid plan/withheld answer 502, storage 503. No corpus/mastery write. |

Next.js `POST /api/tutor/micro-check` validates JSON and proxies only the
allowlisted endpoint; malformed JSON 400, unknown proxy path 404, upstream
errors preserve their status. The returned generic dictionary is not a typed
OpenAPI response schema; runtime behavior is covered by source/tests.
`pedagogy_session` is an orientation envelope, **not a durable server session**:
indices supplied by clients are not completion evidence. Browser work, journey
and coaching remain temporary; upload/approval uses the existing authenticated
attempt-media API. See [34](../34_GUIDED_PROBLEM_WORKSPACE.md).

Orientation responses now include `visual_intent` (or null): canonical code,
current visual goal, required element IDs, level bound, forbidden proof/scale
claims and ordered two-level circumcenter definitions. Q31 setup is gated by
the actual statement; unsupported/reordered definitions return no intent.
No model-generated coordinate or SVG blob is accepted by this contract.
The browser computes verified illustrative coordinates and validates every
frame before rendering; this is not a durable artifact or graded assessment.
Generic-dictionary response schemas still do not describe these fields in
OpenAPI; the runtime tests and requirement 34 define the detailed contract.
Tutor GET proxies combine caller cancellation with a 20-second upstream
deadline, returning explicit 504 timeout errors. Workspace uses a 12-second
browser deadline; background context uses 15 seconds and never blocks writing
or authored checks. Late context does not reset orientation progression.

Tutor GET proxies now add display-only `problem.display_statement` and
`format_warnings` via the same deterministic presentation preparation used by
the workspace. `statement_text` remains unchanged. These Next.js-only additions
are not FastAPI response fields or paid formatter actions.

`POST /v1/tutor/coach` privately loads the same stored-solution references before
choosing a next hint. Its public result adds `solution_evidence` with counts and
source kind/revision/verification status, never bodies. No-reference coaching is
explicitly statement-only/provisional. Selected plan IDs must belong to the
retrieved set. A literal numeric final-answer check is not general proof/spoiler
validation. Generic dictionary response schemas remain an OpenAPI limitation.
No new web POST allowlist for planning is needed: the ADK tool calls REST
directly on the learner's explicit discussion request.

- Incremental behavior refresh, source-derived 2026-10-07 UTC at HEAD `c79060ac0771175baa6e04b37bede840f8c30ee1` plus related worktree changes: the agent session contract now returns answer-key-free lesson progress for stage navigation/timing, and `POST /v1/attempt-media/submissions/{sid}/analyse` refuses unrelated or unverified problem context before critique. No FastAPI route or OpenAPI schema changed. The source-generated OpenAPI was compared in memory with [openapi.json](openapi.json): exact match, 3.1.0 / 186 paths / 93 schemas. No live database or graph was queried.
- Evidence mode: source-derived for route/API descriptions, plus separately labelled operator-reported deployment observations (not independently verified).
- Source revision: `3e915d015aa34268996724a3014c850f5892596e`, with uncommitted worktree changes included (refreshed 2026-10-06 for migrations 021/022).
- Files examined: `mathbank-rest/src/mathbank_rest/main.py`, every router registered there and its referenced DB/runtime/model modules, including `routers/attempt_media.py`, `routers/artifacts.py`, `attempt_media.py`, `attempt_media_models.py`, `media_processing.py`, `artifact_runtime.py`, `object_store.py`, `runtime_ai.py`, `security.py`, and `config.py`; `mathbank-agent/agents/mathbank_tutor/tools/attempt_media_tools.py`, `artifact_tools.py`, and registry wiring; plus `mathbank-web/lib/privateRuntimeProxy.mjs`, the catch-all proxies under `app/api/rest/{attempt-media,artifacts}`, attempt/artifact pages/components, `mathbank-live/server.mjs` and `mathbank-live/lib/attemptEvents.mjs`.
- OpenAPI snapshot: [openapi.json](openapi.json), generated from `app.openapi()` without starting a server. Snapshot validation observed OpenAPI `3.1.0`, **186 paths and 93 component schemas** on 2026-10-07 (UTC), at `c79060ac0771175baa6e04b37bede840f8c30ee1` including related worktree changes; credential-like content was screened before saving. Newly examined topic-practice/admin-evaluation routers, optional bearer authentication, private preview frame parameters and source-book provenance. This incremental refresh is not a new full-system schema audit.
- No endpoint handlers were invoked during source OpenAPI generation. Separately, the parent reports a restarted REST process exposing the attempt-media and artifact path sets; see the dated runtime observation below. This documentation did not independently query that service.

## Auth mechanisms

### Topic planning and relevance feedback (incremental source-derived contract)

Sources: `db/topic_pedagogy.py`, `db/queries.py`, `routers/pedagogy.py`,
`routers/pedagogy_admin.py`, agent `pedagogy_agent.py`, and web proxy allowlists.

| Route | Auth / input | Behavior / errors |
|---|---|---|
| `GET /v1/tutor/topic-plan?q=...` | Public; query 1-200 characters | Exact normalized canonical taxonomy match (articles and "of" ignored), unique match required. Returns teaching stages, first checkpoint and up to five example codes backed by published step annotations. No vector embedding/model call or solution text. Ambiguous/absent match returns `matched=false`, not arbitrary similarity. Data unavailable: 503. |
| `POST /v1/tutor/topic-practice` | Optional student bearer; supplied invalid bearer fails. `TopicPracticeRequest`: topic 1-200 chars, named profile (`topic-fit-v1`), limit 1-25 (10), target difficulty 1-5 or null, known skills <=50, exposed/excluded codes <=100; extra identity fields forbidden. | Exact canonical node, published/reviewed evidence, confidence >=0.8, pending/rejected exclusion and resolved negative gate precede multi-factor ranking. At most 100 candidates considered. Returns bounded ranked candidates/profile/factor scores/unknown signals, not full solutions. Signed-in attempt exposure/gap evidence is server-derived. Missing/ambiguous topic returns `matched=false`; validation 422, database 503. No embeddings/models/writes. |
| `POST /v1/tutor/feedback` | Student bearer; `FeedbackRequest {problem_code,topic,reason}`; identity only from JWT | 201 report with bounded server audit snapshot; duplicate `(student,problem,topic,reason)` returns existing report/status/audit without reopening or resnapshotting review. Unknown problem 404, invalid/blank/extra input 422, no bearer 401, storage unavailable 503. No canonical/graph/mastery mutation. |
| `GET /v1/admin/pedagogy/feedback` | Admin key; limit 1-100 (25), offset >=0 | Paginated reports, pending first; no learner identity in queue payload. Database unavailable 503. |
| `POST /v1/admin/pedagogy/feedback-review` | Admin key; `FeedbackDecision {feedback_id,status,note,retrieval_verdict,error_kind}` | Status RESOLVED or DISMISSED only; note 10-2000 characters. Verdict UNCLASSIFIED/IRRELEVANT/RELEVANT; issue UNCLASSIFIED/METADATA/RETRIEVAL/INSUFFICIENT_EVIDENCE. One pending-row update, otherwise 409; never approves/reclassifies/publishes annotations. |
| `GET /v1/admin/pedagogy/retrieval-examples` | Admin key; limit 1-500 (100) | Only RESOLVED classified labels: query/topic, canonical code, verdict, error kind, evidence note, review time/reference. Evaluation data, no automatic training; 401/422/503. |

Next.js adds authenticated same-origin `POST /api/rest/solve/pedagogy-feedback`.
Admin proxy supports `view=feedback`, `view=retrieval-examples` and `action=feedback-review`.
The root intent router distinguishes bare-topic learning, explicit practice,
review/quiz and lesson continuation. A real pedagogy AgentTool presents theory
before contest practice; Power of a Point has seven authored units with
revision-checked authored radio/numeric checkpoints, skip/jump/hint controls,
elapsed-time and stage status in restorable ADK session state.
Other exact topics disclose unavailable authored content. Unmatched explicit
practice requests return canonical-topic clarification, never vector fall-through.
Explicit practice
checks at most ten ranked candidates for full statement/required source diagrams,
then displays one. Relevance complaints after a known single recommendation
route report -> real retrieval-audit AgentTool -> lesson replan; canonical data
is never changed by the complaint. The activity feed exposes only intent/stage,
checkpoint counts, artifact availability, bounded audit status and report state,
not private reasoning, solutions, identity or complaint contents.
Student chat attachments reuse the existing authenticated submission/media
routes and require the latest tutor response to name a canonical problem.
Transcription/analysis remain explicit actions; analysis fails closed when
problem context is false, unverified, or every step is irrelevant. These are
behavior changes, not new HTTP routes.
Specialist delegation uses the configured paid model in real conversations;
these deterministic endpoint/unit/browser checks do not establish live AI quality.
Ambiguous/long requests and non-topic solve/explore intents may still rely on
existing root-model tools; the router is not a universal natural-language classifier.
For textbook automatic technique listings, published step support is required;
human-reviewed mappings and non-step corpora retain their intended access. Canonical
problem details exclude rejected technique assertions.
Both `/v1/techniques/{slug}/problems` and `/v1/problems?technique=...` include
published/approved step-only evidence when no problem-level assertion exists,
labelled with computed role `STEP_SUPPORTED`. Explicit pending/rejected mappings
are not resurrected. No annotation is written by this read-time union.

| Surface | Auth mechanism | Source |
|---|---|---|
| Public corpus/search/tutor scaffold routes | No auth dependency | `routers/v1.py`, `routers/tutor.py`, `routers/pedagogy.py` |
| Learner and step-runtime protected routes | HTTP bearer JWT via `HTTPBearer`; token subject is `student_id` | `security.get_current_student_id` |
| Learner register/login | No bearer required; returns access token | `routers/learner.py` |
| Admin routes and internal step outcome route | `X-Admin-Api-Key` header checked against configured admin key | `security.require_admin_api_key` |
| Live/fluid routes (`routers/live.py`) | `live_actor`: admin key → actor INSTRUCTOR `instructor:{X-Actor-Id}`, or student bearer → STUDENT `student:{uuid}`; `staff_actor` additionally requires INSTRUCTOR/ADMIN (403 otherwise). `/v1/tutor/sessions/*` with the admin key acts as AI_TUTOR. | `routers/live.py` (`live_actor`, `staff_actor`) |
| Widgets / format-math (`routers/fluid.py`) | `staff_or_student`: admin key or student bearer; registry is public; store/list/review are admin-key only; all `/v1/authoring/*` are admin-key only | `routers/fluid.py` |
| Attempt media (`routers/attempt_media.py`) | `staff_or_student`: student bearer JWT or `X-Admin-Api-Key`; every submission read is owner-scoped for students (non-owner is 404). Create/edit/approve require a student; override requires ADMIN role. | `attempt_media.py`, `routers/fluid.py` |
| Artifacts (`routers/artifacts.py`) | `staff_or_student` for request/read/validation/search; request reads are owner-scoped, non-admin bundle reads require PUBLISHED. Generation, publish and index explicitly require `X-Admin-Api-Key`. | `artifact_runtime.py`, `routers/fluid.py` |
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
| GET | `/v1/problems/by-code/{code}/source` | none | path canonical code | Original source metadata, or `kind=identified` with book/chapter/problem identity and `provenance_status=LOCATION_INCOMPLETE`; null only when neither identity nor document is known | Read-only Postgres lookup; invalid/missing problem 404. URLs with credentials/invalid schemes are omitted. Identified books do not receive guessed PDF paths/pages/highlights. |
| GET | `/v1/problems/by-code/{code}/source-pdf` | none | path canonical code | Cached original problem PDF (`application/pdf`, inline, `no-cache`) | Read-only; 404 if problem/source PDF is not cached. Resolved path is constrained under the ingestion PDF root. |
| GET | `/v1/problems/by-code/{code}/source-highlight` | none | canonical code; optional verified physical `page>=1` | Highlighted page image (`image/png`, no-store/nosniff) | 404 if no verified problem location/page, 422 invalid page. Derived copy, never replaces the source/question figure. |
| GET | `/v1/problems/by-code/{code}/source-marked-pdf` | none | canonical code | Annotated original full document (`application/pdf`, inline, no-store/nosniff) | 404 if no verified problem location. Highlights all verified regions in a copy; original document remains unchanged. |
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
| POST | `/v1/tutor/coach` | none | `CoachRequest` in `mathbank_rest.pedagogy` | coaching response + safe solution evidence | Ensures learning metadata; privately consults stored solution references; can trigger enrichment/model path; 502 for coaching/enrichment failures. |
| POST | `/v1/tutor/guidance-plan` | none | `GuidancePlanRequest` | safe roadmap/checkpoint or unavailable status | Bounded private reference SELECT; explicit planning may invoke model; 404/422/502/503; no canonical or mastery write. |
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

## Private attempt-media routes (migration 021)

All paths are under `/v1/attempt-media`. `S` is a student bearer JWT and `A` is the configured admin API key accepted by `staff_or_student`; resource ownership is checked in the database. The OpenAPI currently declares generic object responses for most handlers and only its usual 422 validation response; the implemented status/error details below come from router/runtime code and are not complete OpenAPI guarantees.

| Method and path | Auth | Request / response contract and effects |
|---|---|---|
| `POST /submissions` | S | `SubmissionIn {problem_ref}`; 201 snapshot after resolving canonical code or problem UUID. Non-student gets 403 `STUDENT_SUBMISSION_REQUIRED`; unknown problem 404. |
| `GET /submissions` | S/A | `limit` default 25, 1..100; `offset` default 0, >=0. Returns `{items, has_more}` newest first; students see their submissions, admins all. |
| `GET /submissions/{sid}` | S/A | Owner-scoped snapshot containing metadata, current evidence/steps, approvals, current assessments, events; admin additionally sees assessment history. Non-owner/missing submission 404. |
| `GET /submissions/{sid}/events` | S/A | `after_sequence` default 0, >=0; `{events}` in sequence order, up to 500 rows. Owner/admin only. |
| `POST /submissions/{sid}/assets` | S/A | Raw request bytes with supported media `Content-Type`; `expected_version` query >=1 and optional `filename` (≤200 chars). 201 `{media_asset_id, transcription_version}`. Streams are limited to 20 MiB by REST; type/signature, page count and duration are validated. Stale version 409; invalid media 413/415/422; storage unavailable 503. |
| `GET /submissions/{sid}/assets/{aid}/content` | S/A | Authenticated original media bytes; private/no-store and `nosniff`. Purged media 410; storage failure 503. |
| `GET /submissions/{sid}/assets/{aid}/pages/{page}` | S/A | Rasterized page PNG; page must exist on an IMAGE/PDF asset or 404 `PAGE_NOT_FOUND`. |
| `DELETE /submissions/{sid}/assets/{aid}` | S/A | Purges source object and direct derivatives, records `purged_at`; returns `{purged, approved_attempt_preserved}`. 409 during processing; 503 object-store failure. |
| `POST /submissions/{sid}/process` | S/A | `Versioned {expected_version}`. Explicit provider-backed transcription of active original assets; emits progress and saves a new candidate version. Errors include `UPLOAD_MEDIA_FIRST`, 409 version/processing conflicts, and 502 provider/processing failures with `manual_review_available`. |
| `GET /submissions/{sid}/transcription` | S/A | Returns the owner-scoped snapshot/current transcription. |
| `PUT /submissions/{sid}/transcription` | S | Full `Transcript` (`expected_version`, ordered steps, optional evidence regions); persists a new STUDENT candidate version. Admin receives 403 `STUDENT_EDIT_REQUIRED`. |
| `PATCH /submissions/{sid}/transcription/steps/{step_id}` | S/A | `StepPatch` extends `Versioned` with optional plain/LaTeX text; edits current candidate into a new version. Missing step 404. |
| `POST /submissions/{sid}/transcription/merge` | S/A | `Merge` extends `Versioned` with 2..100 adjacent unique `step_ids`; returns a new candidate version. Non-adjacent/unknown selection 422. |
| `POST /submissions/{sid}/transcription/split` | S/A | `Split` extends `Versioned` with `step_id` and 2..10 replacement `parts`; returns a new candidate version. Missing step 404. |
| `POST /submissions/{sid}/approve` | S/A | `Versioned`; student only. Creates an approved immutable candidate link and an unevaluated `learner.attempt` with `is_correct=null`. Empty candidate 422; stale version or in-progress transcription 409. |
| `GET /attempts/{aid}/steps` | S/A | Approved step list keyed by the learner attempt; owner/admin checked via approval. Missing attempt 404. |
| `GET /attempts/{aid}/steps/{step_id}/assessment` | S/A | Most recent assessment for the approved attempt/step; 404 if unavailable. |
| `GET /attempts/{aid}/steps/{step_id}/visual` | S/A | Alias of the assessment route; returns assessment/evidence explanation metadata, not a separate image renderer. |
| `POST /submissions/{sid}/analyse` | S/A | `Versioned`; requires current transcript approval, then explicitly aligns/critiques against published solution steps and reviewed dependencies. Provider failure 502 with `approved_attempt_preserved`; does not update mastery. |
| `POST /submissions/{sid}/override` | A | `Override` (`expected_version`, step, correctness, rationale, next action; alignment defaults to `UNMATCHED_BUT_PLAUSIBLE`); appends instructor assessment. Non-admin 403 `INSTRUCTOR_REQUIRED`; missing step 404. |

Spatial evidence must refer to a page and full normalized rectangle; temporal evidence must refer to an increasing timestamp interval. Steps carry one or more evidence IDs. Student edits use optimistic `expected_version`; the API preserves previous candidate versions, and approval links to the exact one reviewed. Nullable `learner.attempt.is_correct` is not counted as incorrect/mastery evidence.

`Transcript` accepts at most 100 contiguous, 1-based steps and 300 regions; each step has 1..30 unique evidence IDs, plain text ≤4,000 characters, LaTeX ≤8,000, and confidence 0..1. Region coordinates are normalized 0..1, page numbers 1..10, and media intervals are bounded to the 120-second media limit. Request models reject unknown fields. The object-store write limit is 25 MiB, but this REST upload route caps the incoming media at 20 MiB.

For video processing, the implementation uses `ffprobe` to detect an audio stream before extraction. It skips only audio extraction/speech transcription for silent video; keyframe extraction and exact FFmpeg `pts_time` evidence continue. Synthetic fixtures with and without audio were reported passing. This is implementation behavior, not a request/response schema change.

## Declarative artifact routes (migration 022)

All paths are under `/v1/artifacts`; bearer/admin-key access follows the artifact row visibility rules above. `ArtifactPlan`, `SearchBody`, `IndexBody`, and `GenerateBody` are strict Pydantic request models. Most successful JSON outputs are generic dictionaries; content routes return binary SVG/asset bytes. As with attempt-media, OpenAPI does not describe every runtime error.

| Method and path | Auth | Request / response contract and effects |
|---|---|---|
| `GET /embedding-profile` | S/A | Configured provider/model/dimensions as `{status: AVAILABLE, ...}` or explicit `{status: UNAVAILABLE, reason}`; does not request an embedding. |
| `POST /validate` | S/A | `ArtifactPlan`; deterministic `{valid, errors}` validation, no write or model call. |
| `POST /requests` | S/A | `ArtifactPlan`; 201 request row after validation and optional linked-problem check. |
| `POST /geometry-preview` | S/A | `GeometryPreview`: geometry-only `ArtifactPlan` plus optional ≤8 triples of named vertices in `incircle_triangles`. Computes exact Euclidean triangle incircles, applies shared geometry validation/rendering, returns validation/rule profile and a declarative `geometry-artifact` markdown block. Ephemeral: no database/object-store writes, publication, embeddings or paid provider calls. Invalid/missing/degenerate triangle references and invalid geometry return 422. |
| `POST /geometry-preview/content` | S/A | Same private validated preview input; optional `frame` ordinal 0-127 selects a validated reset-to-base overlay, absent returns base SVG. Out-of-range authored frame 404, invalid query 422. Returns `image/svg+xml` bytes with no-store/nosniff/sandbox headers. Browser uses an image blob URL, never injects SVG markup. Generated sketches are not source figures or proof. |
| `POST /preview` | S/A | Strict `ArtifactPlan`, all four subjects; shared deterministic validation/generation. Returns validation/rule profile and a declarative `artifact-preview` markdown block. Ephemeral: no storage, publication, indexing or provider calls. Invalid plan returns 422. |
| `POST /preview/content` | S/A | Same plan; optional `frame` ordinal 0-127 selects a reset-to-base overlay; absent returns base SVG. Missing authored ordinal 404, invalid query 422. Private validated SVG bytes with no-store/nosniff/sandbox headers; image-only rendering with separate KaTeX equation lines. No storage, publication or provider call. |
| `GET /requests/{request_id}` | S/A | Owner/admin request detail; missing or other-student request 404. |
| `POST /requests/{request_id}/generate` | A | `GenerateBody {publish=false}`; deterministic generation and private asset storage; admin-only. Optional publication is explicit. |
| `GET /bundles/{bundle_id}` | S/A | Bundle metadata; students see published bundles only, admins can see drafts. |
| `GET /bundles/{bundle_id}/assets` | S/A | Asset metadata with authenticated `content_path`; internal object keys are removed. |
| `GET /bundles/{bundle_id}/assets/{asset_id}/content` | S/A | Private asset bytes with integrity verification, no-store, `nosniff` and sandbox CSP. |
| `GET /bundles/{bundle_id}/frames` | S/A | Validated manifest with authenticated per-frame content paths. |
| `GET /bundles/{bundle_id}/frames/{ordinal}/content` | S/A | Rendered SVG; ordinal 0..127, revalidated from declarative source; private/no-store sandbox response. |
| `POST /bundles/{bundle_id}/validate` | S/A | Recomputes output and checks stored asset integrity/safety. Admin validation appends `validation_result`; student access is read-only. |
| `POST /bundles/{bundle_id}/publish` | A | Locks, validates and publishes/approves a bundle; validation failure is surfaced instead of publication. |
| `POST /bundles/{bundle_id}/index` | A | `IndexBody`; requires current search-text hash and configured model/dimensions; accepts a supplied nonzero vector or explicit `generate_embedding=true` for provider generation. Upserts the bundle's embedding row. |
| `POST /search` | S/A | `SearchBody`; lexical full-text retrieval with subject/tag/difficulty/asset filters, limit 1..100 and offset >=0. Student results are published bundles only. |
| `POST /search/semantic` | S/A | `SearchBody`; requires supplied `query_embedding` or explicit `generate_embedding=true`. Returns `UNAVAILABLE` when profile/index/vectors/provider are unavailable; no lexical fallback. |
| `POST /bundles/{bundle_id}/similar` | S/A | `SearchBody`; semantic neighbors using the bundle's current indexed vector, excluding itself; explicit `UNAVAILABLE` when the source is not indexed. |

The generation/validation renderer is deterministic and does not call a generative model. Embedding providers are called only through explicit indexing/query-generation options. Returned content uses authenticated REST paths, never public or presigned object URLs. `AWS_ENDPOINT_URL_S3` configures object storage independently of Neon Auth and the AI Gateway. Object-store and SQL writes are not one atomic transaction.

Model bounds/defaults: `ArtifactPlan` supports GEOMETRY, ALGEBRA, COMBINATORICS and NUMBER_THEORY; topic/title are required, canvas defaults to 800×600 (240..2000), with 1..128 elements, at most 64 overlays and 128 frames. Per-element/action and subject-specific mathematical checks are described by the strict source model and deterministic validator. `GenerateBody.publish` defaults false. `SearchBody.query` defaults empty (max 2,000), limit defaults 20 (1..100), offset defaults 0 (≤100,000), and optional subject/tag/difficulty/asset filters are exact. `IndexBody` and semantic `SearchBody` default to the requested model identifier `text-embedding-3-small` and 1,536 dimensions; vectors are 1..8,192 finite numeric values and must match the declared/configured dimensions. Index input requires a 64-character lowercase source hash and exactly one of a supplied nonzero vector or `generate_embedding=true`. These source-level defaults do not establish provider support or inference availability.

## OpenAPI and Swagger guidance

- FastAPI serves live `/docs`, `/redoc`, and `/openapi.json` when a server is running. Those reflect the running process, not necessarily this source revision.
- The committed [openapi.json](openapi.json) is a source-generated snapshot and must be regenerated when FastAPI source changes.
- OpenAPI captures Pydantic validation and declared response models where present. Many endpoints return plain `dict`/`list[dict]`, so response schemas are intentionally generic. Implementation-specific errors (for example 409 review conflict or 503 graph failure) are not exhaustively declared in OpenAPI and are documented in the table above.
- This refresh generated the snapshot from checked-in `main:app.openapi()` using the existing REST virtual environment without starting a server or invoking route handlers/providers. The source snapshot is OpenAPI 3.1.0 with 180 paths and 90 schemas: 18 attempt-media paths, 20 artifact paths and 142 other paths. This is not a live-service or deployment observation.

### Artifact specialist communication

Incremental source-viewer additions: `GET /v1/problems/by-code/{code}/source`
also returns `problem_number`, optional `location` (`page`, PDF-coordinate
rectangles, and `pages` for verified multi-page regions), `highlight_url` and `highlight_pdf_url`. Locations use an unambiguous
statement-text match or extraction metadata matching the current PDF hash;
unknown/ambiguous locations remain null. `GET .../source-highlight` returns a
bounded PNG preview (optional `page` selects only a verified problem/diagram page);
`GET .../source-marked-pdf` highlights all verified regions in a copy of the
full PDF. Both are public corpus reads, no-store, and return 404 when no cached
PDF/verified location exists. Neither modifies originals or writes media/data.
Next.js allowlists `solve/source-highlight/{code}` and
`solve/source-marked-pdf/{code}` alongside the existing source/PDF proxy.
The shared source pane opens the annotated PDF at `#page=N`, retaining a direct
untouched original link and page pills for diagrams continued on another page.
Known web sources do not become invented PDFs.

Separate Next.js surface: `POST /api/diagrams/asymptote` accepts `{source}` for
embedded problem Asymptote. Same-origin and REST-verified student authentication
are required. It returns private/no-store PNG, with 400 invalid JSON, 401/403
authentication/origin denial, 413 oversized request, 422 unsupported/failed
compilation, 429 busy renderer, 503 unavailable isolation/tooling and 504 timeout.
Rendering is isolated to a unique temporary directory on macOS; no application
credentials/network access or persistent media writes. Other operating systems
fail closed. This route is owned by Next.js and is not in FastAPI OpenAPI.
See [renderer setup/limits](../../mathbank-web/README.md#math-and-embedded-source-diagrams).

The existing ADK tutor uses ten real specialists built in
`mathbank-agent/agents/mathbank_tutor/artifact_agents.py`: Subject Planning,
Geometry, Algebra, Combinatorics, Number Theory, LaTeX, SVG, Overlay/Frame,
Annotation and Validation. The root exposes planner/subjects as ADK AgentTools;
subjects call refinement/validation agents as tools. They use the existing
OpenAI/LiteLLM model and private REST boundary. Auth is restored into child
invocations from async-context-local `temp:` state, not prompts or persisted
conversation events. Limits: 16 delegations and 24 specialist model calls per
invocation; 120-second delegate timeout. Anonymous calls fail before inference.
No remote A2A endpoint, agent card, discovery or cross-service authentication is
introduced. These are agent-tool contracts, not additional FastAPI HTTP routes.

### Reported runtime provider observation

On 2026-10-06 (UTC), final operator direction is to use official direct OpenAI endpoints and the shared project credential loader as `mathbank-agent` does for new agentic runtime stages; Gateway inference is avoided unless explicitly selected. This is explicit provider selection, not automatic fallback. The Gateway listed 49 models, but the first paid vision request failed with HTTP 403 over a billing-credit blocker. A subsequent direct OpenAI runtime request failed with HTTP 429 `insufficient_quota`; no successful runtime/Gateway inference or model-token response is reported, and the user chose available tests rather than adding credits. Runtime provider defaults to OpenAI. Runtime model configuration follows service `MATHBANK_AGENT_MODEL` (`openai/gpt-4o-mini` default); a root model value applies to a service only when synchronized. The explicit `MATHBANK_RUNTIME_AI_MODEL` override is supported and takes precedence. The current checked worktree also reads runtime-specific root/REST settings before agent model-file values, so the effective deployed override is not independently verified here. Runtime credentials and explicit `OPENAI_API_BASE` / `OPENAI_BASE_URL` use the shared project OpenAI loader/client path. Gateway credentials remain unchanged and Gateway remains a separate explicit option. Timestamped speech uses direct OpenAI `whisper-1`; artifact-agent embeddings use the shared direct OpenAI client with `text-embedding-3-small` at 1,536 dimensions by default. These settings describe selected configuration only, not inference success.

### Reported live integration and agent tools

On 2026-10-06 (UTC), the parent reports that the final REST and agent processes were responsive after restart and the live REST OpenAPI exposed 18 `/v1/attempt-media` and 16 `/v1/artifacts` paths (34 new paths total). These route-group counts match the source-generated OpenAPI snapshot, which has 174 total paths (140 other paths); source snapshot regeneration matched the checked-in JSON byte-for-byte. Three anonymous private REST/proxy GETs reportedly returned 401. These are operator-reported deployment observations; this documentation task did not independently query the running processes. The parent reports the agent registry now includes five new tools: `get_multimodal_attempt`, `get_multimodal_step_assessment`, `search_artifacts`, `get_artifact_bundle`, and `request_artifact`. The first four provide owner-scoped/read-only context or lexical artifact retrieval; `request_artifact` submits a structured request only. No agent tool approves student work, generates/publishes an artifact, or invokes a model/embedding provider.

Final selected checks reported by the parent include 184 focused REST offline passes, six media and one artifact rollback-only Neon tests passed, 15 agent tool tests passed, 25 focused UI unit tests, 17 mocked E2E cases, and a successful web production build. The artifact rollback-only test covered create, generate, publish, access and lexical/semantic search using a supplied fake 1,536-dimensional vector; it used a mocked object store and no AI/provider call or real object bytes. A sanitized constructed client reportedly confirmed provider `openai`, official `api.openai.com` endpoint, and `gpt-4o-mini`; this confirms configuration only, not inference. Live API path availability and these scoped test passes do not constitute full feature-pack acceptance.

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
| `/api/rest/attempt-media/[[...path]]` | Same-origin private proxy to `/v1/attempt-media/*`; gets student cookie/admin session server-side, applies a strict method/path/query allow-list, bounds body size, forwards only auth headers, and uses no-store/nosniff responses. The proxy allow-list is narrower than FastAPI: it does not include transcription merge/split, approved-attempt step/assessment/visual reads, or every REST transcription read. |
| `/api/rest/artifacts/[[...path]]` | Private proxy to `/v1/artifacts/*`; authenticates from student/admin session and method/path/query allow-list. Supports ephemeral geometry preview/content, embedding profile, request/bundle/assets/frames/frame-content/search/similar and admin generation/indexing. Plan/bundle validation and publication are not separately proxied. |
| `/learn/attempt-media`, `/admin/attempt-media` | Student-gated and admin-session-gated views of the attempt-media workspace. |
| `/artifacts` | Artifact library page; shows generation affordances only for a valid admin session. |

The attempt proxy separately caps uploads at 25 MiB and its MIME prefilter includes WebP and OGG, while `media_processing.media_info` currently accepts only PNG/JPEG/PDF, WAV/MP3/MP4/WebM audio and MP4/WebM video and the REST handler caps uploads at 20 MiB. Thus passing the web proxy's prefilter is not proof the REST processor accepts the upload; unsupported types/sizes can still return upstream 415/413.

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
| Socket.IO private attempt relay | `attempt:watch {submission_id, after_sequence?}` and `attempt:unwatch {submission_id}` use the socket actor's student/admin cookie identity, then call the owner-checked REST events route. Up to 10 watched submissions per socket; it emits each private event only to that socket (not classroom rooms), polls every second, and returns `attempt.progress.error {code: REPLAY_UNAVAILABLE}` when polling fails. |

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
