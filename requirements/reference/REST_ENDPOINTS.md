# Complete REST operation inventory

Source revision `375f3743357cef814c50e3c8752f7f4ce2d6ebe5`; generated from `app.openapi()` and registered APIRoute metadata.
**198 paths / 209 HTTP operations / 102 schemas.**
Endpoint handlers were not invoked. No model requests, service starts or database mutations were performed.

[Readable contracts and security caveats](REST_API.md) | [OpenAPI snapshot](openapi.json) | [Schema/access catalog](postgres/README.md) | [Step workflow/examples](../36_STEP_GENERATOR_AND_AUTHORING.md)

## Reading this inventory

- Each operation below is registered, not merely present in an unmounted router file.
- Authentication is derived from dependency functions; per-record ownership and staff-only actions remain handler rules.
- Parameters retain exact default/limit/enum/schema metadata. Request/response schemas resolve in the committed OpenAPI.
- Response status lists are **documented OpenAPI responses**, not an exhaustive guarantee of every implementation error.
- Untyped dict responses, custom HTTPException details, shared-key security, provider/storage failure and many 409 errors are not completely described by OpenAPI.
- Next.js proxy and ADK/live-socket endpoints are separate HTTP services; see the main reference.
- Proposed generator/editor/step-attachment routes are absent deliberately: they are not implemented.

### GET `/health`

**Purpose:** Health.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [main.py:health](../../mathbank-rest/src/mathbank_rest/main.py#L42).

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Health Health Get","type":"object"}` |

### GET `/health/neo4j`

**Purpose:** Health Neo4J.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [main.py:health_neo4j](../../mathbank-rest/src/mathbank_rest/main.py#L59).

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Health Neo4J Health Neo4J Get","type":"object"}` |

### GET `/health/postgres`

**Purpose:** Health Postgres.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [main.py:health_postgres](../../mathbank-rest/src/mathbank_rest/main.py#L51).

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Health Postgres Health Postgres Get","type":"object"}` |

### POST `/v1/activities/definitions`

**Purpose:** Activity Definition.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:activity_definition](../../mathbank-rest/src/mathbank_rest/routers/live.py#L261).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `{"additionalProperties":true,"title":"Body","type":"object"}`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Activity Definition V1 Activities Definitions Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/agent-sessions`

**Purpose:** Admin Agent Sessions.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [agent_sessions.py:admin_agent_sessions](../../mathbank-rest/src/mathbank_rest/routers/agent_sessions.py#L56).

Internal (X-Admin-Api-Key): linked conversations across students + count of unlinked (anonymous) sessions.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `student` | query | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"description":"e-mail substring or student uuid","title":"Student"}` |
| `limit` | query | False | `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Admin Agent Sessions V1 Admin Agent Sessions Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/agent-sessions/{agent_session_id}/transcript`

**Purpose:** Admin Agent Transcript.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [agent_sessions.py:admin_agent_transcript](../../mathbank-rest/src/mathbank_rest/routers/agent_sessions.py#L63).

Internal (X-Admin-Api-Key): full transcript incl. thinking, tool calls and truncated tool results.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `agent_session_id` | path | True | `{"title":"Agent Session Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Admin Agent Transcript V1 Admin Agent Sessions  Agent Session Id  Transcript Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/attempts/{attempt_id}/diagnoses`

**Purpose:** Admin List Diagnoses.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [step_runtime.py:admin_list_diagnoses](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L238).

Internal (X-Admin-Api-Key): full diagnoses with failure modes, confidences and evidence.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `attempt_id` | path | True | `{"format":"uuid","title":"Attempt Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Admin List Diagnoses V1 Admin Attempts  Attempt Id  Diagnoses Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/competitions`

**Purpose:** Create Competition.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin.py:create_competition](../../mathbank-rest/src/mathbank_rest/routers/admin.py#L57).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `CompetitionRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Create Competition V1 Admin Competitions Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/corpus/drafts`

**Purpose:** Drafts.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_corpus.py:drafts](../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L148).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `state` | query | False | `{"default":"DRAFT","enum":["DRAFT","APPROVED","REJECTED"],"title":"State","type":"string"}` |
| `limit` | query | False | `{"default":20,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/corpus/drafts`

**Purpose:** Create Draft.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_corpus.py:create_draft](../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L88).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `DraftRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### PUT `/v1/admin/corpus/drafts/{draft_id}`

**Purpose:** Update Draft.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_corpus.py:update_draft](../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L99).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `draft_id` | path | True | `{"format":"uuid","title":"Draft Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `DraftUpdate`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/corpus/drafts/{draft_id}/image`

**Purpose:** Draft Image.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_corpus.py:draft_image](../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L163).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `draft_id` | path | True | `{"format":"uuid","title":"Draft Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/corpus/drafts/{draft_id}/review`

**Purpose:** Review.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_corpus.py:review](../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L175).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `draft_id` | path | True | `{"format":"uuid","title":"Draft Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `mathbank_rest__routers__admin_corpus__ReviewRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/corpus/generate`

**Purpose:** Generate.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_corpus.py:generate](../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L137).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `GenerateRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/corpus/images`

**Purpose:** Upload.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_corpus.py:upload](../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L119).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `ImageRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/corpus/problems`

**Purpose:** Problems.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_corpus.py:problems](../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L71).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `competition` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Competition"}` |
| `year` | query | False | `{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Year"}` |
| `paper` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Paper"}` |
| `number` | query | False | `{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Number"}` |
| `q` | query | False | `{"default":"","title":"Q","type":"string"}` |
| `missing_only` | query | False | `{"default":true,"title":"Missing Only","type":"boolean"}` |
| `limit` | query | False | `{"default":20,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/corpus/problems/{code}`

**Purpose:** Detail.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_corpus.py:detail](../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L79).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `code` | path | True | `{"title":"Code","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/imports/actions`

**Purpose:** Actions.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:actions](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L188).

Append-only admin decision audit trail.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `target_type` | query | False | `{"anyOf":[{"enum":["IMPORT_CONFLICT","SOLUTION_STEP","STEP_DEPENDENCY","SOLUTION_DAG","LEARNING_ITEM","PROJECTION_REQUEST"],"type":"string"},{"type":"null"}],"title":"Target Type"}` |
| `limit` | query | False | `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Actions V1 Admin Imports Actions Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/imports/conflicts/{conflict_id}/decision`

**Purpose:** Decide Conflict.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:decide_conflict](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L80).

Record a conflict decision (audited). The decision is applied by re-import or a DAG edit.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `conflict_id` | path | True | `{"title":"Conflict Id","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `ConflictDecision`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Decide Conflict V1 Admin Imports Conflicts  Conflict Id  Decision Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### PUT `/v1/admin/imports/dependencies`

**Purpose:** Upsert Dependency.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:upsert_dependency](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L156).

Create an edge or change its type (e.g. mark an alternative branch). Rejects DEPENDS_ON cycles (409).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `DependencyEdit`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Upsert Dependency V1 Admin Imports Dependencies Put","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/imports/dependencies/reject`

**Purpose:** Reject Dependency.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:reject_dependency](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L171).

Mark an edge REJECTED: the runtime ignores it and the next graph projection prunes it.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `DependencyReject`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Reject Dependency V1 Admin Imports Dependencies Reject Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/imports/learning-items/{learning_item_id}/review`

**Purpose:** Review Learning Item.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:review_learning_item](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L120).

Human approve/reject (approval_method=human, never overwritten by re-import).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `learning_item_id` | path | True | `{"title":"Learning Item Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `ItemReview`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Review Learning Item V1 Admin Imports Learning Items  Learning Item Id  Review Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/imports/packages`

**Purpose:** Packages.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:packages](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L44).

Import dashboard: package, version, book, registered/postgres/reconciled status and open work.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `book` | query | False | `{"anyOf":[{"maxLength":64,"pattern":"^[A-Z0-9_]+$","type":"string"},{"type":"null"}],"title":"Book"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Packages V1 Admin Imports Packages Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/imports/packages/{package_id}`

**Purpose:** Package Detail.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:package_detail](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L50).

Per-entity source/valid/imported/rejected/conflict counts, staging summary, files and status history.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `package_id` | path | True | `{"title":"Package Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Package Detail V1 Admin Imports Packages  Package Id  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/imports/packages/{package_id}/conflicts`

**Purpose:** Conflicts.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:conflicts](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L66).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `package_id` | path | True | `{"title":"Package Id","type":"string"}` |
| `entity_type` | query | False | `{"anyOf":[{"maxLength":40,"type":"string"},{"type":"null"}],"title":"Entity Type"}` |
| `resolution_status` | query | False | `{"anyOf":[{"enum":["OPEN","AUTO_RESOLVED","RESOLVED","IGNORED"],"type":"string"},{"type":"null"}],"title":"Resolution Status"}` |
| `limit` | query | False | `{"default":50,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Conflicts V1 Admin Imports Packages  Package Id  Conflicts Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/imports/packages/{package_id}/issues`

**Purpose:** Issues.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:issues](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L57).

Validation issues: rejected staging rows and rows imported with warnings.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `package_id` | path | True | `{"title":"Package Id","type":"string"}` |
| `entity_type` | query | False | `{"anyOf":[{"maxLength":40,"type":"string"},{"type":"null"}],"title":"Entity Type"}` |
| `kind` | query | False | `{"default":"ALL","enum":["ALL","REJECTED","WARNINGS"],"title":"Kind","type":"string"}` |
| `limit` | query | False | `{"default":50,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Issues V1 Admin Imports Packages  Package Id  Issues Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/imports/problems/{code}/dag`

**Purpose:** Problem Dag.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:problem_dag](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L128).

