# How to build CRUD endpoints over the MathBank PostgreSQL schema

This guide is the "how we should build it" companion to the per-schema table
documentation in [schemas/](./schemas/). Every new or reworked endpoint that
reads or writes a Neon/PostgreSQL table should follow it. It generalises the
patterns that already work in this codebase (taxonomy admin, micro-course
lifecycle, Socratic drafts, corpus authoring) instead of inventing new ones,
and lists the places where today's code drifts from them.

Related: [README](./README.md) (schema map and ER diagrams) ·
[doc 45 – REST documentation and admin CRUD gaps](../requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md) ·
[doc 46 – quiz authoring API gaps](../requirements/46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md) ·
[REST_API.md](../requirements/reference/REST_API.md) · [REST_ENDPOINTS.md](../requirements/reference/REST_ENDPOINTS.md)

## 1. The boundary rule

```mermaid
flowchart LR
  web[mathbank-web / mathbank-live / mathbank-exam-web] -->|HTTP| rest
  agent[mathbank-agent / exam-agent / socratic-agent] -->|HTTP tools| rest
  socr[mathbank-socratic-admin SPA] -->|cookie + CSRF| sapp[socratic_app<br/>same codebase, separate deploy]
  subgraph rest[mathbank-rest FastAPI]
    r[routers/*.py<br/>validation, auth, HTTP mapping] --> s[service / db modules<br/>SQL + transactions]
  end
  sapp --> s
  s --> pg[(Neon PostgreSQL + pgvector)]
  s --> neo[(Neo4j AuraDB)]
  etl[mathbank-db/etl + mathbank-graph/etl<br/>batch only] --> pg
  manim[mathbank-manim-studio] -. exception: direct SQL on studio.* .-> pg
  ml[mathbank-ml-training / ml-inference] -. exception: direct reads .-> pg
```

- `mathbank-rest` is the **only runtime reader/writer** of the application
  schemas. UIs and agents never get a database connection string.
- Batch ETL (`mathbank-db/etl`, `mathbank-graph/etl`, `mathbank-rest/scripts`)
  may write directly, but only for bulk loads/backfills, never as a substitute
  for a missing endpoint.