Steps (skill, checkpoint), dependency edges, DAG review status and recent admin actions.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `code` | path | True | `{"title":"Code","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Problem Dag V1 Admin Imports Problems  Code  Dag Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/imports/problems/{code}/dag/review`

**Purpose:** Review Dag.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:review_dag](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L183).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `code` | path | True | `{"title":"Code","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `DagReview`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Review Dag V1 Admin Imports Problems  Code  Dag Review Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/imports/projection-requests`

**Purpose:** Projection Requests.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:projection_requests](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L94).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `status` | query | False | `{"anyOf":[{"enum":["PENDING","DONE","CANCELLED"],"type":"string"},{"type":"null"}],"title":"Status"}` |
| `limit` | query | False | `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Projection Requests V1 Admin Imports Projection Requests Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/imports/projection-requests`

**Purpose:** Request Projection.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:request_projection](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L107).

"Reproject missing": queue a projector run (coalesces with an open request for the same scope).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `ProjectionRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 202 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Request Projection V1 Admin Imports Projection Requests Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/imports/reconciliation`

**Purpose:** Reconciliation.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:reconciliation](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L88).

Graph expected/actual/missing/extra, embedding expected/completed, active model/profile and queue.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `book` | query | False | `{"default":"PRASOLOV_PGV1","maxLength":64,"pattern":"^[A-Z0-9_]+$","title":"Book","type":"string"}` |
| `graph` | query | False | `{"default":true,"description":"Also count Neo4j nodes/edges","title":"Graph","type":"boolean"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Reconciliation V1 Admin Imports Reconciliation Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### PATCH `/v1/admin/imports/steps/{step_id}`

**Purpose:** Edit Step.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_imports.py:edit_step](../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L140).

Adjust skill / mark checkpoint. Emits SOLUTION_STEP_CHANGED (graph + embedding re-projection).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `step_id` | path | True | `{"title":"Step Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `StepEdit`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Edit Step V1 Admin Imports Steps  Step Id  Patch","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/knowledge-gaps`

**Purpose:** Admin Gap Overview.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [step_runtime.py:admin_gap_overview](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L252).

Internal (X-Admin-Api-Key): knowledge gaps across students — status totals, the most common open
targets, and recent hypotheses with their diagnosis and latest recovery plan.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `status` | query | False | `{"anyOf":[{"enum":["UNRESOLVED","CONFIRMED","REJECTED","RESOLVED"],"type":"string"},{"type":"null"}],"title":"Status"}` |
| `student` | query | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"description":"e-mail substring or student uuid","title":"Student"}` |
| `limit` | query | False | `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Admin Gap Overview V1 Admin Knowledge Gaps Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/papers`

**Purpose:** List Papers.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin.py:list_papers](../../mathbank-rest/src/mathbank_rest/routers/admin.py#L98).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `competition` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Competition"}` |
| `status` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"description":"PENDING \| DOWNLOADED \| PARSED \| INGESTED \| FAILED","title":"Status"}` |
| `limit` | query | False | `{"default":100,"maximum":500,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Papers V1 Admin Papers Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/papers`

**Purpose:** Register Paper.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin.py:register_paper](../../mathbank-rest/src/mathbank_rest/routers/admin.py#L88).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `PaperRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Register Paper V1 Admin Papers Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/papers/batch`

**Purpose:** Register Papers Batch.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin.py:register_papers_batch](../../mathbank-rest/src/mathbank_rest/routers/admin.py#L93).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `PapersBatchRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Register Papers Batch V1 Admin Papers Batch Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/papers/{paper_external_code}/retry`

**Purpose:** Retry Paper.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin.py:retry_paper](../../mathbank-rest/src/mathbank_rest/routers/admin.py#L108).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `paper_external_code` | path | True | `{"title":"Paper External Code","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Retry Paper V1 Admin Papers  Paper External Code  Retry Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/pedagogy/approve-starter`

**Purpose:** Approve Starter.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [pedagogy_admin.py:approve_starter](../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L190).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `StarterReviewRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Approve Starter V1 Admin Pedagogy Approve Starter Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/pedagogy/bulk-review`

**Purpose:** Bulk Review.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [pedagogy_admin.py:bulk_review](../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L183).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `BulkReviewRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Bulk Review V1 Admin Pedagogy Bulk Review Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/pedagogy/edit`

**Purpose:** Edit.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [pedagogy_admin.py:edit](../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L195).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `EditRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Edit V1 Admin Pedagogy Edit Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/pedagogy/feedback`

**Purpose:** Feedback Queue.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [pedagogy_admin.py:feedback_queue](../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L61).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `limit` | query | False | `{"default":25,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Feedback Queue V1 Admin Pedagogy Feedback Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/pedagogy/feedback-review`

**Purpose:** Feedback Review.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [pedagogy_admin.py:feedback_review](../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L66).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `FeedbackDecision`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Feedback Review V1 Admin Pedagogy Feedback Review Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/pedagogy/history`

**Purpose:** History.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [pedagogy_admin.py:history](../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L173).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `EntityRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response History V1 Admin Pedagogy History Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/pedagogy/publish`

**Purpose:** Publish.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [pedagogy_admin.py:publish](../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L178).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `PublishRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Publish V1 Admin Pedagogy Publish Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/pedagogy/queue`

**Purpose:** Queue.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [pedagogy_admin.py:queue](../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L156).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `kind` | query | False | `{"default":"skill","enum":["skill","skill_concept","skill_relation","concept_relation","problem_skill","problem_pedagogy","problem_concept","problem_technique"],"title":"Kind","type":"string"}` |
| `status` | query | False | `{"default":"PENDING","enum":["ALL","PENDING","REVIEWED","REJECTED"],"title":"Status","type":"string"}` |
| `limit` | query | False | `{"default":25,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Queue V1 Admin Pedagogy Queue Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/pedagogy/reclassify`

**Purpose:** Reclassify.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [pedagogy_admin.py:reclassify](../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L200).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `ReclassifyRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Reclassify V1 Admin Pedagogy Reclassify Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/pedagogy/retrieval-examples`

**Purpose:** Retrieval Examples.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [pedagogy_admin.py:retrieval_examples](../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L78).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `limit` | query | False | `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Retrieval Examples V1 Admin Pedagogy Retrieval Examples Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/admin/pedagogy/review`

**Purpose:** Review.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [pedagogy_admin.py:review](../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L166).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `mathbank_rest__routers__pedagogy_admin__ReviewRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Review V1 Admin Pedagogy Review Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/pipeline/jobs`

**Purpose:** Pipeline Jobs Status.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin.py:pipeline_jobs_status](../../mathbank-rest/src/mathbank_rest/routers/admin.py#L124).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `competition` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Competition"}` |
| `paper` | query | False | `{"anyOf":[{"maxLength":100,"type":"string"},{"type":"null"}],"title":"Paper"}` |
| `limit` | query | False | `{"default":50,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Pipeline Jobs Status V1 Admin Pipeline Jobs Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/pipeline/runs`

**Purpose:** Pipeline Runs.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin.py:pipeline_runs](../../mathbank-rest/src/mathbank_rest/routers/admin.py#L116).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `limit` | query | False | `{"default":20,"maximum":200,"title":"Limit","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Pipeline Runs V1 Admin Pipeline Runs Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/recovery-plans`

**Purpose:** Admin Recovery Plans.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [step_runtime.py:admin_recovery_plans](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L346).

Internal (X-Admin-Api-Key): recovery plans with item outcome counts.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `student_id` | query | False | `{"anyOf":[{"format":"uuid","type":"string"},{"type":"null"}],"title":"Student Id"}` |
| `status` | query | False | `{"anyOf":[{"enum":["ACTIVE","SUSPENDED","COMPLETED","EXHAUSTED","ABORTED","SUPERSEDED"],"type":"string"},{"type":"null"}],"title":"Status"}` |
| `limit` | query | False | `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Admin Recovery Plans V1 Admin Recovery Plans Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/recovery-plans/{plan_id}`

**Purpose:** Admin Recovery Plan.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [step_runtime.py:admin_recovery_plan](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L354).

Internal (X-Admin-Api-Key): one plan with grader evidence for every item.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"format":"uuid","title":"Plan Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Admin Recovery Plan V1 Admin Recovery Plans  Plan Id  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/students/{student_id}/knowledge-gaps`

**Purpose:** Admin Student Gaps.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [step_runtime.py:admin_student_gaps](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L244).

Internal (X-Admin-Api-Key): a student's knowledge-gap hypotheses across attempts.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `student_id` | path | True | `{"format":"uuid","title":"Student Id","type":"string"}` |
| `status` | query | False | `{"anyOf":[{"enum":["UNRESOLVED","CONFIRMED","REJECTED","RESOLVED"],"type":"string"},{"type":"null"}],"title":"Status"}` |
| `limit` | query | False | `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Admin Student Gaps V1 Admin Students  Student Id  Knowledge Gaps Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/textbooks/coverage`

**Purpose:** Coverage.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_textbooks.py:coverage](../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L28).

Source CSV rows vs Postgres vs pgvector vs Neo4j per entity, packages, conflicts and per-chapter totals.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `book` | query | False | `{"default":"PRASOLOV_PGV1","maxLength":64,"pattern":"^[A-Z0-9_]+$","title":"Book","type":"string"}` |
| `graph` | query | False | `{"default":true,"description":"Also count Neo4j nodes/edges","title":"Graph","type":"boolean"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Coverage V1 Admin Textbooks Coverage Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/textbooks/diagrams/{source_diagram_id}/image`

**Purpose:** Diagram Image.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_textbooks.py:diagram_image](../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L83).

Any diagram file, including SOLUTION_HIDDEN ones students never see.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `source_diagram_id` | path | True | `{"maxLength":100,"pattern":"^[A-Za-z0-9_.-]+$","title":"Source Diagram Id","type":"string"}` |
| `book` | query | False | `{"default":"PRASOLOV_PGV1","maxLength":64,"pattern":"^[A-Z0-9_]+$","title":"Book","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | No schema/content documented |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/textbooks/learning-items`

**Purpose:** Learning Items.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_textbooks.py:learning_items](../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L56).

Paginated transformations (learning items) with per-type totals.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `book` | query | False | `{"default":"PRASOLOV_PGV1","maxLength":64,"pattern":"^[A-Z0-9_]+$","title":"Book","type":"string"}` |
| `transformation_type` | query | False | `{"anyOf":[{"maxLength":64,"type":"string"},{"type":"null"}],"title":"Transformation Type"}` |
| `chapter` | query | False | `{"anyOf":[{"maximum":99,"minimum":1,"type":"integer"},{"type":"null"}],"title":"Chapter"}` |
| `q` | query | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Q"}` |
| `limit` | query | False | `{"default":50,"maximum":200,"minimum":1,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Learning Items V1 Admin Textbooks Learning Items Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/textbooks/problems`

**Purpose:** Problems.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_textbooks.py:problems](../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L34).

Paginated problems with taxonomy, counts and embedding status.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `book` | query | False | `{"default":"PRASOLOV_PGV1","maxLength":64,"pattern":"^[A-Z0-9_]+$","title":"Book","type":"string"}` |
| `chapter` | query | False | `{"anyOf":[{"maximum":99,"minimum":1,"type":"integer"},{"type":"null"}],"title":"Chapter"}` |
| `q` | query | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Q"}` |
| `node` | query | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Node"}` |
| `has_diagram` | query | False | `{"anyOf":[{"type":"boolean"},{"type":"null"}],"title":"Has Diagram"}` |
| `has_solution` | query | False | `{"anyOf":[{"type":"boolean"},{"type":"null"}],"title":"Has Solution"}` |
| `limit` | query | False | `{"default":50,"maximum":200,"minimum":1,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Problems V1 Admin Textbooks Problems Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/textbooks/problems/{code}`

**Purpose:** Problem.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_textbooks.py:problem](../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L44).

Everything about one problem: source, solution, parts/steps/dependencies, learning items (with answers),
taxonomy, diagrams (including solution-hidden ones) and per-store status.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `code` | path | True | `{"title":"Code","type":"string"}` |
| `graph` | query | False | `{"default":true,"title":"Graph","type":"boolean"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Problem V1 Admin Textbooks Problems  Code  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/textbooks/taxonomy`

**Purpose:** Taxonomy.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_textbooks.py:taxonomy](../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L65).

Taxonomy nodes with usage counts (problems, steps, edges).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `book` | query | False | `{"default":"PRASOLOV_PGV1","maxLength":64,"pattern":"^[A-Z0-9_]+$","title":"Book","type":"string"}` |
| `node_type` | query | False | `{"anyOf":[{"enum":["DOMAIN","CONCEPT","SUBCONCEPT","SKILL","TECHNIQUE"],"type":"string"},{"type":"null"}],"title":"Node Type"}` |
| `q` | query | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Q"}` |
| `limit` | query | False | `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Taxonomy V1 Admin Textbooks Taxonomy Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/admin/textbooks/taxonomy/{node_id}`

**Purpose:** Taxonomy Node.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [admin_textbooks.py:taxonomy_node](../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L72).

A taxonomy node with parent, children, edges and up to 50 problems tagged with it.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `node_id` | path | True | `{"title":"Node Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Taxonomy Node V1 Admin Textbooks Taxonomy  Node Id  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/analytics/weak-concepts`

**Purpose:** Get Weak Concepts.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [v1.py:get_weak_concepts](../../mathbank-rest/src/mathbank_rest/routers/v1.py#L123).

Cohort-level (no PII — concept-level aggregates only), lowest average
mastery first. Signals what to improve at the platform level: genuinely
hard material, a thin bank of practice problems, or a retrieval gap —
not any individual student's data.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `min_students` | query | False | `{"default":1,"minimum":1,"title":"Min Students","type":"integer"}` |
| `limit` | query | False | `{"default":20,"maximum":100,"title":"Limit","type":"integer"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Weak Concepts V1 Analytics Weak Concepts Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/artifacts/bundles/{bundle_id}`

**Purpose:** Get Bundle.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:get_bundle](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L198).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `bundle_id` | path | True | `{"format":"uuid","title":"Bundle Id","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Get Bundle V1 Artifacts Bundles  Bundle Id  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/artifacts/bundles/{bundle_id}/assets`

**Purpose:** Assets.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:assets](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L203).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `bundle_id` | path | True | `{"format":"uuid","title":"Bundle Id","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Assets V1 Artifacts Bundles  Bundle Id  Assets Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/artifacts/bundles/{bundle_id}/assets/{asset_id}/content`

**Purpose:** Asset Content.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:asset_content](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L213).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `bundle_id` | path | True | `{"format":"uuid","title":"Bundle Id","type":"string"}` |
| `asset_id` | path | True | `{"format":"uuid","title":"Asset Id","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/artifacts/bundles/{bundle_id}/frames`

**Purpose:** Frames.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:frames](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L228).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `bundle_id` | path | True | `{"format":"uuid","title":"Bundle Id","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Frames V1 Artifacts Bundles  Bundle Id  Frames Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/artifacts/bundles/{bundle_id}/frames/{ordinal}/content`

**Purpose:** Frame Content.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:frame_content](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L233).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `bundle_id` | path | True | `{"format":"uuid","title":"Bundle Id","type":"string"}` |
| `ordinal` | path | True | `{"maximum":127,"minimum":0,"title":"Ordinal","type":"integer"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/bundles/{bundle_id}/index`

**Purpose:** Index.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [artifacts.py:index](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L264).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `bundle_id` | path | True | `{"format":"uuid","title":"Bundle Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `IndexBody`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Index V1 Artifacts Bundles  Bundle Id  Index Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/bundles/{bundle_id}/publish`

**Purpose:** Publish.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [artifacts.py:publish](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L259).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `bundle_id` | path | True | `{"format":"uuid","title":"Bundle Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Publish V1 Artifacts Bundles  Bundle Id  Publish Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/bundles/{bundle_id}/similar`

**Purpose:** Similar.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:similar](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L279).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `bundle_id` | path | True | `{"format":"uuid","title":"Bundle Id","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `SearchBody`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Similar V1 Artifacts Bundles  Bundle Id  Similar Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/bundles/{bundle_id}/validate`

**Purpose:** Validate Bundle.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:validate_bundle](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L254).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `bundle_id` | path | True | `{"format":"uuid","title":"Bundle Id","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Validate Bundle V1 Artifacts Bundles  Bundle Id  Validate Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/artifacts/embedding-profile`

**Purpose:** Embedding Profile.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:embedding_profile](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L143).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Embedding Profile V1 Artifacts Embedding Profile Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/geometry-preview`

**Purpose:** Geometry Preview.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:geometry_preview](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L114).

Private, ephemeral drawing; never publishes, stores, or calls a paid provider.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `GeometryPreview`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Geometry Preview V1 Artifacts Geometry Preview Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/geometry-preview/content`

**Purpose:** Geometry Preview Content.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:geometry_preview_content](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L127).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `frame` | query | False | `{"anyOf":[{"maximum":127,"minimum":0,"type":"integer"},{"type":"null"}],"title":"Frame"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `GeometryPreview`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/preview`

**Purpose:** Preview.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:preview](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L36).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `ArtifactPlan`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Preview V1 Artifacts Preview Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/preview/content`

**Purpose:** Preview Content.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:preview_content](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L53).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `frame` | query | False | `{"anyOf":[{"maximum":127,"minimum":0,"type":"integer"},{"type":"null"}],"title":"Frame"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `ArtifactPlan`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/requests`

**Purpose:** Request Artifact.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:request_artifact](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L173).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `ArtifactPlan`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Request Artifact V1 Artifacts Requests Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/artifacts/requests/{request_id}`

**Purpose:** Get Request.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:get_request](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L178).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `request_id` | path | True | `{"format":"uuid","title":"Request Id","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Get Request V1 Artifacts Requests  Request Id  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/requests/{request_id}/generate`

**Purpose:** Generate.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [artifacts.py:generate](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L183).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `request_id` | path | True | `{"format":"uuid","title":"Request Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `mathbank_rest__artifact_runtime__GenerateBody`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Generate V1 Artifacts Requests  Request Id  Generate Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/search`

**Purpose:** Search.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:search](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L269).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `SearchBody`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Search V1 Artifacts Search Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/search/semantic`

**Purpose:** Semantic Search.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:semantic_search](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L274).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `SearchBody`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Semantic Search V1 Artifacts Search Semantic Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/artifacts/validate`

**Purpose:** Validate.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [artifacts.py:validate](../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L249).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `ArtifactPlan`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Validate V1 Artifacts Validate Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempt-media/attempts/{aid}/steps`

**Purpose:** Approved Steps.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:approved_steps](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L496).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `aid` | path | True | `{"format":"uuid","title":"Aid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempt-media/attempts/{aid}/steps/{step_id}/assessment`

**Purpose:** Approved Assessment.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:approved_assessment](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L514).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `aid` | path | True | `{"format":"uuid","title":"Aid","type":"string"}` |
| `step_id` | path | True | `{"format":"uuid","title":"Step Id","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempt-media/attempts/{aid}/steps/{step_id}/visual`

**Purpose:** Approved Assessment.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:approved_assessment](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L514).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `aid` | path | True | `{"format":"uuid","title":"Aid","type":"string"}` |
| `step_id` | path | True | `{"format":"uuid","title":"Step Id","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempt-media/submissions`