- Known exceptions today: `mathbank-manim-studio` owns `studio.*` with its own
  SQL ([jobs.py](../../mathbank-manim-studio/src/mathbank_manim_studio/jobs.py)),
  and `mathbank-ml-training`/`mathbank-ml-inference` read Postgres directly.
  `mathbank-agent` uses Postgres only for Google ADK session storage (not an
  application schema). New services must not add to this list; see
  [README §6](./README.md#6-target-state--how-it-should-be).

## 2. Layering inside mathbank-rest

| Layer | Location | Responsibilities | Must not |
|---|---|---|---|
| Router | `routers/<area>.py` | Path/verb, Pydantic request/response models, auth dependency, map domain errors → HTTP status | Contain SQL (`text(...)`, `conn.execute`) |
| Service | `<area>_service.py` or `db/<area>.py` | Transactions (`engine.begin()`), SQL, invariants, audit rows, outbox rows | Read HTTP headers, raise `HTTPException` for business rules (raise domain errors instead; the router maps them) |
| Schema | `mathbank-db/sql/NNN_*.sql` | Tables, FKs, CHECKs, triggers for immutability | Be renumbered once applied |

**Drift to fix when touching these files:** inline SQL currently lives in
routers `attempt_media.py` (18 statements), `interaction_templates.py` (14),
`tutoring_routes.py` (10), `admin_corpus.py` (5), `fluid.py` (4),
`exam_integration.py` (3) and `step_runtime.py` (2). Move it into the matching
service module when you next change those routes.

## 3. URL families and authentication

| Audience | Prefix | Auth dependency | Example |
|---|---|---|---|
| Anonymous public catalogue | `/v1/<plural-kebab>` | none | `GET /v1/problems/by-code/{canonical_code}` |
| Learner-owned data | `/v1/learner/...` or resource path with ownership check | `get_current_student_id` ([security.py](../../mathbank-rest/src/mathbank_rest/security.py)) — Bearer JWT | `GET /v1/learner/me` |
| Content/ops admin | `/v1/admin/<domain>/<plural-kebab>` | `require_admin_api_key` (`X-Admin-Api-Key`, registered as an OpenAPI security scheme) | `PATCH /v1/admin/taxonomy/{kind}/{code}` |
| Socratic Studio staff | `/v1/admin/socratic/...` | `require_staff` cookie + CSRF + capability check ([routers/socratic.py](../../mathbank-rest/src/mathbank_rest/routers/socratic.py)) | `POST /v1/admin/socratic/workflows` |
| Service-to-service (agents) | dedicated integration prefix, e.g. `/v1/quiz-integration/...` | today: router-level `require_admin_api_key`; target: a per-service credential plus the learner identity passed explicitly and re-checked | exam agent → `POST /v1/quiz-integration/papers/{quiz_id}/finalize` |

Rules:

1. **Every route re-checks auth itself.** Hiding a route from OpenAPI or the UI is not a control.
2. **Learner reads are owner-scoped in SQL** (`WHERE student_id = :sid`), not filtered after fetch.
3. **GET must be side-effect free.** Today `GET /v1/tutor/learning-context/{problem_code}`
   defaults to `enrich=true` and, for an anonymous caller, can make paid OpenAI calls and
   insert/update `knowledge.enrichment_job`, `knowledge.problem_skill`,
   `knowledge.problem_pedagogy` and `knowledge.pedagogy_publication` rows
   ([routers/pedagogy.py](../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py),
   details in [knowledge-problems.md](./schemas/knowledge-problems.md)).
   New code must put such work behind an authenticated `POST` (or a queued job).
4. **Never return answer keys** (`correct_answer`, `correctness_policy`,
   `option_explanations`, solution text) to a learner before that learner has
   submitted the item. Use separate learner and admin response models rather than
   one model with optional fields.

## 4. Resource design per table type

Each table in [schemas/](./schemas/) is classified in its "CRUD coverage" matrix.
Pick the endpoint shape from its type:

| Table type | Examples | Endpoints | Not allowed |
|---|---|---|---|
| **Catalogue entity** (governed reference data) | `knowledge.concept`, `knowledge.theorem`, `visual.interaction_template` | list/search, get, create (admin), PATCH, `POST /{id}/deactivate` + `/reactivate` | Hard `DELETE` once referenced |
| **Revisioned authoring object** | `authoring.*` drafts, `pedagogy.micro_course_state`, `orchestration.socratic_workflow` | create draft, PATCH with `expected_revision`, `POST /{id}/validate`, `/submit`, `/approve`, `/reject`, `/publish` | Editing a published revision in place |
| **Release / snapshot** | `pedagogy.micro_course_release`, `pedagogy.solution_route_release` | create from a validated draft, get, list, `POST /{id}/retire` | PATCH/DELETE (immutable) |
| **Junction / link** | `*_concept`, `*_skill`, `*_technique` link tables | `GET /parents/{id}/<children>`, `PUT /parents/{id}/<children>/{child_id}` (idempotent attach), `DELETE` same path (detach), `PUT /parents/{id}/<children>` (replace set) | Separate surrogate-id CRUD for links |
| **Learner event / evidence (append-only)** | `quiz.response_event`, `learner.*_attempt`, `attempt_media.*` evidence, `live.event` | `POST` (append), owner-scoped `GET` list, admin `GET` | PATCH, DELETE (guarded by triggers in several schemas) |
| **Learner working state** | `quiz.response_draft`, learner profile | `PUT` (upsert) / PATCH, owner `GET`, `DELETE` to discard | Access by other learners |
| **Queue / job / run** | `pipeline.*`, `pedagogy.route_compile_task`, `studio.*_job`, `knowledge.enrichment_job` | `POST` to enqueue (returns 202 + job id), `GET /{id}` status, admin list, `POST /{id}/cancel` / `/retry` | Clients updating status/lease columns directly |
| **Derived / cache / embedding** | `search.embedding`, `*_similarity`, `quiz.question_pool` | Read-only lookups; admin `POST .../rebuild` that enqueues a job | Direct writes from clients |
| **Audit** | `audit.action_log` | Admin read with filters | Any write endpoint (written only via `record_audit_event`) |

## 5. Standard endpoint contracts

### List / search

```
GET /v1/admin/<domain>/<things>?q=&status=ACTIVE|INACTIVE|ALL&limit=50&offset=0&sort=-updated_at
200 {"items": [...], "total": 123, "limit": 50, "offset": 0}
```

- `limit` default 50, max 200; `offset` ≥ 0. Use keyset (`after=<cursor>`) for
  event tables expected to exceed ~100k rows.
- `q` matches natural keys (code/slug), names and aliases (`ILIKE` or `pg_trgm`).
- Filters for every enumerated status column, typed as `Literal[...]`.
- Return `total` from the same filter (`count(*) OVER ()`) so admin UIs can paginate.

### Get

`GET /.../<things>/{id}` → 200 or 404. Accept the natural key (code/slug) when the
table has one and the UI works with it; otherwise the UUID. Include child collections
only if they are small and always needed; otherwise expose them as sub-resources.

### Create

```
POST /.../<things>            (Idempotency-Key: <uuid> for learner/staff writes)
201 Location: /.../<things>/{id}   body: the created resource
409 natural-key conflict        422 validation
```

- Generate UUIDs server-side (`gen_random_uuid()` or `uuid5` for deterministic keys
  in backfills — see the batching note in [mathbank-db README](../../mathbank-db/README.md)).
- Validate every FK/enum in the service and translate `IntegrityError` into 409/422
  with the constraint name, never a 500.
- Write an `audit.action_log` row for every admin/staff mutation via
  `record_audit_event(...)` in [micro_course_service.py](../../mathbank-rest/src/mathbank_rest/micro_course_service.py).

### Update

```
PATCH /.../<things>/{id}
{"expected_revision": 7, "name": "...", "description": "..."}
200 updated resource   409 {"detail": "revision_conflict", "current_revision": 8}
```

- Partial update only of editable columns; status/lifecycle columns change only
  through action endpoints.
- Optimistic concurrency with `expected_revision` (pattern in
  [routers/admin_corpus.py](../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py))
  or `expected_hash` (Socratic) for every revisioned table.
- Bump `updated_at`/`revision` in the same statement (`... SET revision = revision + 1 ... WHERE id=:id AND revision=:expected RETURNING *`).

### Delete and lifecycle actions

- `DELETE` (204) only for rows that are drafts and unreferenced; the service must
  check references first and return 409 listing the blockers.
- Otherwise expose `POST /{id}/deactivate`, `/reactivate`, `/archive`, `/retire`
  with an optional `reason`, writing `deactivated_at/by` and an audit row
  (template: `POST /v1/admin/taxonomy/{kind}/{code}/deactivate`).

### Bulk and jobs

- Bulk import/backfill endpoints enqueue a `pipeline.job` (or domain job table)
  and return `202 {"job_id": ...}`; never run minutes-long SQL inside a request.
- Batch SQL as multi-row `INSERT ... VALUES (...),(...)` — per-row round trips to
  Neon are the bottleneck (see [mathbank-db README](../../mathbank-db/README.md)).

## 6. SQL and data rules

- SQLAlchemy `text()` with bound parameters only; JSON as `CAST(:payload AS jsonb)`
  (inlined JSON literals are mis-parsed as bind parameters).
- Enumerations: the database `CHECK` and the Pydantic `Literal` must list the same
  values. When adding a value, ship the migration and the model change together.
- One transaction per request (`with engine.begin() as conn:`); audit/outbox rows
  in the same transaction as the change they describe.
- Learner-private columns (raw responses, media keys, transcripts) never appear in
  admin list views by default — fetch on the detail endpoint only.
- Object-store payloads (`object_key`, `object_sha256`) are returned as short-lived
  signed URLs, never raw bucket keys, to learners.

## 7. Checklist for a new endpoint

1. Find the table in [schemas/](./schemas/) and its row in the CRUD matrix; confirm
   the endpoint is not already listed under "REST operations today".
2. Choose the table type (§4) and URL family (§3).
3. Add/extend the service function (SQL + transaction + audit); add the thin router
   function with typed request/response models and a one-line docstring.
4. Add a tag that starts with `admin-` for admin routes and register it in
   `OPENAPI_TAGS` in [main.py](../../mathbank-rest/src/mathbank_rest/main.py).
5. Tests: unit test the service with a rolled-back transaction
   (`ROUTE_DB_TESTS=1 make test`) and a router test for 401/403/404/409/422.
6. Regenerate the endpoint inventory and this documentation's mapping
   (see [README §8](./README.md#8-regenerating-this-documentation)) and update the
   table's "REST operations today" section.