**Purpose:** Listing.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:listing](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L66).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `limit` | query | False | `{"default":25,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempt-media/submissions`

**Purpose:** Create.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:create](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L40).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `SubmissionIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempt-media/submissions/{sid}`

**Purpose:** Get.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:get](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L92).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempt-media/submissions/{sid}/analyse`

**Purpose:** Analyse.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:analyse](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L541).

Explicit paid alignment then critique; uncertainty does not change mastery.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `Versioned`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempt-media/submissions/{sid}/approve`

**Purpose:** Approve.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:approve](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L411).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `Versioned`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempt-media/submissions/{sid}/assets`

**Purpose:** Upload.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:upload](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L145).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `expected_version` | query | True | `{"minimum":1,"title":"Expected Version","type":"integer"}` |
| `filename` | query | False | `{"default":"upload","maxLength":200,"title":"Filename","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### DELETE `/v1/attempt-media/submissions/{sid}/assets/{aid}`

**Purpose:** Purge.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:purge](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L617).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `aid` | path | True | `{"format":"uuid","title":"Aid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempt-media/submissions/{sid}/assets/{aid}/content`

**Purpose:** Content.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:content](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L210).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `aid` | path | True | `{"format":"uuid","title":"Aid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempt-media/submissions/{sid}/assets/{aid}/pages/{page}`

**Purpose:** Pdf Page.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:pdf_page](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L224).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `aid` | path | True | `{"format":"uuid","title":"Aid","type":"string"}` |
| `page` | path | True | `{"title":"Page","type":"integer"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempt-media/submissions/{sid}/events`

**Purpose:** Events.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:events](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L97).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `after_sequence` | query | False | `{"default":0,"minimum":0,"title":"After Sequence","type":"integer"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempt-media/submissions/{sid}/override`

**Purpose:** Override.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:override](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L595).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `Override`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempt-media/submissions/{sid}/process`

**Purpose:** Process.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:process](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L267).

Explicit paid transcription request. Errors preserve uploads for manual review.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `Versioned`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempt-media/submissions/{sid}/transcription`

**Purpose:** Transcription.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:transcription](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L381).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### PUT `/v1/attempt-media/submissions/{sid}/transcription`

**Purpose:** Replace.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:replace](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L386).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `Transcript`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempt-media/submissions/{sid}/transcription/merge`

**Purpose:** Merge.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:merge](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L420).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `Merge`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempt-media/submissions/{sid}/transcription/split`

**Purpose:** Split.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:split](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L458).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `Split`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### PATCH `/v1/attempt-media/submissions/{sid}/transcription/steps/{step_id}`

**Purpose:** Patch.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [attempt_media.py:patch](../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L398).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"format":"uuid","title":"Sid","type":"string"}` |
| `step_id` | path | True | `{"format":"uuid","title":"Step Id","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `StepPatch`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempts/{attempt_id}`

**Purpose:** Get Runtime.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:get_runtime](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L102).

Current step metadata, your own responses and progress counts — never canonical step text.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `attempt_id` | path | True | `{"format":"uuid","title":"Attempt Id","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Get Runtime V1 Attempts  Attempt Id  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempts/{attempt_id}/diagnoses`

**Purpose:** List Diagnoses.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:list_diagnoses](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L232).

Your diagnoses for this attempt, newest first (student view: no failure modes or raw scores).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `attempt_id` | path | True | `{"format":"uuid","title":"Attempt Id","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Diagnoses V1 Attempts  Attempt Id  Diagnoses Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempts/{attempt_id}/recovery-plans`

**Purpose:** List Recovery Plans.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:list_recovery_plans](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L288).

Your detours for this attempt, newest first.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `attempt_id` | path | True | `{"format":"uuid","title":"Attempt Id","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Recovery Plans V1 Attempts  Attempt Id  Recovery Plans Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempts/{attempt_id}/recovery-plans`

**Purpose:** Create Recovery Plan.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:create_recovery_plan](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L276).

Start a detour from the current step: worked example → recognise → use once → use in context →
transfer → return. Persisted before the first item is shown; the step becomes DETOURED and the
runtime enters RECOVERY. If a detour is already running it is returned (``resumed``).
409 NO_RECOVERY_MATERIAL when no approved practice exists for the target skill.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `attempt_id` | path | True | `{"format":"uuid","title":"Attempt Id","type":"string"}` |
| `Idempotency-Key` | header | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}` |

**Request body:** required=True; application/json: `RecoveryCreateRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Create Recovery Plan V1 Attempts  Attempt Id  Recovery Plans Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempts/{attempt_id}/runtime`

**Purpose:** Get Runtime.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:get_runtime](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L102).

Current step metadata, your own responses and progress counts — never canonical step text.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `attempt_id` | path | True | `{"format":"uuid","title":"Attempt Id","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Get Runtime V1 Attempts  Attempt Id  Runtime Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempts/{attempt_id}/steps/{step_id}/diagnose`

**Purpose:** Diagnose Step.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:diagnose_step](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L204).

Rank what may be blocking you on a presented step (local skill first, then the skills of the steps
it builds on). Deterministic and free; identical evidence returns the existing diagnosis
(``reused``). Every hypothesis is persisted; this does not change mode or ``state_version``.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `attempt_id` | path | True | `{"format":"uuid","title":"Attempt Id","type":"string"}` |
| `step_id` | path | True | `{"title":"Step Id","type":"string"}` |

**Request body:** required=False; application/json: `{"anyOf":[{"$ref":"#/components/schemas/DiagnoseRequest"},{"type":"null"}],"title":"Body"}`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Diagnose Step V1 Attempts  Attempt Id  Steps  Step Id  Diagnose Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempts/{attempt_id}/steps/{step_id}/hint`

**Purpose:** Request Hint.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:request_hint](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L160).

Escalate help one level (1–5) and return its text: 1 directional, 2 concept reminder,
3 strategic, 4 near-explicit, 5 the reference step itself. Any help → later success is WITH_HELP.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `attempt_id` | path | True | `{"format":"uuid","title":"Attempt Id","type":"string"}` |
| `step_id` | path | True | `{"title":"Step Id","type":"string"}` |
| `Idempotency-Key` | header | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}` |

**Request body:** required=True; application/json: `VersionedRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Request Hint V1 Attempts  Attempt Id  Steps  Step Id  Hint Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/attempts/{attempt_id}/steps/{step_id}/hints`

**Purpose:** List Hints.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:list_hints](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L178).

Hints already revealed to this student for a step (levels 1..help_level_used), for refresh/restore.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `attempt_id` | path | True | `{"format":"uuid","title":"Attempt Id","type":"string"}` |
| `step_id` | path | True | `{"title":"Step Id","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response List Hints V1 Attempts  Attempt Id  Steps  Step Id  Hints Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempts/{attempt_id}/steps/{step_id}/outcome`

**Purpose:** Record Step Outcome.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [step_runtime.py:record_step_outcome](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L190).

Internal (X-Admin-Api-Key): apply an evaluated result and advance to the next eligible step.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `attempt_id` | path | True | `{"format":"uuid","title":"Attempt Id","type":"string"}` |
| `step_id` | path | True | `{"title":"Step Id","type":"string"}` |
| `Idempotency-Key` | header | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `StepOutcomeRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Record Step Outcome V1 Attempts  Attempt Id  Steps  Step Id  Outcome Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempts/{attempt_id}/steps/{step_id}/responses`

**Purpose:** Submit Step Response.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:submit_step_response](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L116).

Save the response, then grade it (unless ``evaluate=false``) and advance on success.

``evaluation_status``: EVALUATED, PENDING (not requested / superseded by a newer action) or
UNAVAILABLE (model error; the response is kept and the student can resubmit).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `attempt_id` | path | True | `{"format":"uuid","title":"Attempt Id","type":"string"}` |
| `step_id` | path | True | `{"title":"Step Id","type":"string"}` |
| `Idempotency-Key` | header | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}` |

**Request body:** required=True; application/json: `StepResponseRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Submit Step Response V1 Attempts  Attempt Id  Steps  Step Id  Responses Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/attempts/{attempt_id}/submit`

**Purpose:** Submit Attempt.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:submit_attempt](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L360).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `attempt_id` | path | True | `{"format":"uuid","title":"Attempt Id","type":"string"}` |
| `Idempotency-Key` | header | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}` |

**Request body:** required=True; application/json: `VersionedRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Submit Attempt V1 Attempts  Attempt Id  Submit Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/authoring/chat/sessions`

**Purpose:** Chat Create.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:chat_create](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L268).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `ChatIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Chat Create V1 Authoring Chat Sessions Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/authoring/chat/sessions/{chat_id}`

**Purpose:** Chat Get.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:chat_get](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L273).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `chat_id` | path | True | `{"title":"Chat Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Chat Get V1 Authoring Chat Sessions  Chat Id  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/authoring/chat/sessions/{chat_id}/messages`

**Purpose:** Chat Message.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:chat_message](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L278).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `chat_id` | path | True | `{"title":"Chat Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `MessageIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Chat Message V1 Authoring Chat Sessions  Chat Id  Messages Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/authoring/chat/sessions/{chat_id}/proposed-patches`

**Purpose:** Chat Patches.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:chat_patches](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L283).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `chat_id` | path | True | `{"title":"Chat Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Chat Patches V1 Authoring Chat Sessions  Chat Id  Proposed Patches Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/authoring/chat/sessions/{chat_id}/proposed-patches/{patch_id}/apply`

**Purpose:** Chat Patch Decide.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:chat_patch_decide](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L288).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `chat_id` | path | True | `{"title":"Chat Id","type":"string"}` |
| `patch_id` | path | True | `{"title":"Patch Id","type":"string"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `PatchDecision`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Chat Patch Decide V1 Authoring Chat Sessions  Chat Id  Proposed Patches  Patch Id  Apply Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/authoring/presentation-plans`

**Purpose:** Plans.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:plans](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L223).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `limit` | query | False | `{"default":100,"maximum":500,"title":"Limit","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Plans V1 Authoring Presentation Plans Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/authoring/presentation-plans`

**Purpose:** Create Plan.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:create_plan](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L228).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `PlanIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Create Plan V1 Authoring Presentation Plans Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/authoring/presentation-plans/{plan_id}`

**Purpose:** Plan.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:plan](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L233).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"title":"Plan Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Plan V1 Authoring Presentation Plans  Plan Id  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/authoring/presentation-plans/{plan_id}/approve`

**Purpose:** Plan Approve.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:plan_approve](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L253).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"title":"Plan Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Plan Approve V1 Authoring Presentation Plans  Plan Id  Approve Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/authoring/presentation-plans/{plan_id}/new-version`

**Purpose:** Plan New Version.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:plan_new_version](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L263).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"title":"Plan Id","type":"string"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Plan New Version V1 Authoring Presentation Plans  Plan Id  New Version Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/authoring/presentation-plans/{plan_id}/publish`

**Purpose:** Plan Publish.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:plan_publish](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L258).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"title":"Plan Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Plan Publish V1 Authoring Presentation Plans  Plan Id  Publish Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### PATCH `/v1/authoring/presentation-plans/{plan_id}/timing`

**Purpose:** Plan Timing.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:plan_timing](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L243).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"title":"Plan Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `TimingIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Plan Timing V1 Authoring Presentation Plans  Plan Id  Timing Patch","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### PUT `/v1/authoring/presentation-plans/{plan_id}/topics`

**Purpose:** Plan Topics.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:plan_topics](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L238).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"title":"Plan Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `TopicsIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Plan Topics V1 Authoring Presentation Plans  Plan Id  Topics Put","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/authoring/presentation-plans/{plan_id}/validate`

**Purpose:** Plan Validate.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:plan_validate](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L248).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"title":"Plan Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Plan Validate V1 Authoring Presentation Plans  Plan Id  Validate Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/competitions`

**Purpose:** Get Competitions.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [v1.py:get_competitions](../../mathbank-rest/src/mathbank_rest/routers/v1.py#L51).

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Competitions V1 Competitions Get","type":"array"}` |

### GET `/v1/concepts`

**Purpose:** Get Concepts.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [v1.py:get_concepts](../../mathbank-rest/src/mathbank_rest/routers/v1.py#L85).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `domain` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Domain"}` |
| `limit` | query | False | `{"default":50,"maximum":200,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Concepts V1 Concepts Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/concepts/{slug}/neighbors`

**Purpose:** Get Concept Neighbors.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [v1.py:get_concept_neighbors](../../mathbank-rest/src/mathbank_rest/routers/v1.py#L101).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `slug` | path | True | `{"title":"Slug","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Concept Neighbors V1 Concepts  Slug  Neighbors Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/concepts/{slug}/problems`

**Purpose:** Get Concept Problems.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [v1.py:get_concept_problems](../../mathbank-rest/src/mathbank_rest/routers/v1.py#L94).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `slug` | path | True | `{"title":"Slug","type":"string"}` |
| `limit` | query | False | `{"default":25,"maximum":200,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Concept Problems V1 Concepts  Slug  Problems Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/corpus/coverage`

**Purpose:** Get Corpus Coverage.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [v1.py:get_corpus_coverage](../../mathbank-rest/src/mathbank_rest/routers/v1.py#L118).

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Corpus Coverage V1 Corpus Coverage Get","type":"array"}` |

### POST `/v1/instructor/live/{sid}/commands`

**Purpose:** Instructor Nl.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:instructor_nl](../../mathbank-rest/src/mathbank_rest/routers/live.py#L340).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `NLIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Instructor Nl V1 Instructor Live  Sid  Commands Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/instructor/live/{sid}/handoff`

**Purpose:** Handoff.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:handoff](../../mathbank-rest/src/mathbank_rest/routers/live.py#L360).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `scope` | query | False | `{"default":"SESSION","enum":["SESSION","STUDENT","GROUP"],"title":"Scope","type":"string"}` |
| `scope_id` | query | False | `{"default":"*","title":"Scope Id","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Handoff V1 Instructor Live  Sid  Handoff Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/instructor/live/{sid}/overrides`

**Purpose:** Override.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:override](../../mathbank-rest/src/mathbank_rest/routers/live.py#L334).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `OverrideIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Override V1 Instructor Live  Sid  Overrides Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/instructor/live/{sid}/recommendations`

**Purpose:** Recommendations.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:recommendations](../../mathbank-rest/src/mathbank_rest/routers/live.py#L346).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `status` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Status"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Recommendations V1 Instructor Live  Sid  Recommendations Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/instructor/live/{sid}/recommendations/{rid}`

**Purpose:** Decide.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:decide](../../mathbank-rest/src/mathbank_rest/routers/live.py#L351).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `rid` | path | True | `{"title":"Rid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `DecisionIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Decide V1 Instructor Live  Sid  Recommendations  Rid  Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/learner/agent-sessions`

**Purpose:** My Agent Sessions.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [agent_sessions.py:my_agent_sessions](../../mathbank-rest/src/mathbank_rest/routers/agent_sessions.py#L43).

The student's conversations, newest first, with message counts and a preview.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `limit` | query | False | `{"default":50,"maximum":200,"minimum":1,"title":"Limit","type":"integer"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response My Agent Sessions V1 Learner Agent Sessions Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/learner/agent-sessions`

**Purpose:** Link Agent Session.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [agent_sessions.py:link_agent_session](../../mathbank-rest/src/mathbank_rest/routers/agent_sessions.py#L36).

Link an ADK session (created under this student's id) to the student. Idempotent.

**Request body:** required=True; application/json: `AgentSessionLinkRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Link Agent Session V1 Learner Agent Sessions Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/learner/agent-sessions/{agent_session_id}/transcript`

**Purpose:** My Agent Transcript.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [agent_sessions.py:my_agent_transcript](../../mathbank-rest/src/mathbank_rest/routers/agent_sessions.py#L50).

Rebuilt conversation (student text + tutor replies only).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `agent_session_id` | path | True | `{"title":"Agent Session Id","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response My Agent Transcript V1 Learner Agent Sessions  Agent Session Id  Transcript Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/learner/attempts`

**Purpose:** Get Attempts.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [learner.py:get_attempts](../../mathbank-rest/src/mathbank_rest/routers/learner.py#L137).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `limit` | query | False | `{"default":50,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"title":"Offset","type":"integer"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Attempts V1 Learner Attempts Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/learner/attempts`

**Purpose:** Submit Attempt.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [learner.py:submit_attempt](../../mathbank-rest/src/mathbank_rest/routers/learner.py#L114).

**Request body:** required=True; application/json: `AttemptRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Submit Attempt V1 Learner Attempts Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/learner/login`

**Purpose:** Login.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [learner.py:login](../../mathbank-rest/src/mathbank_rest/routers/learner.py#L90).

**Request body:** required=True; application/json: `LoginRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `AuthResponse` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/learner/mastery`

**Purpose:** Get Mastery Summary.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [learner.py:get_mastery_summary](../../mathbank-rest/src/mathbank_rest/routers/learner.py#L144).

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Get Mastery Summary V1 Learner Mastery Get","type":"object"}` |

### GET `/v1/learner/mastery/improvement-plan`

**Purpose:** Get Improvement Plan.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [learner.py:get_improvement_plan](../../mathbank-rest/src/mathbank_rest/routers/learner.py#L149).

Actionable 'what to improve next' view: weakest concepts/techniques
(not yet 'solid'), each with a few recommended practice problems.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `max_focus_areas` | query | False | `{"default":5,"title":"Max Focus Areas","type":"integer"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Get Improvement Plan V1 Learner Mastery Improvement Plan Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/learner/me`

**Purpose:** Get Me.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [learner.py:get_me](../../mathbank-rest/src/mathbank_rest/routers/learner.py#L106).

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Get Me V1 Learner Me Get","type":"object"}` |

### GET `/v1/learner/practice-progress`

**Purpose:** Get Practice Progress.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [learner.py:get_practice_progress](../../mathbank-rest/src/mathbank_rest/routers/learner.py#L62).

Distinct available/attempted/unattempted problems per exact corpus theme.

All recorded learner attempts count, including ungraded work. Coverage is
not correctness or mastery. Technique eligibility matches the corpus filter.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `PracticeProgressResponse` |

### POST `/v1/learner/register`

**Purpose:** Register.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [learner.py:register](../../mathbank-rest/src/mathbank_rest/routers/learner.py#L74).

**Request body:** required=True; application/json: `RegisterRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `AuthResponse` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/live/sessions`

**Purpose:** List Sessions.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:list_sessions](../../mathbank-rest/src/mathbank_rest/routers/live.py#L202).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `limit` | query | False | `{"default":50,"maximum":200,"title":"Limit","type":"integer"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response List Sessions V1 Live Sessions Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/live/sessions`

**Purpose:** Create Session.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:create_session](../../mathbank-rest/src/mathbank_rest/routers/live.py#L197).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `SessionIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Create Session V1 Live Sessions Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/live/sessions/join`

**Purpose:** Join.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:join](../../mathbank-rest/src/mathbank_rest/routers/live.py#L207).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `JoinIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Join V1 Live Sessions Join Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/live/sessions/{sid}/activities`

**Purpose:** Open Activity.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:open_activity](../../mathbank-rest/src/mathbank_rest/routers/live.py#L268).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `ActivityIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Open Activity V1 Live Sessions  Sid  Activities Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/live/sessions/{sid}/activities/{aid}/aggregate`

**Purpose:** Activity Aggregate.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:activity_aggregate](../../mathbank-rest/src/mathbank_rest/routers/live.py#L280).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `aid` | path | True | `{"title":"Aid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Activity Aggregate V1 Live Sessions  Sid  Activities  Aid  Aggregate Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/live/sessions/{sid}/activities/{aid}/close`

**Purpose:** Close Activity.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:close_activity](../../mathbank-rest/src/mathbank_rest/routers/live.py#L290).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `aid` | path | True | `{"title":"Aid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `VersionedIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Close Activity V1 Live Sessions  Sid  Activities  Aid  Close Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/live/sessions/{sid}/activities/{aid}/responses`

**Purpose:** Respond.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:respond](../../mathbank-rest/src/mathbank_rest/routers/live.py#L274).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `aid` | path | True | `{"title":"Aid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `ResponseIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Respond V1 Live Sessions  Sid  Activities  Aid  Responses Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/live/sessions/{sid}/activities/{aid}/reveal`

**Purpose:** Reveal Activity.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:reveal_activity](../../mathbank-rest/src/mathbank_rest/routers/live.py#L296).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `aid` | path | True | `{"title":"Aid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `VersionedIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Reveal Activity V1 Live Sessions  Sid  Activities  Aid  Reveal Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/live/sessions/{sid}/commands`

**Purpose:** Command.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:command](../../mathbank-rest/src/mathbank_rest/routers/live.py#L232).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `CommandIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Command V1 Live Sessions  Sid  Commands Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/live/sessions/{sid}/events`

**Purpose:** Events.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:events](../../mathbank-rest/src/mathbank_rest/routers/live.py#L222).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `after_sequence` | query | False | `{"default":0,"minimum":0,"title":"After Sequence","type":"integer"}` |
| `limit` | query | False | `{"default":500,"maximum":1000,"minimum":1,"title":"Limit","type":"integer"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Events V1 Live Sessions  Sid  Events Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/live/sessions/{sid}/pause`

**Purpose:** Pause.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:pause](../../mathbank-rest/src/mathbank_rest/routers/live.py#L244).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `VersionedIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Pause V1 Live Sessions  Sid  Pause Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/live/sessions/{sid}/resume`

**Purpose:** Resume.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:resume](../../mathbank-rest/src/mathbank_rest/routers/live.py#L249).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `VersionedIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Resume V1 Live Sessions  Sid  Resume Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/live/sessions/{sid}/state`

**Purpose:** State.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:state](../../mathbank-rest/src/mathbank_rest/routers/live.py#L214).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response State V1 Live Sessions  Sid  State Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/live/sessions/{sid}/time`

**Purpose:** Time State.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:time_state](../../mathbank-rest/src/mathbank_rest/routers/live.py#L254).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Time State V1 Live Sessions  Sid  Time Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/live/sessions/{sid}/transition`

**Purpose:** Transition.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:transition](../../mathbank-rest/src/mathbank_rest/routers/live.py#L238).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `TransitionIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Transition V1 Live Sessions  Sid  Transition Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/live/sessions/{sid}/widgets`

**Purpose:** Show Widget.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:show_widget](../../mathbank-rest/src/mathbank_rest/routers/live.py#L304).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `WidgetIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Show Widget V1 Live Sessions  Sid  Widgets Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### DELETE `/v1/live/sessions/{sid}/widgets/{wid}`

**Purpose:** Hide Widget.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:hide_widget](../../mathbank-rest/src/mathbank_rest/routers/live.py#L325).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `wid` | path | True | `{"title":"Wid","type":"string"}` |
| `expected_session_version` | query | False | `{"anyOf":[{"minimum":1,"type":"integer"},{"type":"null"}],"title":"Expected Session Version"}` |
| `client_command_id` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Client Command Id"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Hide Widget V1 Live Sessions  Sid  Widgets  Wid  Delete","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### PATCH `/v1/live/sessions/{sid}/widgets/{wid}/state`

**Purpose:** Widget State.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:widget_state](../../mathbank-rest/src/mathbank_rest/routers/live.py#L319).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `wid` | path | True | `{"title":"Wid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

**Request body:** required=True; application/json: `WidgetStateIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Widget State V1 Live Sessions  Sid  Widgets  Wid  State Patch","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/problem-images/{image_id}`

**Purpose:** Get Problem Image.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [step_runtime.py:get_problem_image](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L443).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `image_id` | path | True | `{"format":"uuid","title":"Image Id","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | No schema/content documented |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/problems`

**Purpose:** Get Problems.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [v1.py:get_problems](../../mathbank-rest/src/mathbank_rest/routers/v1.py#L56).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `competition` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Competition"}` |
| `year_min` | query | False | `{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Year Min"}` |
| `year_max` | query | False | `{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Year Max"}` |
| `concept` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Concept"}` |
| `technique` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Technique"}` |
| `limit` | query | False | `{"default":25,"maximum":200,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Problems V1 Problems Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/problems/by-code/{canonical_code}`

**Purpose:** Get Problem.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [v1.py:get_problem](../../mathbank-rest/src/mathbank_rest/routers/v1.py#L77).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `canonical_code` | path | True | `{"title":"Canonical Code","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Get Problem V1 Problems By Code  Canonical Code  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/problems/by-code/{code}/diagrams`

**Purpose:** List Problem Diagrams.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [step_runtime.py:list_problem_diagrams](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L383).

Problem-statement diagrams (never solution diagrams) for the workspace.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `code` | path | True | `{"title":"Code","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Problem Diagrams V1 Problems By Code  Code  Diagrams Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/problems/by-code/{code}/source`

**Purpose:** Get Problem Source.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [step_runtime.py:get_problem_source](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L390).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `code` | path | True | `{"title":"Code","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"anyOf":[{"additionalProperties":true,"type":"object"},{"type":"null"}],"title":"Response Get Problem Source V1 Problems By Code  Code  Source Get"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/problems/by-code/{code}/source-highlight`

**Purpose:** Get Problem Source Highlight.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [step_runtime.py:get_problem_source_highlight](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L410).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `code` | path | True | `{"title":"Code","type":"string"}` |
| `page` | query | False | `{"anyOf":[{"minimum":1,"type":"integer"},{"type":"null"}],"title":"Page"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/problems/by-code/{code}/source-marked-pdf`

**Purpose:** Get Problem Source Marked Pdf.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [step_runtime.py:get_problem_source_marked_pdf](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L428).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `code` | path | True | `{"title":"Code","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/problems/by-code/{code}/source-pdf`

**Purpose:** Get Problem Source Pdf.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [step_runtime.py:get_problem_source_pdf](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L399).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `code` | path | True | `{"title":"Code","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | No schema/content documented |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/realtime/sessions/{sid}`

**Purpose:** Realtime Info.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [live.py:realtime_info](../../mathbank-rest/src/mathbank_rest/routers/live.py#L398).

Connection hints for the Socket.IO gateway (``mathbank-live``).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Realtime Info V1 Realtime Sessions  Sid  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/recovery-plans/{plan_id}`

**Purpose:** Get Recovery Plan.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:get_recovery_plan](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L294).

Plan, stage progress and mastery-policy progress. Item content only for the current item and
finished items; answers only after an item is finished.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"format":"uuid","title":"Plan Id","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Get Recovery Plan V1 Recovery Plans  Plan Id  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/recovery-plans/{plan_id}/abort`

**Purpose:** Abort Recovery.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:abort_recovery](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L338).

Leave the detour early: open plans end ABORTED, remaining items SKIPPED, back to the origin step.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"format":"uuid","title":"Plan Id","type":"string"}` |
| `Idempotency-Key` | header | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}` |

**Request body:** required=True; application/json: `VersionedRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Abort Recovery V1 Recovery Plans  Plan Id  Abort Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/recovery-plans/{plan_id}/items/{item_id}/responses`

**Purpose:** Answer Recovery Item.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:answer_recovery_item](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L306).

Answer the current item. MCQs are graded deterministically, subproblems by the step evaluator
(outside the attempt lock), worked examples by acknowledging. The plan then adapts: advance,
confirmation item, retry, alternate item or a prerequisite branch.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"format":"uuid","title":"Plan Id","type":"string"}` |
| `item_id` | path | True | `{"format":"uuid","title":"Item Id","type":"string"}` |
| `Idempotency-Key` | header | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}` |

**Request body:** required=True; application/json: `RecoveryItemResponse`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Answer Recovery Item V1 Recovery Plans  Plan Id  Items  Item Id  Responses Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/recovery-plans/{plan_id}/next`

**Purpose:** Next Recovery Item.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:next_recovery_item](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L301).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"format":"uuid","title":"Plan Id","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Next Recovery Item V1 Recovery Plans  Plan Id  Next Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/recovery-plans/{plan_id}/resume`

**Purpose:** Resume From Recovery.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:resume_from_recovery](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L331).

Return to the exact step the detour started from (the plan must be COMPLETED or EXHAUSTED).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `plan_id` | path | True | `{"format":"uuid","title":"Plan Id","type":"string"}` |
| `Idempotency-Key` | header | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}` |

**Request body:** required=True; application/json: `VersionedRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Resume From Recovery V1 Recovery Plans  Plan Id  Resume Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/search/concepts`

**Purpose:** Search Concepts.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [v1.py:search_concepts](../../mathbank-rest/src/mathbank_rest/routers/v1.py#L134).

Concept-level hybrid search over the embedded taxonomy (TAXONOMY_NODE vectors).

Maps a topic to taxonomy nodes with their corpus slug, problem count and example problem codes.
If the query embedding is unavailable, falls back to lexical ranking and reports a warning.

**Request body:** required=True; application/json: `ConceptSearchRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Search Concepts V1 Search Concepts Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/search/problems`

**Purpose:** Search Problems.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [v1.py:search_problems](../../mathbank-rest/src/mathbank_rest/routers/v1.py#L171).

**Request body:** required=True; application/json: `ProblemSearchRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Search Problems V1 Search Problems Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/solution-steps/{step_id}/practice`

**Purpose:** Practice For Step.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:practice_for_step](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L373).

Similar steps from *other* problems exercising the same skill (hybrid vector + lexical, no step text).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `step_id` | path | True | `{"title":"Step Id","type":"string"}` |
| `limit` | query | False | `{"default":5,"maximum":20,"minimum":1,"title":"Limit","type":"integer"}` |
| `same_skill` | query | False | `{"default":true,"title":"Same Skill","type":"boolean"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Practice For Step V1 Solution Steps  Step Id  Practice Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/students/{student_id}/events`

**Purpose:** List Events.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:list_events](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L366).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `student_id` | path | True | `{"format":"uuid","title":"Student Id","type":"string"}` |
| `attempt_id` | query | False | `{"anyOf":[{"format":"uuid","type":"string"},{"type":"null"}],"title":"Attempt Id"}` |
| `limit` | query | False | `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Events V1 Students  Student Id  Events Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/students/{student_id}/problems/{problem_ref}/attempts`

**Purpose:** Start Attempt.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [step_runtime.py:start_attempt](../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L88).

Start the step-by-step session for a problem (uuid or canonical code), or resume the open one.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `student_id` | path | True | `{"format":"uuid","title":"Student Id","type":"string"}` |
| `problem_ref` | path | True | `{"title":"Problem Ref","type":"string"}` |
| `Idempotency-Key` | header | False | `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Start Attempt V1 Students  Student Id  Problems  Problem Ref  Attempts Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/techniques`

**Purpose:** Get Techniques.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [v1.py:get_techniques](../../mathbank-rest/src/mathbank_rest/routers/v1.py#L106).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `limit` | query | False | `{"default":50,"maximum":200,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Techniques V1 Techniques Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/techniques/{slug}/problems`

**Purpose:** Get Technique Problems.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [v1.py:get_technique_problems](../../mathbank-rest/src/mathbank_rest/routers/v1.py#L111).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `slug` | path | True | `{"title":"Slug","type":"string"}` |
| `limit` | query | False | `{"default":25,"maximum":200,"title":"Limit","type":"integer"}` |
| `offset` | query | False | `{"default":0,"minimum":0,"title":"Offset","type":"integer"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Technique Problems V1 Techniques  Slug  Problems Get","type":"array"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/tutor/check-subproblem`

**Purpose:** Check Subproblem.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [tutor.py:check_subproblem](../../mathbank-rest/src/mathbank_rest/routers/tutor.py#L35).

**Request body:** required=True; application/json: `CheckSubproblemRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Check Subproblem V1 Tutor Check Subproblem Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/tutor/coach`

**Purpose:** Coach.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [pedagogy.py:coach](../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L156).

**Request body:** required=True; application/json: `CoachRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Coach V1 Tutor Coach Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/tutor/decompose`

**Purpose:** Decompose.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [tutor.py:decompose](../../mathbank-rest/src/mathbank_rest/routers/tutor.py#L27).

**Request body:** required=True; application/json: `DecomposeRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Decompose V1 Tutor Decompose Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/tutor/feedback`

**Purpose:** Feedback.
**Auth:** Learner bearer JWT; handler checks ownership.
**Handler:** [pedagogy.py:feedback](../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L73).

**Request body:** required=True; application/json: `FeedbackRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Feedback V1 Tutor Feedback Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/tutor/format-math`

**Purpose:** Format Math.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [fluid.py:format_math](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L169).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `FormatBody`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Format Math V1 Tutor Format Math Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/tutor/guidance-plan`

**Purpose:** Guidance Plan.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [pedagogy.py:guidance_plan](../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L131).

Explicit planning action; raw solutions remain inside the REST service.

**Request body:** required=True; application/json: `GuidancePlanRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Guidance Plan V1 Tutor Guidance Plan Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/tutor/learning-context/{problem_code}`

**Purpose:** Learning Context.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [pedagogy.py:learning_context](../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L104).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `problem_code` | path | True | `{"title":"Problem Code","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Learning Context V1 Tutor Learning Context  Problem Code  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/tutor/micro-check`

**Purpose:** Micro Check.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [pedagogy.py:micro_check](../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L137).

**Request body:** required=True; application/json: `MicroCheckRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Micro Check V1 Tutor Micro Check Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/tutor/practice/{problem_code}`

**Purpose:** Practice.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [pedagogy.py:practice](../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L151).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `problem_code` | path | True | `{"title":"Problem Code","type":"string"}` |
| `limit` | query | False | `{"default":5,"maximum":20,"minimum":1,"title":"Limit","type":"integer"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Practice V1 Tutor Practice  Problem Code  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/tutor/prerequisites/{skill_slug}`

**Purpose:** Prerequisites.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [pedagogy.py:prerequisites](../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L146).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `skill_slug` | path | True | `{"title":"Skill Slug","type":"string"}` |
| `max_depth` | query | False | `{"default":4,"maximum":8,"minimum":1,"title":"Max Depth","type":"integer"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Prerequisites V1 Tutor Prerequisites  Skill Slug  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/tutor/sessions/{sid}/actions`

**Purpose:** Tutor Action.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [live.py:tutor_action](../../mathbank-rest/src/mathbank_rest/routers/live.py#L373).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `TutorActionIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Tutor Action V1 Tutor Sessions  Sid  Actions Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/tutor/sessions/{sid}/context`

**Purpose:** Tutor Context.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [live.py:tutor_context](../../mathbank-rest/src/mathbank_rest/routers/live.py#L368).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `participant_id` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Participant Id"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Tutor Context V1 Tutor Sessions  Sid  Context Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/tutor/sessions/{sid}/messages`

**Purpose:** Tutor Message.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [live.py:tutor_message](../../mathbank-rest/src/mathbank_rest/routers/live.py#L379).

Generate a live reply outside the transaction, then commit it only if the version is still current.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `sid` | path | True | `{"title":"Sid","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `TutorMessageIn`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Tutor Message V1 Tutor Sessions  Sid  Messages Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/tutor/topic-plan`

**Purpose:** Topic Plan.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [pedagogy.py:topic_plan](../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L41).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `q` | query | True | `{"maxLength":200,"minLength":1,"title":"Q","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Topic Plan V1 Tutor Topic Plan Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/tutor/topic-practice`

**Purpose:** Topic Practice.
**Auth:** Anonymous allowed; invalid supplied JWT rejected.
**Handler:** [pedagogy.py:topic_practice](../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L63).

**Request body:** required=True; application/json: `TopicPracticeRequest`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Topic Practice V1 Tutor Topic Practice Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/tutor/workspace/{problem_code}`

**Purpose:** Workspace.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [pedagogy.py:workspace](../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L112).

Canonical question and authored orientation without graph/enrichment.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `problem_code` | path | True | `{"title":"Problem Code","type":"string"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Workspace V1 Tutor Workspace  Problem Code  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/widgets/generate`

**Purpose:** Widget Generate.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [fluid.py:widget_generate](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L86).

Deterministic FAST-path composition (never calls a model); optionally stores the result.

Students (e.g. the tutor agent acting with the learner's token) may compose for display only;
persisting a spec (``store``) stays staff-only.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `mathbank_rest__routers__fluid__GenerateBody`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Widget Generate V1 Widgets Generate Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/widgets/registry`

**Purpose:** Widget Registry.
**Auth:** No auth dependency; see handler for additional gates.
**Handler:** [fluid.py:widget_registry](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L74).

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Widget Registry V1 Widgets Registry Get","type":"object"}` |

### GET `/v1/widgets/specs`

**Purpose:** Widget Specs.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:widget_specs](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L117).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `lifecycle` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Lifecycle"}` |
| `persistence` | query | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Persistence"}` |
| `limit` | query | False | `{"default":50,"maximum":200,"title":"Limit","type":"integer"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Widget Specs V1 Widgets Specs Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/widgets/specs`

**Purpose:** Widget Store.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:widget_store](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L105).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `x-actor-id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `StoreBody`.

| Documented status | Description | Response schema |
|---|---|---|
| 201 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Widget Store V1 Widgets Specs Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### GET `/v1/widgets/specs/{spec_id}`

**Purpose:** Widget Spec.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [fluid.py:widget_spec](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L129).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `spec_id` | path | True | `{"title":"Spec Id","type":"string"}` |
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Widget Spec V1 Widgets Specs  Spec Id  Get","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/widgets/specs/{spec_id}/review`

**Purpose:** Widget Review.
**Auth:** Shared X-Admin-Api-Key.
**Handler:** [fluid.py:widget_review](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L140).

Persistence promotion (fluid 19/20): agent-created → candidate → admin-approved STATIC template.

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `spec_id` | path | True | `{"title":"Spec Id","type":"string"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `ReviewBody`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Widget Review V1 Widgets Specs  Spec Id  Review Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

### POST `/v1/widgets/validate`

**Purpose:** Widget Validate.
**Auth:** Admin key OR learner JWT; handler checks role/ownership.
**Handler:** [fluid.py:widget_validate](../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L79).

| Parameter | Location | Required | Type/default/validation |
|---|---|---|---|
| `authorization` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}` |
| `x-admin-api-key` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}` |

**Request body:** required=True; application/json: `SpecBody`.

| Documented status | Description | Response schema |
|---|---|---|
| 200 | Successful Response | application/json: `{"additionalProperties":true,"title":"Response Widget Validate V1 Widgets Validate Post","type":"object"}` |
| 422 | Validation Error | application/json: `HTTPValidationError` |

## Request/response model index

Resolve definitions, required lists, enumerations, formats and nested references in [openapi.json](openapi.json).

| Model | Required properties | Properties |
|---|---|---|
| `Action` | action, targets | action, targets, label, latex, region |
| `ActivityIn` | - | client_command_id, expected_session_version, activity_id, definition, seconds, anonymous |
| `AgentSessionLinkRequest` | agent_session_id | agent_session_id, surface, context |
| `Angle` | kind, id, vertex, start_degrees, end_degrees, label | kind, id, vertex, start_degrees, end_degrees, radius, label |
| `ArtifactPlan` | subject, topic, title, elements | subject, topic, subtopic, title, summary, difficulty_band, grade_band, goal_type, request_source, linked_problem_id, linked_solution_step_id, parent_bundle_id, concept_ids, skill_ids, theorem_ids, width, height, elements, overlays, frames, modulus, number_theory_mode |
| `AttemptRequest` | problem_code, is_correct | problem_code, is_correct, submitted_answer, time_spent_seconds, hint_count, source |
| `AuthResponse` | access_token, student_id | access_token, token_type, student_id, first_name, last_name, display_name |
| `BulkItem` | kind, key, expected_revision | kind, key, expected_revision |
| `BulkReviewRequest` | items, review_status, note | items, review_status, note |
| `Cell` | kind, id, row, column, label | kind, id, row, column, label |
| `ChatIn` | plan_id | plan_id |
| `CheckSubproblemRequest` | subproblem_prompt, student_answer | subproblem_prompt, student_answer |
| `Circle` | kind, id, cx, cy, radius | kind, id, cx, cy, radius |
| `CoachRequest` | problem_code, diagnosis, student_attempt | problem_code, diagnosis, student_attempt, hint_level |
| `CommandIn` | command_type | command_type, client_command_id, expected_session_version, payload, correlation_id |
| `CompetitionRequest` | external_code, name | external_code, name, organization, country, level |
| `ConceptSearchRequest` | query | query, node_types, chapter_number, retrieval, limit |
| `ConceptSearchRetrieval` | - | semantic, lexical |
| `ConflictDecision` | decision | decision, note |
| `DagReview` | status | status, note |
| `DecisionIn` | decision | decision, expected_session_version |
| `DecomposeRequest` | problem_code | problem_code, max_steps |
| `DependencyEdit` | from_step_id, to_step_id, relationship_type | from_step_id, to_step_id, relationship_type, previous_type, logical_dependency, note |
| `DependencyReject` | from_step_id, to_step_id, relationship_type | from_step_id, to_step_id, relationship_type, note |
| `DiagnoseRequest` | - | trigger |
| `DraftRequest` | statement, kind, note | statement, solution, answer, diagram_required, kind, problem_code, expected_hash, note |
| `DraftUpdate` | statement, note, expected_revision | statement, solution, answer, diagram_required, note, expected_revision |
| `EditRequest` | kind, key, expected_revision, changes, note | kind, key, expected_revision, changes, note |
| `EntityRequest` | kind, key | kind, key |
| `Equation` | kind, id, latex, reason | kind, id, latex, reason, linked_step_id, terms |
| `FeedbackDecision` | feedback_id, status, note | feedback_id, status, note, retrieval_verdict, error_kind |
| `FeedbackRequest` | problem_code, topic, reason | problem_code, topic, reason |
| `FormatBody` | text | text, mode |
| `Frame` | overlay_id | overlay_id, duration_ms, transition |
| `GenerateRequest` | theme, confirm_paid | theme, confirm_paid |
| `GeometryPreview` | subject, topic, title, elements | subject, topic, subtopic, title, summary, difficulty_band, grade_band, goal_type, request_source, linked_problem_id, linked_solution_step_id, parent_bundle_id, concept_ids, skill_ids, theorem_ids, width, height, elements, overlays, frames, modulus, number_theory_mode, incircle_triangles |
| `GuidancePlanRequest` | problem_code | problem_code |
| `HTTPValidationError` | - | detail |
| `ImageRequest` | problem_code, side, mime_type, data_base64, note, rights_confirmed, expected_hash | problem_code, side, mime_type, data_base64, note, rights_confirmed, expected_hash |
| `IndexBody` | search_text_sha256 | embedding, generate_embedding, model, dimensions, search_text_sha256 |
| `ItemReview` | decision | decision, note |
| `JoinIn` | join_code | join_code, display_name |
| `LoginRequest` | email, password | email, password |
| `Merge` | expected_version, step_ids | expected_version, step_ids |
| `MessageIn` | content | content |
| `MicroCheckRequest` | problem_code, index, response | problem_code, index, response |
| `NLIn` | message | message, auto_apply, expected_session_version |
| `Node` | kind, id, x, y, label | kind, id, x, y, label, prime |
| `Overlay` | id, caption, actions | id, caption, linked_step_id, explanation_text, concept_tag, hint_tag, actions |
| `Override` | expected_version, step_id, correctness, why, next_action | expected_version, step_id, correctness, why, next_action, alignment_type |
| `OverrideIn` | action | client_command_id, expected_session_version, action, scope, scope_id |
| `PaperRequest` | paper_external_code, competition_external_code, year, problem_url | paper_external_code, competition_external_code, year, problem_url, solution_url, source_kind, link_scope |
| `PapersBatchRequest` | papers | papers |
| `PatchDecision` | action | action, operations |
| `PlanIn` | title, course_limit_seconds | title, description, plan_key, course_limit_seconds, interaction_buffer_seconds, hard_limit, topics |
| `Point` | kind, id, x, y, label | kind, id, x, y, label, contact |
| `PracticeProgressResponse` | items | items |
| `PracticeThemeProgress` | kind, slug, name, available, attempted, remaining | kind, slug, name, available, attempted, remaining |
| `ProblemSearchRequest` | query | query, filters, retrieval, order_by, limit |
| `ProjectionRequest` | target, scope_id | target, scope_type, scope_id, note |
| `PublishRequest` | expected_fingerprint | expected_fingerprint |
| `ReclassifyRequest` | problem_code | problem_code |
| `RecoveryCreateRequest` | state_version | state_version, trigger, gap_diagnosis_id |
| `RecoveryItemResponse` | state_version | state_version, choice_index, response_text, acknowledged |
| `Region` | media_asset_id | region_id, media_asset_id, page_number, x_norm, y_norm, width_norm, height_norm, start_ms, end_ms, region_type, reading_order, confidence |
| `RegisterRequest` | email, password, first_name, last_name | email, password, first_name, last_name |
| `ResponseIn` | - | client_command_id, option, text, confidence |
| `ReviewBody` | decision | decision, reviewer |
| `SearchBody` | - | query, subject, concept_id, skill_id, theorem_id, difficulty_band, asset_type, limit, offset, query_embedding, generate_embedding, model, dimensions |
| `SearchFilters` | - | competition, year_min, year_max |
| `SearchRetrieval` | - | semantic, lexical, graph |
| `Segment` | kind, id, start, end | kind, id, start, end, auxiliary |
| `SessionIn` | - | title, plan_id, course_limit_seconds, interaction_buffer_seconds, hard_limit, control_mode, topics |
| `SpecBody` | spec | spec, audience |
| `Split` | expected_version, step_id, parts | expected_version, step_id, parts |
| `StarterReviewRequest` | expected_fingerprint, note | expected_fingerprint, note |
| `Step` | ordinal, evidence_ids | step_id, ordinal, plain_text, latex_text, step_type, confidence, evidence_ids |
| `StepEdit` | - | skill_node_id, is_checkpoint, note |
| `StepOutcomeRequest` | result, state_version | result, state_version, actor_type, evaluation |
| `StepPatch` | expected_version | expected_version, plain_text, latex_text |
| `StepResponseRequest` | response_text, state_version | response_text, state_version, evaluate |
| `StoreBody` | spec | spec, source_type, live_session_id |
| `SubmissionIn` | problem_ref | problem_ref |
| `Term` | id, latex | id, latex |
| `TimingIn` | - | course_limit_seconds, interaction_buffer_seconds, hard_limit |
| `TopicIn` | title, planned_seconds | title, concept, problem_ref, planned_seconds, min_seconds, max_seconds, required, scenes |
| `TopicPracticeRequest` | topic | topic, profile_version, limit, target_difficulty, known_skills, exposed_codes, exclude_codes |
| `TopicsIn` | topics | topics |
| `Transcript` | expected_version, steps | expected_version, steps, regions |
| `TransitionIn` | to | client_command_id, expected_session_version, to, topic_index, scene_index |
| `TutorActionIn` | action, based_on_version | action, rationale, based_on_version, participant_id |
| `TutorMessageIn` | message | message, participant_id, client_command_id |
| `ValidationError` | loc, msg, type | loc, msg, type, input, ctx |
| `Versioned` | expected_version | expected_version |
| `VersionedIn` | - | client_command_id, expected_session_version |
| `VersionedRequest` | state_version | state_version |
| `WidgetIn` | - | client_command_id, expected_session_version, widget_spec_id, spec, intent, context, widget_instance_id |
| `WidgetStateIn` | - | client_command_id, expected_session_version, operations, state |
| `mathbank_rest__artifact_runtime__GenerateBody` | - | publish |
| `mathbank_rest__routers__admin_corpus__ReviewRequest` | decision, note, expected_revision | decision, note, expected_revision |
| `mathbank_rest__routers__fluid__GenerateBody` | intent | intent, context, store, source_type |
| `mathbank_rest__routers__pedagogy_admin__ReviewRequest` | kind, key, expected_revision, review_status, note | kind, key, expected_revision, review_status, note |
