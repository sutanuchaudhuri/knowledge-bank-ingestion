# Complete REST operation inventory

Source revision `99b9c503e3ef1abce15fbc681f087401b78227d5`; generated from the checked-in `mathbank_rest.main:app.openapi()` plus registered FastAPI handler metadata. Worktree changes are included.

**324 paths / 346 HTTP operations / 177 schemas.** No endpoint handlers were invoked, no server was started, and no live API/database parity is claimed.

[Readable REST contracts and security caveats](REST_API.md) | [OpenAPI snapshot](openapi.json) | [PostgreSQL schema/access catalog](postgres/README.md) | [DML behavior](POSTGRES_DML.md)

## Reading this inventory

- Each operation is present in the generated source OpenAPI and tied to a registered handler when route metadata is available.
- Parameters, body and documented response models reflect OpenAPI; implementation-only authorization, ownership checks, status codes and side effects may be stricter or broader.
- OpenAPI security requirements are shown exactly as declared. If none is declared, that is not proof an endpoint is anonymous; inspect its handler/dependencies.
- Next.js proxy, exam-agent and Socket.IO endpoints belong to separate services and are not included here.

### GET `/health`
**Purpose:** Health
**Tags:** `ops`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`health`](../../../mathbank-rest/src/mathbank_rest/main.py#L119)
**Operation ID:** `health_health_get`
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Health Health Get","type":"object"}`

### GET `/health/neo4j`
**Purpose:** Health Neo4J
**Tags:** `ops`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`health_neo4j`](../../../mathbank-rest/src/mathbank_rest/main.py#L136)
**Operation ID:** `health_neo4j_health_neo4j_get`
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Health Neo4J Health Neo4J Get","type":"object"}`

### GET `/health/postgres`
**Purpose:** Health Postgres
**Tags:** `ops`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`health_postgres`](../../../mathbank-rest/src/mathbank_rest/main.py#L128)
**Operation ID:** `health_postgres_health_postgres_get`
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Health Postgres Health Postgres Get","type":"object"}`

### POST `/v1/activities/definitions`
**Purpose:** Activity Definition
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`activity_definition`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L261)
**Operation ID:** `activity_definition_v1_activities_definitions_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `{"additionalProperties":true,"title":"Body","type":"object"}`
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Activity Definition V1 Activities Definitions Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/activities`
**Purpose:** List Activities
**Tags:** `admin-activities`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`list_activities`](../../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py#L136)
**Operation ID:** `list_activities_v1_admin_activities_get`
**Parameters:** `q` (query, optional; default ``; `{"default":"","maxLength":200,"title":"Q","type":"string"}`); `activity_type` (query, optional; `{"anyOf":[{"enum":["MCQ","MULTISELECT","NUMERIC","SHORT_RESPONSE","SUBPROBLEM","STEP_ORDERING","ERROR_DIAGNOSIS","CONFIDENCE_CHECK","LIVE_POLL"],"type":"string"},{"type":"null"}],"title":"Activity Type"}`); `source_type` (query, optional; `{"anyOf":[{"enum":["PRECOMPILED","CORPUS_DERIVED","LIVE_AGENT_CREATED","INSTRUCTOR_CREATED"],"type":"string"},{"type":"null"}],"title":"Source Type"}`); `status` (query, optional; default `ALL`; `{"default":"ALL","enum":["ACTIVE","INACTIVE","ALL"],"title":"Status","type":"string"}`); `limit` (query, optional; default `50`; `{"default":50,"maximum":200,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response List Activities V1 Admin Activities Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/activities`
**Purpose:** Create Activity
**Tags:** `admin-activities`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_activity`](../../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py#L123)
**Operation ID:** `create_activity_v1_admin_activities_post`
**Request body:** required; `application/json`: `ActivityCreateRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Activity V1 Admin Activities Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/activities/{activity_id}`
**Purpose:** Get Activity
**Tags:** `admin-activities`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_activity`](../../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py#L150)
**Operation ID:** `get_activity_v1_admin_activities__activity_id__get`
**Parameters:** `activity_id` (path, required; `{"format":"uuid","title":"Activity Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Activity V1 Admin Activities  Activity Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PATCH `/v1/admin/activities/{activity_id}`
**Purpose:** Update Activity
**Tags:** `admin-activities`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`update_activity`](../../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py#L155)
**Operation ID:** `update_activity_v1_admin_activities__activity_id__patch`
**Parameters:** `activity_id` (path, required; `{"format":"uuid","title":"Activity Id","type":"string"}`)
**Request body:** required; `application/json`: `ActivityUpdateRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Update Activity V1 Admin Activities  Activity Id  Patch","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/activities/{activity_id}/deactivate`
**Purpose:** Deactivate Activity
**Tags:** `admin-activities`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`deactivate_activity`](../../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py#L165)
**Operation ID:** `deactivate_activity_v1_admin_activities__activity_id__deactivate_post`
**Parameters:** `activity_id` (path, required; `{"format":"uuid","title":"Activity Id","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__admin_activities__ActorRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Deactivate Activity V1 Admin Activities  Activity Id  Deactivate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/activities/{activity_id}/reactivate`
**Purpose:** Reactivate Activity
**Tags:** `admin-activities`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`reactivate_activity`](../../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py#L170)
**Operation ID:** `reactivate_activity_v1_admin_activities__activity_id__reactivate_post`
**Parameters:** `activity_id` (path, required; `{"format":"uuid","title":"Activity Id","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__admin_activities__ActorRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Reactivate Activity V1 Admin Activities  Activity Id  Reactivate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PATCH `/v1/admin/activities/{activity_id}/skill-mapping`
**Purpose:** Set Skill Mapping
**Tags:** `admin-activities`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`set_skill_mapping`](../../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py#L175)
**Operation ID:** `set_skill_mapping_v1_admin_activities__activity_id__skill_mapping_patch`
**Parameters:** `activity_id` (path, required; `{"format":"uuid","title":"Activity Id","type":"string"}`)
**Request body:** required; `application/json`: `SkillMappingRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Set Skill Mapping V1 Admin Activities  Activity Id  Skill Mapping Patch","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PATCH `/v1/admin/activities/{activity_id}/source-mapping`
**Purpose:** Set Source Mapping
**Tags:** `admin-activities`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`set_source_mapping`](../../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py#L182)
**Operation ID:** `set_source_mapping_v1_admin_activities__activity_id__source_mapping_patch`
**Parameters:** `activity_id` (path, required; `{"format":"uuid","title":"Activity Id","type":"string"}`)
**Request body:** required; `application/json`: `SourceMappingRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Set Source Mapping V1 Admin Activities  Activity Id  Source Mapping Patch","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/agent-sessions`
**Purpose:** Admin Agent Sessions
**Tags:** `agent-sessions`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`admin_agent_sessions`](../../../mathbank-rest/src/mathbank_rest/routers/agent_sessions.py#L56)
**Operation ID:** `admin_agent_sessions_v1_admin_agent_sessions_get`
**Parameters:** `student` (query, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"description":"e-mail substring or student uuid","title":"Student"}`; e-mail substring or student uuid); `limit` (query, optional; default `100`; `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Admin Agent Sessions V1 Admin Agent Sessions Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/agent-sessions/{agent_session_id}/transcript`
**Purpose:** Admin Agent Transcript
**Tags:** `agent-sessions`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`admin_agent_transcript`](../../../mathbank-rest/src/mathbank_rest/routers/agent_sessions.py#L63)
**Operation ID:** `admin_agent_transcript_v1_admin_agent_sessions__agent_session_id__transcript_get`
**Parameters:** `agent_session_id` (path, required; `{"title":"Agent Session Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Admin Agent Transcript V1 Admin Agent Sessions  Agent Session Id  Transcript Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/attempts/{attempt_id}/diagnoses`
**Purpose:** Admin List Diagnoses
**Tags:** `step-runtime`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`admin_list_diagnoses`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L238)
**Operation ID:** `admin_list_diagnoses_v1_admin_attempts__attempt_id__diagnoses_get`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Admin List Diagnoses V1 Admin Attempts  Attempt Id  Diagnoses Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/competitions`
**Purpose:** Create Competition
**Tags:** `admin-pipeline`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_competition`](../../../mathbank-rest/src/mathbank_rest/routers/admin.py#L59)
**Operation ID:** `create_competition_v1_admin_competitions_post`
**Request body:** required; `application/json`: `CompetitionRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Competition V1 Admin Competitions Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/corpus/drafts`
**Purpose:** Drafts
**Tags:** `admin-corpus`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`drafts`](../../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L148)
**Operation ID:** `drafts_v1_admin_corpus_drafts_get`
**Parameters:** `state` (query, optional; default `DRAFT`; `{"default":"DRAFT","enum":["DRAFT","APPROVED","REJECTED"],"title":"State","type":"string"}`); `limit` (query, optional; default `20`; `{"default":20,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/corpus/drafts`
**Purpose:** Create Draft
**Tags:** `admin-corpus`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_draft`](../../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L88)
**Operation ID:** `create_draft_v1_admin_corpus_drafts_post`
**Request body:** required; `application/json`: `DraftRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PUT `/v1/admin/corpus/drafts/{draft_id}`
**Purpose:** Update Draft
**Tags:** `admin-corpus`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`update_draft`](../../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L99)
**Operation ID:** `update_draft_v1_admin_corpus_drafts__draft_id__put`
**Parameters:** `draft_id` (path, required; `{"format":"uuid","title":"Draft Id","type":"string"}`)
**Request body:** required; `application/json`: `DraftUpdate` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/corpus/drafts/{draft_id}/image`
**Purpose:** Draft Image
**Tags:** `admin-corpus`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`draft_image`](../../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L163)
**Operation ID:** `draft_image_v1_admin_corpus_drafts__draft_id__image_get`
**Parameters:** `draft_id` (path, required; `{"format":"uuid","title":"Draft Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/corpus/drafts/{draft_id}/review`
**Purpose:** Review
**Tags:** `admin-corpus`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`review`](../../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L175)
**Operation ID:** `review_v1_admin_corpus_drafts__draft_id__review_post`
**Parameters:** `draft_id` (path, required; `{"format":"uuid","title":"Draft Id","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__admin_corpus__ReviewRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/corpus/generate`
**Purpose:** Generate
**Tags:** `admin-corpus`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`generate`](../../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L137)
**Operation ID:** `generate_v1_admin_corpus_generate_post`
**Request body:** required; `application/json`: `GenerateRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/corpus/images`
**Purpose:** Upload
**Tags:** `admin-corpus`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`upload`](../../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L119)
**Operation ID:** `upload_v1_admin_corpus_images_post`
**Request body:** required; `application/json`: `ImageRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/corpus/problems`
**Purpose:** Problems
**Tags:** `admin-corpus`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`problems`](../../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L71)
**Operation ID:** `problems_v1_admin_corpus_problems_get`
**Parameters:** `competition` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Competition"}`); `year` (query, optional; `{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Year"}`); `paper` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Paper"}`); `number` (query, optional; `{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Number"}`); `q` (query, optional; default ``; `{"default":"","title":"Q","type":"string"}`); `missing_only` (query, optional; default `True`; `{"default":true,"title":"Missing Only","type":"boolean"}`); `limit` (query, optional; default `20`; `{"default":20,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/corpus/problems/{code}`
**Purpose:** Detail
**Tags:** `admin-corpus`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`detail`](../../../mathbank-rest/src/mathbank_rest/routers/admin_corpus.py#L79)
**Operation ID:** `detail_v1_admin_corpus_problems__code__get`
**Parameters:** `code` (path, required; `{"title":"Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/imports/actions`
**Purpose:** Actions
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`actions`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L188)
**Operation ID:** `actions_v1_admin_imports_actions_get`
**Parameters:** `target_type` (query, optional; `{"anyOf":[{"enum":["IMPORT_CONFLICT","SOLUTION_STEP","STEP_DEPENDENCY","SOLUTION_DAG","LEARNING_ITEM","PROJECTION_REQUEST"],"type":"string"},{"type":"null"}],"title":"Target Type"}`); `limit` (query, optional; default `100`; `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Actions V1 Admin Imports Actions Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/imports/conflicts/{conflict_id}/decision`
**Purpose:** Decide Conflict
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`decide_conflict`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L80)
**Operation ID:** `decide_conflict_v1_admin_imports_conflicts__conflict_id__decision_post`
**Parameters:** `conflict_id` (path, required; `{"title":"Conflict Id","type":"integer"}`)
**Request body:** required; `application/json`: `ConflictDecision` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Decide Conflict V1 Admin Imports Conflicts  Conflict Id  Decision Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PUT `/v1/admin/imports/dependencies`
**Purpose:** Upsert Dependency
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`upsert_dependency`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L156)
**Operation ID:** `upsert_dependency_v1_admin_imports_dependencies_put`
**Request body:** required; `application/json`: `DependencyEdit` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Upsert Dependency V1 Admin Imports Dependencies Put","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/imports/dependencies/reject`
**Purpose:** Reject Dependency
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`reject_dependency`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L171)
**Operation ID:** `reject_dependency_v1_admin_imports_dependencies_reject_post`
**Request body:** required; `application/json`: `DependencyReject` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Reject Dependency V1 Admin Imports Dependencies Reject Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/imports/learning-items/{learning_item_id}/review`
**Purpose:** Review Learning Item
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`review_learning_item`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L120)
**Operation ID:** `review_learning_item_v1_admin_imports_learning_items__learning_item_id__review_post`
**Parameters:** `learning_item_id` (path, required; `{"title":"Learning Item Id","type":"string"}`)
**Request body:** required; `application/json`: `ItemReview` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Review Learning Item V1 Admin Imports Learning Items  Learning Item Id  Review Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/imports/packages`
**Purpose:** Packages
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`packages`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L44)
**Operation ID:** `packages_v1_admin_imports_packages_get`
**Parameters:** `book` (query, optional; `{"anyOf":[{"maxLength":64,"pattern":"^[A-Z0-9_]+$","type":"string"},{"type":"null"}],"title":"Book"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Packages V1 Admin Imports Packages Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/imports/packages/{package_id}`
**Purpose:** Package Detail
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`package_detail`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L50)
**Operation ID:** `package_detail_v1_admin_imports_packages__package_id__get`
**Parameters:** `package_id` (path, required; `{"title":"Package Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Package Detail V1 Admin Imports Packages  Package Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/imports/packages/{package_id}/conflicts`
**Purpose:** Conflicts
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`conflicts`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L66)
**Operation ID:** `conflicts_v1_admin_imports_packages__package_id__conflicts_get`
**Parameters:** `package_id` (path, required; `{"title":"Package Id","type":"string"}`); `entity_type` (query, optional; `{"anyOf":[{"maxLength":40,"type":"string"},{"type":"null"}],"title":"Entity Type"}`); `resolution_status` (query, optional; `{"anyOf":[{"enum":["OPEN","AUTO_RESOLVED","RESOLVED","IGNORED"],"type":"string"},{"type":"null"}],"title":"Resolution Status"}`); `limit` (query, optional; default `50`; `{"default":50,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Conflicts V1 Admin Imports Packages  Package Id  Conflicts Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/imports/packages/{package_id}/issues`
**Purpose:** Issues
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`issues`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L57)
**Operation ID:** `issues_v1_admin_imports_packages__package_id__issues_get`
**Parameters:** `package_id` (path, required; `{"title":"Package Id","type":"string"}`); `entity_type` (query, optional; `{"anyOf":[{"maxLength":40,"type":"string"},{"type":"null"}],"title":"Entity Type"}`); `kind` (query, optional; default `ALL`; `{"default":"ALL","enum":["ALL","REJECTED","WARNINGS"],"title":"Kind","type":"string"}`); `limit` (query, optional; default `50`; `{"default":50,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Issues V1 Admin Imports Packages  Package Id  Issues Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/imports/problems/{code}/dag`
**Purpose:** Problem Dag
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`problem_dag`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L128)
**Operation ID:** `problem_dag_v1_admin_imports_problems__code__dag_get`
**Parameters:** `code` (path, required; `{"title":"Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Problem Dag V1 Admin Imports Problems  Code  Dag Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/imports/problems/{code}/dag/review`
**Purpose:** Review Dag
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`review_dag`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L183)
**Operation ID:** `review_dag_v1_admin_imports_problems__code__dag_review_post`
**Parameters:** `code` (path, required; `{"title":"Code","type":"string"}`)
**Request body:** required; `application/json`: `DagReview` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Review Dag V1 Admin Imports Problems  Code  Dag Review Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/imports/projection-requests`
**Purpose:** Projection Requests
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`projection_requests`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L94)
**Operation ID:** `projection_requests_v1_admin_imports_projection_requests_get`
**Parameters:** `status` (query, optional; `{"anyOf":[{"enum":["PENDING","DONE","CANCELLED"],"type":"string"},{"type":"null"}],"title":"Status"}`); `limit` (query, optional; default `100`; `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Projection Requests V1 Admin Imports Projection Requests Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/imports/projection-requests`
**Purpose:** Request Projection
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`request_projection`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L107)
**Operation ID:** `request_projection_v1_admin_imports_projection_requests_post`
**Request body:** required; `application/json`: `ProjectionRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `202` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Request Projection V1 Admin Imports Projection Requests Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/imports/reconciliation`
**Purpose:** Reconciliation
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`reconciliation`](../../../mathbank-rest/src/mathbank_rest/routers/admin_imports.py#L88)
**Operation ID:** `reconciliation_v1_admin_imports_reconciliation_get`
**Parameters:** `book` (query, optional; default `PRASOLOV_PGV1`; `{"default":"PRASOLOV_PGV1","maxLength":64,"pattern":"^[A-Z0-9_]+$","title":"Book","type":"string"}`); `graph` (query, optional; default `True`; `{"default":true,"description":"Also count Neo4j nodes/edges","title":"Graph","type":"boolean"}`; Also count Neo4j nodes/edges)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Reconciliation V1 Admin Imports Reconciliation Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PATCH `/v1/admin/imports/steps/{step_id}`
**Purpose:** Edit Step
**Tags:** `admin-imports`
**OpenAPI security:** `APIKeyHeader`
**Operation ID:** `edit_step_v1_admin_imports_steps__step_id__patch`
**Parameters:** `step_id` (path, required; `{"title":"Step Id","type":"string"}`)
**Request body:** required; `application/json`: `StepEdit` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Edit Step V1 Admin Imports Steps  Step Id  Patch","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/interaction-templates`
**Purpose:** List Templates
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`list_templates`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L68)
**Operation ID:** `list_templates_v1_admin_interaction_templates_get`
**Documented responses:** `200` Successful Response: `application/json` unspecified

### POST `/v1/admin/interaction-templates/graph/rebuild`
**Purpose:** Rebuild Graph
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`rebuild_graph`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L256)
**Operation ID:** `rebuild_graph_v1_admin_interaction_templates_graph_rebuild_post`
**Documented responses:** `200` Successful Response: `application/json` unspecified

### GET `/v1/admin/interaction-templates/graph/verify`
**Purpose:** Verify Graph
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`verify_graph`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L271)
**Operation ID:** `verify_graph_v1_admin_interaction_templates_graph_verify_get`
**Documented responses:** `200` Successful Response: `application/json` unspecified

### POST `/v1/admin/interaction-templates/instances/{instance_id}/approve`
**Purpose:** Approve Instance
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`approve_instance`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L111)
**Operation ID:** `approve_instance_v1_admin_interaction_templates_instances__instance_id__approve_post`
**Parameters:** `instance_id` (path, required; `{"format":"uuid","title":"Instance Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/interaction-templates/instances/{instance_id}/validate`
**Purpose:** Validate Instance
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`validate_instance`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L105)
**Operation ID:** `validate_instance_v1_admin_interaction_templates_instances__instance_id__validate_post`
**Parameters:** `instance_id` (path, required; `{"format":"uuid","title":"Instance Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/interaction-templates/load-seed-catalog`
**Purpose:** Load Seed Catalog
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`load_seed_catalog`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L73)
**Operation ID:** `load_seed_catalog_v1_admin_interaction_templates_load_seed_catalog_post`
**Documented responses:** `200` Successful Response: `application/json` unspecified

### GET `/v1/admin/interaction-templates/scenes`
**Purpose:** List Scenes
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`list_scenes`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L140)
**Operation ID:** `list_scenes_v1_admin_interaction_templates_scenes_get`
**Documented responses:** `200` Successful Response: `application/json` unspecified

### GET `/v1/admin/interaction-templates/scenes/promotable-candidates`
**Purpose:** List Promotable Candidates Endpoint
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`list_promotable_candidates_endpoint`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L130)
**Operation ID:** `list_promotable_candidates_endpoint_v1_admin_interaction_templates_scenes_promotable_candidates_get`
**Documented responses:** `200` Successful Response: `application/json` unspecified

### POST `/v1/admin/interaction-templates/scenes/promote`
**Purpose:** Promote Scene
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`promote_scene`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L199)
**Operation ID:** `promote_scene_v1_admin_interaction_templates_scenes_promote_post`
**Request body:** required; `application/json`: `PromoteSceneRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/interaction-templates/scenes/{scene_spec_id}`
**Purpose:** Get Scene
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_scene`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L157)
**Operation ID:** `get_scene_v1_admin_interaction_templates_scenes__scene_spec_id__get`
**Parameters:** `scene_spec_id` (path, required; `{"format":"uuid","title":"Scene Spec Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/interaction-templates/scenes/{scene_spec_id}/approve`
**Purpose:** Approve Scene
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`approve_scene`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L219)
**Operation ID:** `approve_scene_v1_admin_interaction_templates_scenes__scene_spec_id__approve_post`
**Parameters:** `scene_spec_id` (path, required; `{"format":"uuid","title":"Scene Spec Id","type":"string"}`); `approved_by` (query, optional; default `admin`; `{"default":"admin","title":"Approved By","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/interaction-templates/scenes/{scene_spec_id}/create-instance`
**Purpose:** Create Instance From Scene
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_instance_from_scene`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L240)
**Operation ID:** `create_instance_from_scene_v1_admin_interaction_templates_scenes__scene_spec_id__create_instance_post`
**Parameters:** `scene_spec_id` (path, required; `{"format":"uuid","title":"Scene Spec Id","type":"string"}`)
**Request body:** required; `application/json`: `CreateInstanceFromSceneRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/interaction-templates/scenes/{scene_spec_id}/validate`
**Purpose:** Validate Scene
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`validate_scene`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L213)
**Operation ID:** `validate_scene_v1_admin_interaction_templates_scenes__scene_spec_id__validate_post`
**Parameters:** `scene_spec_id` (path, required; `{"format":"uuid","title":"Scene Spec Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/interaction-templates/scenes/{scene_spec_id}/video`
**Purpose:** Get Scene Video
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_scene_video`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L179)
**Operation ID:** `get_scene_video_v1_admin_interaction_templates_scenes__scene_spec_id__video_get`
**Parameters:** `scene_spec_id` (path, required; `{"format":"uuid","title":"Scene Spec Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/interaction-templates/versions/{version_id}/publish`
**Purpose:** Publish Template Version
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`publish_template_version`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L86)
**Operation ID:** `publish_template_version_v1_admin_interaction_templates_versions__version_id__publish_post`
**Parameters:** `version_id` (path, required; `{"format":"uuid","title":"Version Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/interaction-templates/versions/{version_id}/validate`
**Purpose:** Validate Template Version
**Tags:** `admin-interaction-templates`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`validate_template_version`](../../../mathbank-rest/src/mathbank_rest/routers/interaction_templates.py#L80)
**Operation ID:** `validate_template_version_v1_admin_interaction_templates_versions__version_id__validate_post`
**Parameters:** `version_id` (path, required; `{"format":"uuid","title":"Version Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/knowledge-gaps`
**Purpose:** Admin Gap Overview
**Tags:** `step-runtime`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`admin_gap_overview`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L252)
**Operation ID:** `admin_gap_overview_v1_admin_knowledge_gaps_get`
**Parameters:** `status` (query, optional; `{"anyOf":[{"enum":["UNRESOLVED","CONFIRMED","REJECTED","RESOLVED"],"type":"string"},{"type":"null"}],"title":"Status"}`); `student` (query, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"description":"e-mail substring or student uuid","title":"Student"}`; e-mail substring or student uuid); `limit` (query, optional; default `100`; `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Admin Gap Overview V1 Admin Knowledge Gaps Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/micro-courses`
**Purpose:** List Admin Courses
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`list_admin_courses`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L207)
**Operation ID:** `list_admin_courses_v1_admin_micro_courses_get`
**Parameters:** `limit` (query, optional; default `50`; `{"default":50,"maximum":200,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Admin Courses V1 Admin Micro Courses Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses`
**Purpose:** Create Admin Course
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_admin_course`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L215)
**Operation ID:** `create_admin_course_v1_admin_micro_courses_post`
**Request body:** required; `application/json`: `CreateCourse` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Admin Course V1 Admin Micro Courses Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/micro-courses/interactions`
**Purpose:** Get Approved Interactions
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_approved_interactions`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L231)
**Operation ID:** `get_approved_interactions_v1_admin_micro_courses_interactions_get`
**Parameters:** `limit` (query, optional; default `100`; `{"default":100,"maximum":250,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Approved Interactions V1 Admin Micro Courses Interactions Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/micro-courses/releases/{release_id}`
**Purpose:** Get Admin Release
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_admin_release`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L287)
**Operation ID:** `get_admin_release_v1_admin_micro_courses_releases__release_id__get`
**Parameters:** `release_id` (path, required; `{"format":"uuid","title":"Release Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Admin Release V1 Admin Micro Courses Releases  Release Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/micro-courses/releases/{release_id}/diff/{other_release_id}`
**Purpose:** Diff Admin Releases
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`diff_admin_releases`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L292)
**Operation ID:** `diff_admin_releases_v1_admin_micro_courses_releases__release_id__diff__other_release_id__get`
**Parameters:** `release_id` (path, required; `{"format":"uuid","title":"Release Id","type":"string"}`); `other_release_id` (path, required; `{"format":"uuid","title":"Other Release Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Diff Admin Releases V1 Admin Micro Courses Releases  Release Id  Diff  Other Release Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/releases/{release_id}/modules`
**Purpose:** Create Module
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_module`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L297)
**Operation ID:** `create_module_v1_admin_micro_courses_releases__release_id__modules_post`
**Parameters:** `release_id` (path, required; `{"format":"uuid","title":"Release Id","type":"string"}`)
**Request body:** required; `application/json`: `CreateModule` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Module V1 Admin Micro Courses Releases  Release Id  Modules Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/releases/{release_id}/publish`
**Purpose:** Publish Admin Release
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`publish_admin_release`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L448)
**Operation ID:** `publish_admin_release_v1_admin_micro_courses_releases__release_id__publish_post`
**Parameters:** `release_id` (path, required; `{"format":"uuid","title":"Release Id","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__micro_courses__PublishRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Publish Admin Release V1 Admin Micro Courses Releases  Release Id  Publish Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/releases/{release_id}/review`
**Purpose:** Review Admin Release
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`review_admin_release`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L437)
**Operation ID:** `review_admin_release_v1_admin_micro_courses_releases__release_id__review_post`
**Parameters:** `release_id` (path, required; `{"format":"uuid","title":"Release Id","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__micro_courses__ReviewRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Review Admin Release V1 Admin Micro Courses Releases  Release Id  Review Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/releases/{release_id}/states`
**Purpose:** Create State
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_state`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L312)
**Operation ID:** `create_state_v1_admin_micro_courses_releases__release_id__states_post`
**Parameters:** `release_id` (path, required; `{"format":"uuid","title":"Release Id","type":"string"}`)
**Request body:** required; `application/json`: `CreateState` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create State V1 Admin Micro Courses Releases  Release Id  States Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/releases/{release_id}/transitions`
**Purpose:** Create Transition
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_transition`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L416)
**Operation ID:** `create_transition_v1_admin_micro_courses_releases__release_id__transitions_post`
**Parameters:** `release_id` (path, required; `{"format":"uuid","title":"Release Id","type":"string"}`)
**Request body:** required; `application/json`: `CreateTransition` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Transition V1 Admin Micro Courses Releases  Release Id  Transitions Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/releases/{release_id}/validate`
**Purpose:** Validate Admin Release
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`validate_admin_release`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L431)
**Operation ID:** `validate_admin_release_v1_admin_micro_courses_releases__release_id__validate_post`
**Parameters:** `release_id` (path, required; `{"format":"uuid","title":"Release Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Validate Admin Release V1 Admin Micro Courses Releases  Release Id  Validate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/states/{state_id}/activities`
**Purpose:** Attach Activity
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`attach_activity`](../../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py#L191)
**Operation ID:** `attach_activity_v1_admin_micro_courses_states__state_id__activities_post`
**Parameters:** `state_id` (path, required; `{"format":"uuid","title":"State Id","type":"string"}`)
**Request body:** required; `application/json`: `AttachActivityRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Attach Activity V1 Admin Micro Courses States  State Id  Activities Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### DELETE `/v1/admin/micro-courses/states/{state_id}/activities/{activity_id}`
**Purpose:** Detach Activity
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`detach_activity`](../../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py#L202)
**Operation ID:** `detach_activity_v1_admin_micro_courses_states__state_id__activities__activity_id__delete`
**Parameters:** `state_id` (path, required; `{"format":"uuid","title":"State Id","type":"string"}`); `activity_id` (path, required; `{"format":"uuid","title":"Activity Id","type":"string"}`)
**Documented responses:** `204` Successful Response: no response schema declared; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PATCH `/v1/admin/micro-courses/states/{state_id}/activities/{activity_id}`
**Purpose:** Update Activity Binding
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`update_activity_binding`](../../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py#L207)
**Operation ID:** `update_activity_binding_v1_admin_micro_courses_states__state_id__activities__activity_id__patch`
**Parameters:** `state_id` (path, required; `{"format":"uuid","title":"State Id","type":"string"}`); `activity_id` (path, required; `{"format":"uuid","title":"Activity Id","type":"string"}`)
**Request body:** required; `application/json`: `UpdateBindingRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Update Activity Binding V1 Admin Micro Courses States  State Id  Activities  Activity Id  Patch","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/states/{state_id}/assets`
**Purpose:** Upload State Asset
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`upload_state_asset`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L358)
**Operation ID:** `upload_state_asset_v1_admin_micro_courses_states__state_id__assets_post`
**Parameters:** `state_id` (path, required; `{"format":"uuid","title":"State Id","type":"string"}`); `title` (query, required; `{"maxLength":300,"minLength":1,"title":"Title","type":"string"}`); `presentation_role` (query, optional; default `SUPPORT`; `{"default":"SUPPORT","enum":["PRIMARY","SUPPORT","EXAMPLE","REFERENCE","OPTIONAL"],"title":"Presentation Role","type":"string"}`); `reviewed_by` (query, required; `{"maxLength":200,"minLength":1,"title":"Reviewed By","type":"string"}`); `admin_confirmed` (query, optional; default `False`; `{"default":false,"title":"Admin Confirmed","type":"boolean"}`); `rights_note` (query, optional; `{"anyOf":[{"maxLength":1000,"type":"string"},{"type":"null"}],"title":"Rights Note"}`)
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Upload State Asset V1 Admin Micro Courses States  State Id  Assets Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/states/{state_id}/bindings`
**Purpose:** Bind State
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`bind_state`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L332)
**Operation ID:** `bind_state_v1_admin_micro_courses_states__state_id__bindings_post`
**Parameters:** `state_id` (path, required; `{"format":"uuid","title":"State Id","type":"string"}`)
**Request body:** required; `application/json`: `StateBinding` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Bind State V1 Admin Micro Courses States  State Id  Bindings Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/states/{state_id}/interactions`
**Purpose:** Bind Interaction
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`bind_interaction`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L346)
**Operation ID:** `bind_interaction_v1_admin_micro_courses_states__state_id__interactions_post`
**Parameters:** `state_id` (path, required; `{"format":"uuid","title":"State Id","type":"string"}`)
**Request body:** required; `application/json`: `AttachInteraction` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Bind Interaction V1 Admin Micro Courses States  State Id  Interactions Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PATCH `/v1/admin/micro-courses/states/{state_id}/items/{item_kind}/{item_id}/sequence`
**Purpose:** Set Item Sequence Position
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`set_item_sequence_position`](../../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py#L216)
**Operation ID:** `set_item_sequence_position_v1_admin_micro_courses_states__state_id__items__item_kind___item_id__sequence_patch`
**Parameters:** `state_id` (path, required; `{"format":"uuid","title":"State Id","type":"string"}`); `item_kind` (path, required; `{"enum":["asset","interaction","learning_item","activity"],"title":"Item Kind","type":"string"}`); `item_id` (path, required; `{"title":"Item Id","type":"string"}`)
**Request body:** required; `application/json`: `SetItemSequenceRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Set Item Sequence Position V1 Admin Micro Courses States  State Id  Items  Item Kind   Item Id  Sequence Patch","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/micro-courses/targets`
**Purpose:** Search Targets
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`search_targets`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L198)
**Operation ID:** `search_targets_v1_admin_micro_courses_targets_get`
**Parameters:** `target_type` (query, required; `{"enum":["CONCEPT","TECHNIQUE","SKILL","THEOREM","MISCONCEPTION"],"title":"Target Type","type":"string"}`); `q` (query, optional; default ``; `{"default":"","maxLength":120,"title":"Q","type":"string"}`); `limit` (query, optional; default `20`; `{"default":20,"maximum":50,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Search Targets V1 Admin Micro Courses Targets Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/micro-courses/templates`
**Purpose:** Get Widget Library
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_widget_library`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L238)
**Operation ID:** `get_widget_library_v1_admin_micro_courses_templates_get`
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Widget Library V1 Admin Micro Courses Templates Get","type":"object"}`

### GET `/v1/admin/micro-courses/{canonical_code}`
**Purpose:** Get Admin Course
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_admin_course`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L243)
**Operation ID:** `get_admin_course_v1_admin_micro_courses__canonical_code__get`
**Parameters:** `canonical_code` (path, required; `{"title":"Canonical Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Admin Course V1 Admin Micro Courses  Canonical Code  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/micro-courses/{canonical_code}/activity`
**Purpose:** Get Admin Course Activity
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_admin_course_activity`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L263)
**Operation ID:** `get_admin_course_activity_v1_admin_micro_courses__canonical_code__activity_get`
**Parameters:** `canonical_code` (path, required; `{"title":"Canonical Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Admin Course Activity V1 Admin Micro Courses  Canonical Code  Activity Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/{canonical_code}/deactivate`
**Purpose:** Deactivate Admin Course
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`deactivate_admin_course`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L253)
**Operation ID:** `deactivate_admin_course_v1_admin_micro_courses__canonical_code__deactivate_post`
**Parameters:** `canonical_code` (path, required; `{"title":"Canonical Code","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__micro_courses__ActorRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Deactivate Admin Course V1 Admin Micro Courses  Canonical Code  Deactivate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/micro-courses/{canonical_code}/preview`
**Purpose:** Get Admin Course Preview
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_admin_course_preview`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L268)
**Operation ID:** `get_admin_course_preview_v1_admin_micro_courses__canonical_code__preview_get`
**Parameters:** `canonical_code` (path, required; `{"title":"Canonical Code","type":"string"}`); `release_id` (query, optional; `{"anyOf":[{"format":"uuid","type":"string"},{"type":"null"}],"title":"Release Id"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Admin Course Preview V1 Admin Micro Courses  Canonical Code  Preview Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/{canonical_code}/reactivate`
**Purpose:** Reactivate Admin Course
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`reactivate_admin_course`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L258)
**Operation ID:** `reactivate_admin_course_v1_admin_micro_courses__canonical_code__reactivate_post`
**Parameters:** `canonical_code` (path, required; `{"title":"Canonical Code","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__micro_courses__ActorRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Reactivate Admin Course V1 Admin Micro Courses  Canonical Code  Reactivate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/micro-courses/{canonical_code}/releases`
**Purpose:** Create Admin Release
**Tags:** `admin-micro-courses`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_admin_release`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L276)
**Operation ID:** `create_admin_release_v1_admin_micro_courses__canonical_code__releases_post`
**Parameters:** `canonical_code` (path, required; `{"title":"Canonical Code","type":"string"}`)
**Request body:** required; `application/json`: `CreateRelease` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Admin Release V1 Admin Micro Courses  Canonical Code  Releases Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/papers`
**Purpose:** List Papers
**Tags:** `admin-pipeline`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`list_papers`](../../../mathbank-rest/src/mathbank_rest/routers/admin.py#L97)
**Operation ID:** `list_papers_v1_admin_papers_get`
**Parameters:** `competition` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Competition"}`); `status` (query, optional; `{"anyOf":[{"enum":["PENDING","DOWNLOADED","PARSED","INGESTED","FAILED"],"type":"string"},{"type":"null"}],"title":"Status"}`); `limit` (query, optional; default `100`; `{"default":100,"maximum":500,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Papers V1 Admin Papers Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/papers`
**Purpose:** Register Paper
**Tags:** `admin-pipeline`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`register_paper`](../../../mathbank-rest/src/mathbank_rest/routers/admin.py#L87)
**Operation ID:** `register_paper_v1_admin_papers_post`
**Request body:** required; `application/json`: `PaperRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Register Paper V1 Admin Papers Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/papers/batch`
**Purpose:** Register Papers Batch
**Tags:** `admin-pipeline`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`register_papers_batch`](../../../mathbank-rest/src/mathbank_rest/routers/admin.py#L92)
**Operation ID:** `register_papers_batch_v1_admin_papers_batch_post`
**Request body:** required; `application/json`: `PapersBatchRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Register Papers Batch V1 Admin Papers Batch Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/papers/{paper_external_code}/retry`
**Purpose:** Retry Paper
**Tags:** `admin-pipeline`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`retry_paper`](../../../mathbank-rest/src/mathbank_rest/routers/admin.py#L107)
**Operation ID:** `retry_paper_v1_admin_papers__paper_external_code__retry_post`
**Parameters:** `paper_external_code` (path, required; `{"title":"Paper External Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Retry Paper V1 Admin Papers  Paper External Code  Retry Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/pedagogy/approve-starter`
**Purpose:** Approve Starter
**Tags:** `admin-pedagogy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`approve_starter`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L190)
**Operation ID:** `approve_starter_v1_admin_pedagogy_approve_starter_post`
**Request body:** required; `application/json`: `StarterReviewRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Approve Starter V1 Admin Pedagogy Approve Starter Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/pedagogy/bulk-review`
**Purpose:** Bulk Review
**Tags:** `admin-pedagogy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`bulk_review`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L183)
**Operation ID:** `bulk_review_v1_admin_pedagogy_bulk_review_post`
**Request body:** required; `application/json`: `BulkReviewRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Bulk Review V1 Admin Pedagogy Bulk Review Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/pedagogy/edit`
**Purpose:** Edit
**Tags:** `admin-pedagogy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`edit`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L195)
**Operation ID:** `edit_v1_admin_pedagogy_edit_post`
**Request body:** required; `application/json`: `mathbank_rest__routers__pedagogy_admin__EditRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Edit V1 Admin Pedagogy Edit Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/pedagogy/feedback`
**Purpose:** Feedback Queue
**Tags:** `admin-pedagogy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`feedback_queue`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L61)
**Operation ID:** `feedback_queue_v1_admin_pedagogy_feedback_get`
**Parameters:** `limit` (query, optional; default `25`; `{"default":25,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Feedback Queue V1 Admin Pedagogy Feedback Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/pedagogy/feedback-review`
**Purpose:** Feedback Review
**Tags:** `admin-pedagogy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`feedback_review`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L66)
**Operation ID:** `feedback_review_v1_admin_pedagogy_feedback_review_post`
**Request body:** required; `application/json`: `FeedbackDecision` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Feedback Review V1 Admin Pedagogy Feedback Review Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/pedagogy/history`
**Purpose:** History
**Tags:** `admin-pedagogy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`history`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L173)
**Operation ID:** `history_v1_admin_pedagogy_history_post`
**Request body:** required; `application/json`: `EntityRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response History V1 Admin Pedagogy History Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/pedagogy/publish`
**Purpose:** Publish
**Tags:** `admin-pedagogy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`publish`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L178)
**Operation ID:** `publish_v1_admin_pedagogy_publish_post`
**Request body:** required; `application/json`: `mathbank_rest__routers__pedagogy_admin__PublishRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Publish V1 Admin Pedagogy Publish Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/pedagogy/queue`
**Purpose:** Queue
**Tags:** `admin-pedagogy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`queue`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L156)
**Operation ID:** `queue_v1_admin_pedagogy_queue_get`
**Parameters:** `kind` (query, optional; default `skill`; `{"default":"skill","enum":["skill","skill_concept","skill_relation","concept_relation","problem_skill","problem_pedagogy","problem_concept","problem_technique"],"title":"Kind","type":"string"}`); `status` (query, optional; default `PENDING`; `{"default":"PENDING","enum":["ALL","PENDING","REVIEWED","REJECTED"],"title":"Status","type":"string"}`); `limit` (query, optional; default `25`; `{"default":25,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Queue V1 Admin Pedagogy Queue Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/pedagogy/reclassify`
**Purpose:** Reclassify
**Tags:** `admin-pedagogy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`reclassify`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L200)
**Operation ID:** `reclassify_v1_admin_pedagogy_reclassify_post`
**Request body:** required; `application/json`: `ReclassifyRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Reclassify V1 Admin Pedagogy Reclassify Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/pedagogy/retrieval-examples`
**Purpose:** Retrieval Examples
**Tags:** `admin-pedagogy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`retrieval_examples`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L78)
**Operation ID:** `retrieval_examples_v1_admin_pedagogy_retrieval_examples_get`
**Parameters:** `limit` (query, optional; default `100`; `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Retrieval Examples V1 Admin Pedagogy Retrieval Examples Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/pedagogy/review`
**Purpose:** Review
**Tags:** `admin-pedagogy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`review`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py#L166)
**Operation ID:** `review_v1_admin_pedagogy_review_post`
**Request body:** required; `application/json`: `mathbank_rest__routers__pedagogy_admin__ReviewRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Review V1 Admin Pedagogy Review Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/pipeline/jobs`
**Purpose:** Pipeline Jobs Status
**Tags:** `admin-pipeline`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`pipeline_jobs_status`](../../../mathbank-rest/src/mathbank_rest/routers/admin.py#L123)
**Operation ID:** `pipeline_jobs_status_v1_admin_pipeline_jobs_get`
**Parameters:** `competition` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Competition"}`); `paper` (query, optional; `{"anyOf":[{"maxLength":100,"type":"string"},{"type":"null"}],"title":"Paper"}`); `limit` (query, optional; default `50`; `{"default":50,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Pipeline Jobs Status V1 Admin Pipeline Jobs Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/pipeline/runs`
**Purpose:** Pipeline Runs
**Tags:** `admin-pipeline`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`pipeline_runs`](../../../mathbank-rest/src/mathbank_rest/routers/admin.py#L115)
**Operation ID:** `pipeline_runs_v1_admin_pipeline_runs_get`
**Parameters:** `limit` (query, optional; default `20`; `{"default":20,"maximum":200,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Pipeline Runs V1 Admin Pipeline Runs Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/recovery-plans`
**Purpose:** Admin Recovery Plans
**Tags:** `step-runtime`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`admin_recovery_plans`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L346)
**Operation ID:** `admin_recovery_plans_v1_admin_recovery_plans_get`
**Parameters:** `student_id` (query, optional; `{"anyOf":[{"format":"uuid","type":"string"},{"type":"null"}],"title":"Student Id"}`); `status` (query, optional; `{"anyOf":[{"enum":["ACTIVE","SUSPENDED","COMPLETED","EXHAUSTED","ABORTED","SUPERSEDED"],"type":"string"},{"type":"null"}],"title":"Status"}`); `limit` (query, optional; default `100`; `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Admin Recovery Plans V1 Admin Recovery Plans Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/recovery-plans/{plan_id}`
**Purpose:** Admin Recovery Plan
**Tags:** `step-runtime`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`admin_recovery_plan`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L354)
**Operation ID:** `admin_recovery_plan_v1_admin_recovery_plans__plan_id__get`
**Parameters:** `plan_id` (path, required; `{"format":"uuid","title":"Plan Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Admin Recovery Plan V1 Admin Recovery Plans  Plan Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/students/{student_id}/knowledge-gaps`
**Purpose:** Admin Student Gaps
**Tags:** `step-runtime`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`admin_student_gaps`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L244)
**Operation ID:** `admin_student_gaps_v1_admin_students__student_id__knowledge_gaps_get`
**Parameters:** `student_id` (path, required; `{"format":"uuid","title":"Student Id","type":"string"}`); `status` (query, optional; `{"anyOf":[{"enum":["UNRESOLVED","CONFIRMED","REJECTED","RESOLVED"],"type":"string"},{"type":"null"}],"title":"Status"}`); `limit` (query, optional; default `100`; `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Admin Student Gaps V1 Admin Students  Student Id  Knowledge Gaps Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/taxonomy/{kind}`
**Purpose:** List Entities
**Tags:** `admin-taxonomy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`list_entities`](../../../mathbank-rest/src/mathbank_rest/routers/admin_taxonomy.py#L66)
**Operation ID:** `list_entities_v1_admin_taxonomy__kind__get`
**Parameters:** `kind` (path, required; `{"enum":["concepts","techniques","skills","misconceptions"],"title":"Kind","type":"string"}`); `q` (query, optional; default ``; `{"default":"","maxLength":200,"title":"Q","type":"string"}`); `status` (query, optional; default `ALL`; `{"default":"ALL","enum":["ACTIVE","INACTIVE","ALL"],"title":"Status","type":"string"}`); `review_status` (query, optional; default `ALL`; `{"default":"ALL","description":"For skills/misconceptions only; one of PENDING|REVIEWED|REJECTED (skills) or PENDING_REVIEW|APPROVED|REJECTED (misconceptions), or ALL.","title":"Review Status","type":"string"}`; For skills/misconceptions only; one of PENDING\|REVIEWED\|REJECTED (skills) or PENDING_REVIEW\|APPROVED\|REJECTED (misconceptions), or ALL.); `limit` (query, optional; default `50`; `{"default":50,"maximum":200,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response List Entities V1 Admin Taxonomy  Kind  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/taxonomy/{kind}/{code}`
**Purpose:** Get Entity
**Tags:** `admin-taxonomy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_entity`](../../../mathbank-rest/src/mathbank_rest/routers/admin_taxonomy.py#L83)
**Operation ID:** `get_entity_v1_admin_taxonomy__kind___code__get`
**Parameters:** `kind` (path, required; `{"enum":["concepts","techniques","skills","misconceptions"],"title":"Kind","type":"string"}`); `code` (path, required; `{"title":"Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Entity V1 Admin Taxonomy  Kind   Code  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PATCH `/v1/admin/taxonomy/{kind}/{code}`
**Purpose:** Update Entity
**Tags:** `admin-taxonomy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`update_entity`](../../../mathbank-rest/src/mathbank_rest/routers/admin_taxonomy.py#L89)
**Operation ID:** `update_entity_v1_admin_taxonomy__kind___code__patch`
**Parameters:** `kind` (path, required; `{"enum":["concepts","techniques","skills","misconceptions"],"title":"Kind","type":"string"}`); `code` (path, required; `{"title":"Code","type":"string"}`)
**Request body:** required; `application/json`: `UpdateEntityRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Update Entity V1 Admin Taxonomy  Kind   Code  Patch","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/taxonomy/{kind}/{code}/aliases`
**Purpose:** List Aliases
**Tags:** `admin-taxonomy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`list_aliases`](../../../mathbank-rest/src/mathbank_rest/routers/admin_taxonomy.py#L110)
**Operation ID:** `list_aliases_v1_admin_taxonomy__kind___code__aliases_get`
**Parameters:** `kind` (path, required; `{"enum":["concepts","techniques","skills","misconceptions"],"title":"Kind","type":"string"}`); `code` (path, required; `{"title":"Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Aliases V1 Admin Taxonomy  Kind   Code  Aliases Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/taxonomy/{kind}/{code}/aliases`
**Purpose:** Add Alias
**Tags:** `admin-taxonomy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`add_alias`](../../../mathbank-rest/src/mathbank_rest/routers/admin_taxonomy.py#L116)
**Operation ID:** `add_alias_v1_admin_taxonomy__kind___code__aliases_post`
**Parameters:** `kind` (path, required; `{"enum":["concepts","techniques","skills","misconceptions"],"title":"Kind","type":"string"}`); `code` (path, required; `{"title":"Code","type":"string"}`)
**Request body:** required; `application/json`: `AliasRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Add Alias V1 Admin Taxonomy  Kind   Code  Aliases Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### DELETE `/v1/admin/taxonomy/{kind}/{code}/aliases/{alias_id}`
**Purpose:** Remove Alias
**Tags:** `admin-taxonomy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`remove_alias`](../../../mathbank-rest/src/mathbank_rest/routers/admin_taxonomy.py#L122)
**Operation ID:** `remove_alias_v1_admin_taxonomy__kind___code__aliases__alias_id__delete`
**Parameters:** `kind` (path, required; `{"enum":["concepts","techniques","skills","misconceptions"],"title":"Kind","type":"string"}`); `code` (path, required; `{"title":"Code","type":"string"}`); `alias_id` (path, required; `{"title":"Alias Id","type":"string"}`); `actor` (query, required; `{"maxLength":200,"minLength":1,"title":"Actor","type":"string"}`)
**Documented responses:** `204` Successful Response: no response schema declared; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/taxonomy/{kind}/{code}/deactivate`
**Purpose:** Deactivate Entity
**Tags:** `admin-taxonomy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`deactivate_entity`](../../../mathbank-rest/src/mathbank_rest/routers/admin_taxonomy.py#L98)
**Operation ID:** `deactivate_entity_v1_admin_taxonomy__kind___code__deactivate_post`
**Parameters:** `kind` (path, required; `{"enum":["concepts","techniques","skills","misconceptions"],"title":"Kind","type":"string"}`); `code` (path, required; `{"title":"Code","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__admin_taxonomy__ActorRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Deactivate Entity V1 Admin Taxonomy  Kind   Code  Deactivate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/taxonomy/{kind}/{code}/reactivate`
**Purpose:** Reactivate Entity
**Tags:** `admin-taxonomy`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`reactivate_entity`](../../../mathbank-rest/src/mathbank_rest/routers/admin_taxonomy.py#L104)
**Operation ID:** `reactivate_entity_v1_admin_taxonomy__kind___code__reactivate_post`
**Parameters:** `kind` (path, required; `{"enum":["concepts","techniques","skills","misconceptions"],"title":"Kind","type":"string"}`); `code` (path, required; `{"title":"Code","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__admin_taxonomy__ActorRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Reactivate Entity V1 Admin Taxonomy  Kind   Code  Reactivate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/textbooks/coverage`
**Purpose:** Coverage
**Tags:** `admin-textbooks`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`coverage`](../../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L28)
**Operation ID:** `coverage_v1_admin_textbooks_coverage_get`
**Parameters:** `book` (query, optional; default `PRASOLOV_PGV1`; `{"default":"PRASOLOV_PGV1","maxLength":64,"pattern":"^[A-Z0-9_]+$","title":"Book","type":"string"}`); `graph` (query, optional; default `True`; `{"default":true,"description":"Also count Neo4j nodes/edges","title":"Graph","type":"boolean"}`; Also count Neo4j nodes/edges)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Coverage V1 Admin Textbooks Coverage Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/textbooks/diagrams/{source_diagram_id}/image`
**Purpose:** Diagram Image
**Tags:** `admin-textbooks`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`diagram_image`](../../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L83)
**Operation ID:** `diagram_image_v1_admin_textbooks_diagrams__source_diagram_id__image_get`
**Parameters:** `source_diagram_id` (path, required; `{"maxLength":100,"pattern":"^[A-Za-z0-9_.-]+$","title":"Source Diagram Id","type":"string"}`); `book` (query, optional; default `PRASOLOV_PGV1`; `{"default":"PRASOLOV_PGV1","maxLength":64,"pattern":"^[A-Z0-9_]+$","title":"Book","type":"string"}`)
**Documented responses:** `200` Successful Response: no response schema declared; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/textbooks/learning-items`
**Purpose:** Learning Items
**Tags:** `admin-textbooks`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`learning_items`](../../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L56)
**Operation ID:** `learning_items_v1_admin_textbooks_learning_items_get`
**Parameters:** `book` (query, optional; default `PRASOLOV_PGV1`; `{"default":"PRASOLOV_PGV1","maxLength":64,"pattern":"^[A-Z0-9_]+$","title":"Book","type":"string"}`); `transformation_type` (query, optional; `{"anyOf":[{"maxLength":64,"type":"string"},{"type":"null"}],"title":"Transformation Type"}`); `chapter` (query, optional; `{"anyOf":[{"maximum":99,"minimum":1,"type":"integer"},{"type":"null"}],"title":"Chapter"}`); `q` (query, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Q"}`); `limit` (query, optional; default `50`; `{"default":50,"maximum":200,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Learning Items V1 Admin Textbooks Learning Items Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/textbooks/problems`
**Purpose:** Problems
**Tags:** `admin-textbooks`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`problems`](../../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L34)
**Operation ID:** `problems_v1_admin_textbooks_problems_get`
**Parameters:** `book` (query, optional; default `PRASOLOV_PGV1`; `{"default":"PRASOLOV_PGV1","maxLength":64,"pattern":"^[A-Z0-9_]+$","title":"Book","type":"string"}`); `chapter` (query, optional; `{"anyOf":[{"maximum":99,"minimum":1,"type":"integer"},{"type":"null"}],"title":"Chapter"}`); `q` (query, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Q"}`); `node` (query, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Node"}`); `has_diagram` (query, optional; `{"anyOf":[{"type":"boolean"},{"type":"null"}],"title":"Has Diagram"}`); `has_solution` (query, optional; `{"anyOf":[{"type":"boolean"},{"type":"null"}],"title":"Has Solution"}`); `limit` (query, optional; default `50`; `{"default":50,"maximum":200,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Problems V1 Admin Textbooks Problems Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/textbooks/problems/{code}`
**Purpose:** Problem
**Tags:** `admin-textbooks`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`problem`](../../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L44)
**Operation ID:** `problem_v1_admin_textbooks_problems__code__get`
**Parameters:** `code` (path, required; `{"title":"Code","type":"string"}`); `graph` (query, optional; default `True`; `{"default":true,"title":"Graph","type":"boolean"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Problem V1 Admin Textbooks Problems  Code  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/textbooks/taxonomy`
**Purpose:** Taxonomy
**Tags:** `admin-textbooks`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`taxonomy`](../../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L65)
**Operation ID:** `taxonomy_v1_admin_textbooks_taxonomy_get`
**Parameters:** `book` (query, optional; default `PRASOLOV_PGV1`; `{"default":"PRASOLOV_PGV1","maxLength":64,"pattern":"^[A-Z0-9_]+$","title":"Book","type":"string"}`); `node_type` (query, optional; `{"anyOf":[{"enum":["DOMAIN","CONCEPT","SUBCONCEPT","SKILL","TECHNIQUE"],"type":"string"},{"type":"null"}],"title":"Node Type"}`); `q` (query, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Q"}`); `limit` (query, optional; default `100`; `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Taxonomy V1 Admin Textbooks Taxonomy Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/textbooks/taxonomy/{node_id}`
**Purpose:** Taxonomy Node
**Tags:** `admin-textbooks`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`taxonomy_node`](../../../mathbank-rest/src/mathbank_rest/routers/admin_textbooks.py#L72)
**Operation ID:** `taxonomy_node_v1_admin_textbooks_taxonomy__node_id__get`
**Parameters:** `node_id` (path, required; `{"title":"Node Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Taxonomy Node V1 Admin Textbooks Taxonomy  Node Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/theorems`
**Purpose:** List Admin Theorems
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`list_admin_theorems`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L134)
**Operation ID:** `list_admin_theorems_v1_admin_theorems_get`
**Parameters:** `q` (query, optional; default ``; `{"default":"","maxLength":200,"title":"Q","type":"string"}`); `kind` (query, optional; default ``; `{"default":"","title":"Kind","type":"string"}`); `field` (query, optional; default ``; `{"default":"","title":"Field","type":"string"}`); `review_status` (query, optional; default `ALL`; `{"default":"ALL","title":"Review Status","type":"string"}`); `limit` (query, optional; default `50`; `{"default":50,"maximum":200,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response List Admin Theorems V1 Admin Theorems Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/theorems`
**Purpose:** Create Admin Theorem
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_admin_theorem`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L149)
**Operation ID:** `create_admin_theorem_v1_admin_theorems_post`
**Request body:** required; `application/json`: `CreateTheorem` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Admin Theorem V1 Admin Theorems Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/theorems/search`
**Purpose:** Search Admin Theorems
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`search_admin_theorems`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L154)
**Operation ID:** `search_admin_theorems_v1_admin_theorems_search_get`
**Parameters:** `q` (query, required; `{"maxLength":200,"minLength":1,"title":"Q","type":"string"}`); `field` (query, optional; default ``; `{"default":"","title":"Field","type":"string"}`); `kind` (query, optional; default ``; `{"default":"","title":"Kind","type":"string"}`); `limit` (query, optional; default `10`; `{"default":10,"maximum":50,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Search Admin Theorems V1 Admin Theorems Search Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/theorems/sources/{theorem_source_id}/approve`
**Purpose:** Approve Theorem Source
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`approve_theorem_source`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L233)
**Operation ID:** `approve_theorem_source_v1_admin_theorems_sources__theorem_source_id__approve_post`
**Parameters:** `theorem_source_id` (path, required; `{"title":"Theorem Source Id","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__theorems__ActorRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Approve Theorem Source V1 Admin Theorems Sources  Theorem Source Id  Approve Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/theorems/{slug}`
**Purpose:** Get Admin Theorem
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_admin_theorem`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L166)
**Operation ID:** `get_admin_theorem_v1_admin_theorems__slug__get`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Admin Theorem V1 Admin Theorems  Slug  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PATCH `/v1/admin/theorems/{slug}`
**Purpose:** Update Admin Theorem
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`update_admin_theorem`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L171)
**Operation ID:** `update_admin_theorem_v1_admin_theorems__slug__patch`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`)
**Request body:** required; `application/json`: `UpdateTheorem` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Update Admin Theorem V1 Admin Theorems  Slug  Patch","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/theorems/{slug}/approve`
**Purpose:** Approve Admin Theorem
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`approve_admin_theorem`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L176)
**Operation ID:** `approve_admin_theorem_v1_admin_theorems__slug__approve_post`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__theorems__ActorRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Approve Admin Theorem V1 Admin Theorems  Slug  Approve Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/theorems/{slug}/assets`
**Purpose:** Create Theorem Asset
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_theorem_asset`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L238)
**Operation ID:** `create_theorem_asset_v1_admin_theorems__slug__assets_post`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`)
**Request body:** required; `application/json`: `CreateAsset` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Theorem Asset V1 Admin Theorems  Slug  Assets Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/theorems/{slug}/prerequisites`
**Purpose:** Get Theorem Prerequisites Admin
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_theorem_prerequisites_admin`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L202)
**Operation ID:** `get_theorem_prerequisites_admin_v1_admin_theorems__slug__prerequisites_get`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`); `max_depth` (query, optional; default `4`; `{"default":4,"maximum":10,"minimum":1,"title":"Max Depth","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Theorem Prerequisites Admin V1 Admin Theorems  Slug  Prerequisites Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/theorems/{slug}/reject`
**Purpose:** Reject Admin Theorem
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`reject_admin_theorem`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L181)
**Operation ID:** `reject_admin_theorem_v1_admin_theorems__slug__reject_post`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__theorems__ActorRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Reject Admin Theorem V1 Admin Theorems  Slug  Reject Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/theorems/{slug}/relations`
**Purpose:** Get Theorem Relations
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_theorem_relations`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L197)
**Operation ID:** `get_theorem_relations_v1_admin_theorems__slug__relations_get`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Theorem Relations V1 Admin Theorems  Slug  Relations Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/theorems/{slug}/relations`
**Purpose:** Create Theorem Relation
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_theorem_relation`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L188)
**Operation ID:** `create_theorem_relation_v1_admin_theorems__slug__relations_post`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`)
**Request body:** required; `application/json`: `CreateRelation` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Theorem Relation V1 Admin Theorems  Slug  Relations Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/theorems/{slug}/sources`
**Purpose:** Create Theorem Source
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_theorem_source`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L225)
**Operation ID:** `create_theorem_source_v1_admin_theorems__slug__sources_post`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`)
**Request body:** required; `application/json`: `CreateSource` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Theorem Source V1 Admin Theorems  Slug  Sources Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/theorems/{slug}/taxonomy-links`
**Purpose:** Link Theorem Taxonomy
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`link_theorem_taxonomy`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L217)
**Operation ID:** `link_theorem_taxonomy_v1_admin_theorems__slug__taxonomy_links_post`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`)
**Request body:** required; `application/json`: `CreateTaxonomyLink` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Link Theorem Taxonomy V1 Admin Theorems  Slug  Taxonomy Links Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/theorems/{slug}/techniques`
**Purpose:** Link Theorem Technique
**Tags:** `admin-theorems`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`link_theorem_technique`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L209)
**Operation ID:** `link_theorem_technique_v1_admin_theorems__slug__techniques_post`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`)
**Request body:** required; `application/json`: `CreateTechniqueLink` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Link Theorem Technique V1 Admin Theorems  Slug  Techniques Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/admin/tutoring-routes`
**Purpose:** Drafts
**Tags:** `tutoring-routes`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`drafts`](../../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py#L63)
**Operation ID:** `drafts_v1_admin_tutoring_routes_get`
**Parameters:** `limit` (query, optional; default `25`; `{"default":25,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/tutoring-routes/refresh-graph`
**Purpose:** Refresh Graph
**Tags:** `tutoring-routes`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`refresh_graph`](../../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py#L157)
**Operation ID:** `refresh_graph_v1_admin_tutoring_routes_refresh_graph_post`
**Documented responses:** `200` Successful Response: `application/json` unspecified

### GET `/v1/admin/tutoring-routes/{release_id}`
**Purpose:** Preview
**Tags:** `tutoring-routes`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`preview`](../../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py#L88)
**Operation ID:** `preview_v1_admin_tutoring_routes__release_id__get`
**Parameters:** `release_id` (path, required; `{"format":"uuid","title":"Release Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/tutoring-routes/{release_id}/edit`
**Purpose:** Edit
**Tags:** `tutoring-routes`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`edit`](../../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py#L150)
**Operation ID:** `edit_v1_admin_tutoring_routes__release_id__edit_post`
**Parameters:** `release_id` (path, required; `{"format":"uuid","title":"Release Id","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__tutoring_routes__EditRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/tutoring-routes/{release_id}/publish`
**Purpose:** Publish
**Tags:** `tutoring-routes`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`publish`](../../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py#L143)
**Operation ID:** `publish_v1_admin_tutoring_routes__release_id__publish_post`
**Parameters:** `release_id` (path, required; `{"format":"uuid","title":"Release Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/admin/tutoring-routes/{release_id}/review`
**Purpose:** Review
**Tags:** `tutoring-routes`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`review`](../../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py#L136)
**Operation ID:** `review_v1_admin_tutoring_routes__release_id__review_post`
**Parameters:** `release_id` (path, required; `{"format":"uuid","title":"Release Id","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__tutoring_routes__ReviewRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/analytics/weak-concepts`
**Purpose:** Get Weak Concepts
**Tags:** `analytics`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_weak_concepts`](../../../mathbank-rest/src/mathbank_rest/routers/v1.py#L127)
**Operation ID:** `get_weak_concepts_v1_analytics_weak_concepts_get`
**Parameters:** `min_students` (query, optional; default `1`; `{"default":1,"minimum":1,"title":"Min Students","type":"integer"}`); `limit` (query, optional; default `20`; `{"default":20,"maximum":100,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Weak Concepts V1 Analytics Weak Concepts Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/artifacts/bundles/{bundle_id}`
**Purpose:** Get Bundle
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_bundle`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L198)
**Operation ID:** `get_bundle_v1_artifacts_bundles__bundle_id__get`
**Parameters:** `bundle_id` (path, required; `{"format":"uuid","title":"Bundle Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Bundle V1 Artifacts Bundles  Bundle Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/artifacts/bundles/{bundle_id}/assets`
**Purpose:** Assets
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`assets`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L203)
**Operation ID:** `assets_v1_artifacts_bundles__bundle_id__assets_get`
**Parameters:** `bundle_id` (path, required; `{"format":"uuid","title":"Bundle Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Assets V1 Artifacts Bundles  Bundle Id  Assets Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/artifacts/bundles/{bundle_id}/assets/{asset_id}/content`
**Purpose:** Asset Content
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`asset_content`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L213)
**Operation ID:** `asset_content_v1_artifacts_bundles__bundle_id__assets__asset_id__content_get`
**Parameters:** `bundle_id` (path, required; `{"format":"uuid","title":"Bundle Id","type":"string"}`); `asset_id` (path, required; `{"format":"uuid","title":"Asset Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/artifacts/bundles/{bundle_id}/frames`
**Purpose:** Frames
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`frames`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L228)
**Operation ID:** `frames_v1_artifacts_bundles__bundle_id__frames_get`
**Parameters:** `bundle_id` (path, required; `{"format":"uuid","title":"Bundle Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Frames V1 Artifacts Bundles  Bundle Id  Frames Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/artifacts/bundles/{bundle_id}/frames/{ordinal}/content`
**Purpose:** Frame Content
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`frame_content`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L233)
**Operation ID:** `frame_content_v1_artifacts_bundles__bundle_id__frames__ordinal__content_get`
**Parameters:** `bundle_id` (path, required; `{"format":"uuid","title":"Bundle Id","type":"string"}`); `ordinal` (path, required; `{"maximum":127,"minimum":0,"title":"Ordinal","type":"integer"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/bundles/{bundle_id}/index`
**Purpose:** Index
**Tags:** `artifacts`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`index`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L264)
**Operation ID:** `index_v1_artifacts_bundles__bundle_id__index_post`
**Parameters:** `bundle_id` (path, required; `{"format":"uuid","title":"Bundle Id","type":"string"}`)
**Request body:** required; `application/json`: `IndexBody` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Index V1 Artifacts Bundles  Bundle Id  Index Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/bundles/{bundle_id}/publish`
**Purpose:** Publish
**Tags:** `artifacts`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`publish`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L259)
**Operation ID:** `publish_v1_artifacts_bundles__bundle_id__publish_post`
**Parameters:** `bundle_id` (path, required; `{"format":"uuid","title":"Bundle Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Publish V1 Artifacts Bundles  Bundle Id  Publish Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/bundles/{bundle_id}/similar`
**Purpose:** Similar
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`similar`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L279)
**Operation ID:** `similar_v1_artifacts_bundles__bundle_id__similar_post`
**Parameters:** `bundle_id` (path, required; `{"format":"uuid","title":"Bundle Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `SearchBody` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Similar V1 Artifacts Bundles  Bundle Id  Similar Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/bundles/{bundle_id}/validate`
**Purpose:** Validate Bundle
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`validate_bundle`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L254)
**Operation ID:** `validate_bundle_v1_artifacts_bundles__bundle_id__validate_post`
**Parameters:** `bundle_id` (path, required; `{"format":"uuid","title":"Bundle Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Validate Bundle V1 Artifacts Bundles  Bundle Id  Validate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/artifacts/embedding-profile`
**Purpose:** Embedding Profile
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`embedding_profile`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L143)
**Operation ID:** `embedding_profile_v1_artifacts_embedding_profile_get`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Embedding Profile V1 Artifacts Embedding Profile Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/geometry-preview`
**Purpose:** Geometry Preview
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`geometry_preview`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L114)
**Operation ID:** `geometry_preview_v1_artifacts_geometry_preview_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `GeometryPreview` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Geometry Preview V1 Artifacts Geometry Preview Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/geometry-preview/content`
**Purpose:** Geometry Preview Content
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`geometry_preview_content`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L127)
**Operation ID:** `geometry_preview_content_v1_artifacts_geometry_preview_content_post`
**Parameters:** `frame` (query, optional; `{"anyOf":[{"maximum":127,"minimum":0,"type":"integer"},{"type":"null"}],"title":"Frame"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `GeometryPreview` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/preview`
**Purpose:** Preview
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`preview`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L36)
**Operation ID:** `preview_v1_artifacts_preview_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `ArtifactPlan` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Preview V1 Artifacts Preview Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/preview/content`
**Purpose:** Preview Content
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`preview_content`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L53)
**Operation ID:** `preview_content_v1_artifacts_preview_content_post`
**Parameters:** `frame` (query, optional; `{"anyOf":[{"maximum":127,"minimum":0,"type":"integer"},{"type":"null"}],"title":"Frame"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `ArtifactPlan` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/requests`
**Purpose:** Request Artifact
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`request_artifact`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L173)
**Operation ID:** `request_artifact_v1_artifacts_requests_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `ArtifactPlan` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Request Artifact V1 Artifacts Requests Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/artifacts/requests/{request_id}`
**Purpose:** Get Request
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_request`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L178)
**Operation ID:** `get_request_v1_artifacts_requests__request_id__get`
**Parameters:** `request_id` (path, required; `{"format":"uuid","title":"Request Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Request V1 Artifacts Requests  Request Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/requests/{request_id}/generate`
**Purpose:** Generate
**Tags:** `artifacts`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`generate`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L183)
**Operation ID:** `generate_v1_artifacts_requests__request_id__generate_post`
**Parameters:** `request_id` (path, required; `{"format":"uuid","title":"Request Id","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__artifact_runtime__GenerateBody` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Generate V1 Artifacts Requests  Request Id  Generate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/search`
**Purpose:** Search
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`search`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L269)
**Operation ID:** `search_v1_artifacts_search_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `SearchBody` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Search V1 Artifacts Search Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/search/semantic`
**Purpose:** Semantic Search
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`semantic_search`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L274)
**Operation ID:** `semantic_search_v1_artifacts_search_semantic_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `SearchBody` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Semantic Search V1 Artifacts Search Semantic Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/artifacts/validate`
**Purpose:** Validate
**Tags:** `artifacts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`validate`](../../../mathbank-rest/src/mathbank_rest/routers/artifacts.py#L249)
**Operation ID:** `validate_v1_artifacts_validate_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `ArtifactPlan` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Validate V1 Artifacts Validate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempt-media/attempts/{aid}/steps`
**Purpose:** Approved Steps
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`approved_steps`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L496)
**Operation ID:** `approved_steps_v1_attempt_media_attempts__aid__steps_get`
**Parameters:** `aid` (path, required; `{"format":"uuid","title":"Aid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempt-media/attempts/{aid}/steps/{step_id}/assessment`
**Purpose:** Approved Assessment
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`approved_assessment`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L514)
**Operation ID:** `approved_assessment_v1_attempt_media_attempts__aid__steps__step_id__assessment_get`
**Parameters:** `aid` (path, required; `{"format":"uuid","title":"Aid","type":"string"}`); `step_id` (path, required; `{"format":"uuid","title":"Step Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempt-media/attempts/{aid}/steps/{step_id}/visual`
**Purpose:** Approved Assessment
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`approved_assessment`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L514)
**Operation ID:** `approved_assessment_v1_attempt_media_attempts__aid__steps__step_id__visual_get`
**Parameters:** `aid` (path, required; `{"format":"uuid","title":"Aid","type":"string"}`); `step_id` (path, required; `{"format":"uuid","title":"Step Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempt-media/submissions`
**Purpose:** Listing
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`listing`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L66)
**Operation ID:** `listing_v1_attempt_media_submissions_get`
**Parameters:** `limit` (query, optional; default `25`; `{"default":25,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempt-media/submissions`
**Purpose:** Create
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`create`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L40)
**Operation ID:** `create_v1_attempt_media_submissions_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `SubmissionIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempt-media/submissions/{sid}`
**Purpose:** Get
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L92)
**Operation ID:** `get_v1_attempt_media_submissions__sid__get`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempt-media/submissions/{sid}/analyse`
**Purpose:** Analyse
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`analyse`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L541)
**Operation ID:** `analyse_v1_attempt_media_submissions__sid__analyse_post`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `Versioned` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempt-media/submissions/{sid}/approve`
**Purpose:** Approve
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`approve`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L411)
**Operation ID:** `approve_v1_attempt_media_submissions__sid__approve_post`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `Versioned` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempt-media/submissions/{sid}/assets`
**Purpose:** Upload
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`upload`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L145)
**Operation ID:** `upload_v1_attempt_media_submissions__sid__assets_post`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `expected_version` (query, required; `{"minimum":1,"title":"Expected Version","type":"integer"}`); `filename` (query, optional; default `upload`; `{"default":"upload","maxLength":200,"title":"Filename","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `201` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### DELETE `/v1/attempt-media/submissions/{sid}/assets/{aid}`
**Purpose:** Purge
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`purge`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L617)
**Operation ID:** `purge_v1_attempt_media_submissions__sid__assets__aid__delete`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `aid` (path, required; `{"format":"uuid","title":"Aid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempt-media/submissions/{sid}/assets/{aid}/content`
**Purpose:** Content
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`content`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L210)
**Operation ID:** `content_v1_attempt_media_submissions__sid__assets__aid__content_get`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `aid` (path, required; `{"format":"uuid","title":"Aid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempt-media/submissions/{sid}/assets/{aid}/pages/{page}`
**Purpose:** Pdf Page
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`pdf_page`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L224)
**Operation ID:** `pdf_page_v1_attempt_media_submissions__sid__assets__aid__pages__page__get`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `aid` (path, required; `{"format":"uuid","title":"Aid","type":"string"}`); `page` (path, required; `{"title":"Page","type":"integer"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempt-media/submissions/{sid}/events`
**Purpose:** Events
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`events`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L97)
**Operation ID:** `events_v1_attempt_media_submissions__sid__events_get`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `after_sequence` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"After Sequence","type":"integer"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempt-media/submissions/{sid}/override`
**Purpose:** Override
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`override`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L595)
**Operation ID:** `override_v1_attempt_media_submissions__sid__override_post`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `Override` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempt-media/submissions/{sid}/process`
**Purpose:** Process
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`process`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L267)
**Operation ID:** `process_v1_attempt_media_submissions__sid__process_post`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `Versioned` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempt-media/submissions/{sid}/transcription`
**Purpose:** Transcription
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`transcription`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L381)
**Operation ID:** `transcription_v1_attempt_media_submissions__sid__transcription_get`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PUT `/v1/attempt-media/submissions/{sid}/transcription`
**Purpose:** Replace
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`replace`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L386)
**Operation ID:** `replace_v1_attempt_media_submissions__sid__transcription_put`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `Transcript` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempt-media/submissions/{sid}/transcription/merge`
**Purpose:** Merge
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`merge`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L420)
**Operation ID:** `merge_v1_attempt_media_submissions__sid__transcription_merge_post`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `Merge` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempt-media/submissions/{sid}/transcription/split`
**Purpose:** Split
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`split`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L458)
**Operation ID:** `split_v1_attempt_media_submissions__sid__transcription_split_post`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `Split` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PATCH `/v1/attempt-media/submissions/{sid}/transcription/steps/{step_id}`
**Purpose:** Patch
**Tags:** `multimodal-attempts`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`patch`](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L398)
**Operation ID:** `patch_v1_attempt_media_submissions__sid__transcription_steps__step_id__patch`
**Parameters:** `sid` (path, required; `{"format":"uuid","title":"Sid","type":"string"}`); `step_id` (path, required; `{"format":"uuid","title":"Step Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `StepPatch` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempts/{attempt_id}`
**Purpose:** Get Runtime
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`get_runtime`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L102)
**Operation ID:** `get_runtime_v1_attempts__attempt_id__get`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Runtime V1 Attempts  Attempt Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempts/{attempt_id}/diagnoses`
**Purpose:** List Diagnoses
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`list_diagnoses`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L232)
**Operation ID:** `list_diagnoses_v1_attempts__attempt_id__diagnoses_get`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Diagnoses V1 Attempts  Attempt Id  Diagnoses Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempts/{attempt_id}/recovery-plans`
**Purpose:** List Recovery Plans
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`list_recovery_plans`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L288)
**Operation ID:** `list_recovery_plans_v1_attempts__attempt_id__recovery_plans_get`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Recovery Plans V1 Attempts  Attempt Id  Recovery Plans Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempts/{attempt_id}/recovery-plans`
**Purpose:** Create Recovery Plan
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`create_recovery_plan`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L276)
**Operation ID:** `create_recovery_plan_v1_attempts__attempt_id__recovery_plans_post`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`); `Idempotency-Key` (header, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}`)
**Request body:** required; `application/json`: `RecoveryCreateRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Recovery Plan V1 Attempts  Attempt Id  Recovery Plans Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempts/{attempt_id}/runtime`
**Purpose:** Get Runtime
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`get_runtime`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L102)
**Operation ID:** `get_runtime_v1_attempts__attempt_id__runtime_get`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Runtime V1 Attempts  Attempt Id  Runtime Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempts/{attempt_id}/steps/{step_id}/diagnose`
**Purpose:** Diagnose Step
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Operation ID:** `diagnose_step_v1_attempts__attempt_id__steps__step_id__diagnose_post`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`); `step_id` (path, required; `{"title":"Step Id","type":"string"}`)
**Request body:** optional; `application/json`: `{"anyOf":[{"$ref":"#/components/schemas/DiagnoseRequest"},{"type":"null"}],"title":"Body"}`
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Diagnose Step V1 Attempts  Attempt Id  Steps  Step Id  Diagnose Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempts/{attempt_id}/steps/{step_id}/hint`
**Purpose:** Request Hint
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Operation ID:** `request_hint_v1_attempts__attempt_id__steps__step_id__hint_post`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`); `step_id` (path, required; `{"title":"Step Id","type":"string"}`); `Idempotency-Key` (header, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}`)
**Request body:** required; `application/json`: `VersionedRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Request Hint V1 Attempts  Attempt Id  Steps  Step Id  Hint Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/attempts/{attempt_id}/steps/{step_id}/hints`
**Purpose:** List Hints
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Operation ID:** `list_hints_v1_attempts__attempt_id__steps__step_id__hints_get`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`); `step_id` (path, required; `{"title":"Step Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response List Hints V1 Attempts  Attempt Id  Steps  Step Id  Hints Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempts/{attempt_id}/steps/{step_id}/outcome`
**Purpose:** Record Step Outcome
**Tags:** `step-runtime`
**OpenAPI security:** `APIKeyHeader`
**Operation ID:** `record_step_outcome_v1_attempts__attempt_id__steps__step_id__outcome_post`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`); `step_id` (path, required; `{"title":"Step Id","type":"string"}`); `Idempotency-Key` (header, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}`)
**Request body:** required; `application/json`: `StepOutcomeRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Record Step Outcome V1 Attempts  Attempt Id  Steps  Step Id  Outcome Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempts/{attempt_id}/steps/{step_id}/responses`
**Purpose:** Submit Step Response
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Operation ID:** `submit_step_response_v1_attempts__attempt_id__steps__step_id__responses_post`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`); `step_id` (path, required; `{"title":"Step Id","type":"string"}`); `Idempotency-Key` (header, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}`)
**Request body:** required; `application/json`: `StepResponseRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Submit Step Response V1 Attempts  Attempt Id  Steps  Step Id  Responses Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/attempts/{attempt_id}/submit`
**Purpose:** Submit Attempt
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`submit_attempt`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L360)
**Operation ID:** `submit_attempt_v1_attempts__attempt_id__submit_post`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`); `Idempotency-Key` (header, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}`)
**Request body:** required; `application/json`: `VersionedRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Submit Attempt V1 Attempts  Attempt Id  Submit Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/authoring/chat/sessions`
**Purpose:** Chat Create
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`chat_create`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L268)
**Operation ID:** `chat_create_v1_authoring_chat_sessions_post`
**Parameters:** `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `ChatIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Chat Create V1 Authoring Chat Sessions Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/authoring/chat/sessions/{chat_id}`
**Purpose:** Chat Get
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`chat_get`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L273)
**Operation ID:** `chat_get_v1_authoring_chat_sessions__chat_id__get`
**Parameters:** `chat_id` (path, required; `{"title":"Chat Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Chat Get V1 Authoring Chat Sessions  Chat Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/authoring/chat/sessions/{chat_id}/messages`
**Purpose:** Chat Message
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`chat_message`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L278)
**Operation ID:** `chat_message_v1_authoring_chat_sessions__chat_id__messages_post`
**Parameters:** `chat_id` (path, required; `{"title":"Chat Id","type":"string"}`)
**Request body:** required; `application/json`: `MessageIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Chat Message V1 Authoring Chat Sessions  Chat Id  Messages Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/authoring/chat/sessions/{chat_id}/proposed-patches`
**Purpose:** Chat Patches
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`chat_patches`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L283)
**Operation ID:** `chat_patches_v1_authoring_chat_sessions__chat_id__proposed_patches_get`
**Parameters:** `chat_id` (path, required; `{"title":"Chat Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Chat Patches V1 Authoring Chat Sessions  Chat Id  Proposed Patches Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/authoring/chat/sessions/{chat_id}/proposed-patches/{patch_id}/apply`
**Purpose:** Chat Patch Decide
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`chat_patch_decide`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L288)
**Operation ID:** `chat_patch_decide_v1_authoring_chat_sessions__chat_id__proposed_patches__patch_id__apply_post`
**Parameters:** `chat_id` (path, required; `{"title":"Chat Id","type":"string"}`); `patch_id` (path, required; `{"title":"Patch Id","type":"string"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `PatchDecision` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Chat Patch Decide V1 Authoring Chat Sessions  Chat Id  Proposed Patches  Patch Id  Apply Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/authoring/presentation-plans`
**Purpose:** Plans
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`plans`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L223)
**Operation ID:** `plans_v1_authoring_presentation_plans_get`
**Parameters:** `limit` (query, optional; default `100`; `{"default":100,"maximum":500,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Plans V1 Authoring Presentation Plans Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/authoring/presentation-plans`
**Purpose:** Create Plan
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`create_plan`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L228)
**Operation ID:** `create_plan_v1_authoring_presentation_plans_post`
**Parameters:** `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `PlanIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Plan V1 Authoring Presentation Plans Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/authoring/presentation-plans/{plan_id}`
**Purpose:** Plan
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`plan`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L233)
**Operation ID:** `plan_v1_authoring_presentation_plans__plan_id__get`
**Parameters:** `plan_id` (path, required; `{"title":"Plan Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Plan V1 Authoring Presentation Plans  Plan Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/authoring/presentation-plans/{plan_id}/approve`
**Purpose:** Plan Approve
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`plan_approve`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L253)
**Operation ID:** `plan_approve_v1_authoring_presentation_plans__plan_id__approve_post`
**Parameters:** `plan_id` (path, required; `{"title":"Plan Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Plan Approve V1 Authoring Presentation Plans  Plan Id  Approve Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/authoring/presentation-plans/{plan_id}/new-version`
**Purpose:** Plan New Version
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`plan_new_version`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L263)
**Operation ID:** `plan_new_version_v1_authoring_presentation_plans__plan_id__new_version_post`
**Parameters:** `plan_id` (path, required; `{"title":"Plan Id","type":"string"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Plan New Version V1 Authoring Presentation Plans  Plan Id  New Version Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/authoring/presentation-plans/{plan_id}/publish`
**Purpose:** Plan Publish
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`plan_publish`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L258)
**Operation ID:** `plan_publish_v1_authoring_presentation_plans__plan_id__publish_post`
**Parameters:** `plan_id` (path, required; `{"title":"Plan Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Plan Publish V1 Authoring Presentation Plans  Plan Id  Publish Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PATCH `/v1/authoring/presentation-plans/{plan_id}/timing`
**Purpose:** Plan Timing
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`plan_timing`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L243)
**Operation ID:** `plan_timing_v1_authoring_presentation_plans__plan_id__timing_patch`
**Parameters:** `plan_id` (path, required; `{"title":"Plan Id","type":"string"}`)
**Request body:** required; `application/json`: `TimingIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Plan Timing V1 Authoring Presentation Plans  Plan Id  Timing Patch","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PUT `/v1/authoring/presentation-plans/{plan_id}/topics`
**Purpose:** Plan Topics
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`plan_topics`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L238)
**Operation ID:** `plan_topics_v1_authoring_presentation_plans__plan_id__topics_put`
**Parameters:** `plan_id` (path, required; `{"title":"Plan Id","type":"string"}`)
**Request body:** required; `application/json`: `TopicsIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Plan Topics V1 Authoring Presentation Plans  Plan Id  Topics Put","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/authoring/presentation-plans/{plan_id}/validate`
**Purpose:** Plan Validate
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`plan_validate`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L248)
**Operation ID:** `plan_validate_v1_authoring_presentation_plans__plan_id__validate_post`
**Parameters:** `plan_id` (path, required; `{"title":"Plan Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Plan Validate V1 Authoring Presentation Plans  Plan Id  Validate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/competitions`
**Purpose:** Get Competitions
**Tags:** `corpus`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_competitions`](../../../mathbank-rest/src/mathbank_rest/routers/v1.py#L51)
**Operation ID:** `get_competitions_v1_competitions_get`
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Competitions V1 Competitions Get","type":"array"}`

### GET `/v1/concepts`
**Purpose:** Get Concepts
**Tags:** `taxonomy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_concepts`](../../../mathbank-rest/src/mathbank_rest/routers/v1.py#L85)
**Operation ID:** `get_concepts_v1_concepts_get`
**Parameters:** `domain` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Domain"}`); `limit` (query, optional; default `50`; `{"default":50,"maximum":200,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Concepts V1 Concepts Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/concepts/{slug}/neighbors`
**Purpose:** Get Concept Neighbors
**Tags:** `taxonomy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_concept_neighbors`](../../../mathbank-rest/src/mathbank_rest/routers/v1.py#L101)
**Operation ID:** `get_concept_neighbors_v1_concepts__slug__neighbors_get`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Concept Neighbors V1 Concepts  Slug  Neighbors Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/concepts/{slug}/problems`
**Purpose:** Get Concept Problems
**Tags:** `taxonomy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_concept_problems`](../../../mathbank-rest/src/mathbank_rest/routers/v1.py#L94)
**Operation ID:** `get_concept_problems_v1_concepts__slug__problems_get`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`); `limit` (query, optional; default `25`; `{"default":25,"maximum":200,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Concept Problems V1 Concepts  Slug  Problems Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/corpus/coverage`
**Purpose:** Get Corpus Coverage
**Tags:** `analytics`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_corpus_coverage`](../../../mathbank-rest/src/mathbank_rest/routers/v1.py#L122)
**Operation ID:** `get_corpus_coverage_v1_corpus_coverage_get`
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Corpus Coverage V1 Corpus Coverage Get","type":"array"}`

### POST `/v1/geometry-scenes`
**Purpose:** Create
**Tags:** `geometry-scenes`, `geometry-scenes`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`create`](../../../mathbank-geometry-engine/src/geometry_scene/api.py#L75)
**Operation ID:** `create_v1_geometry_scenes_post`
**Parameters:** `Idempotency-Key` (header, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `SceneInput` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/geometry-scenes/debug/runs`
**Purpose:** List Runs
**Tags:** `geometry-scenes`, `geometry-scenes`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`list_runs`](../../../mathbank-rest/src/mathbank_rest/routers/geometry_scenes.py#L87)
**Operation ID:** `list_runs_v1_geometry_scenes_debug_runs_get`
**Parameters:** `owner` (query, required; `{"maxLength":200,"minLength":1,"title":"Owner","type":"string"}`); `limit` (query, optional; default `50`; `{"default":50,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/geometry-scenes/debug/runs/{run_id}`
**Purpose:** Read Run
**Tags:** `geometry-scenes`, `geometry-scenes`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`read_run`](../../../mathbank-rest/src/mathbank_rest/routers/geometry_scenes.py#L82)
**Operation ID:** `read_run_v1_geometry_scenes_debug_runs__run_id__get`
**Parameters:** `run_id` (path, required; `{"maxLength":200,"minLength":1,"title":"Run Id","type":"string"}`); `owner` (query, required; `{"maxLength":200,"minLength":1,"title":"Owner","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/geometry-scenes/debug/runs/{run_id}/review`
**Purpose:** Review Run
**Tags:** `geometry-scenes`, `geometry-scenes`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`review_run`](../../../mathbank-rest/src/mathbank_rest/routers/geometry_scenes.py#L94)
**Operation ID:** `review_run_v1_geometry_scenes_debug_runs__run_id__review_post`
**Parameters:** `run_id` (path, required; `{"maxLength":200,"minLength":1,"title":"Run Id","type":"string"}`); `owner` (query, required; `{"maxLength":200,"minLength":1,"title":"Owner","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `Review` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/geometry-scenes/interpret`
**Purpose:** Interpret Scene
**Tags:** `geometry-agent`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`interpret_scene`](../../../mathbank-rest/src/mathbank_rest/routers/geometry_interpretation.py#L19)
**Operation ID:** `interpret_scene_v1_geometry_scenes_interpret_post`
**Parameters:** `idempotency-key` (header, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `GeometryRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/geometry-scenes/{scene_id}`
**Purpose:** Current
**Tags:** `geometry-scenes`, `geometry-scenes`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`current`](../../../mathbank-geometry-engine/src/geometry_scene/api.py#L85)
**Operation ID:** `current_v1_geometry_scenes__scene_id__get`
**Parameters:** `scene_id` (path, required; `{"pattern":"^[A-Za-z][A-Za-z0-9_]{0,63}$","title":"Scene Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/geometry-scenes/{scene_id}/deltas`
**Purpose:** Delta
**Tags:** `geometry-scenes`, `geometry-scenes`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`delta`](../../../mathbank-geometry-engine/src/geometry_scene/api.py#L80)
**Operation ID:** `delta_v1_geometry_scenes__scene_id__deltas_post`
**Parameters:** `scene_id` (path, required; `{"pattern":"^[A-Za-z][A-Za-z0-9_]{0,63}$","title":"Scene Id","type":"string"}`); `Idempotency-Key` (header, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `StateDelta` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/geometry-scenes/{scene_id}/frames`
**Purpose:** Frames
**Tags:** `geometry-scenes`, `geometry-scenes`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`frames`](../../../mathbank-geometry-engine/src/geometry_scene/api.py#L110)
**Operation ID:** `frames_v1_geometry_scenes__scene_id__frames_get`
**Parameters:** `scene_id` (path, required; `{"pattern":"^[A-Za-z][A-Za-z0-9_]{0,63}$","title":"Scene Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/geometry-scenes/{scene_id}/versions/{version}`
**Purpose:** Read
**Tags:** `geometry-scenes`, `geometry-scenes`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`read`](../../../mathbank-geometry-engine/src/geometry_scene/api.py#L89)
**Operation ID:** `read_v1_geometry_scenes__scene_id__versions__version__get`
**Parameters:** `scene_id` (path, required; `{"pattern":"^[A-Za-z][A-Za-z0-9_]{0,63}$","title":"Scene Id","type":"string"}`); `version` (path, required; `{"minimum":0,"title":"Version","type":"integer"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/geometry-scenes/{scene_id}/versions/{version}/render`
**Purpose:** Render Version
**Tags:** `geometry-scenes`, `geometry-scenes`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`render_version`](../../../mathbank-geometry-engine/src/geometry_scene/api.py#L93)
**Operation ID:** `render_version_v1_geometry_scenes__scene_id__versions__version__render_get`
**Parameters:** `scene_id` (path, required; `{"pattern":"^[A-Za-z][A-Za-z0-9_]{0,63}$","title":"Scene Id","type":"string"}`); `version` (path, required; `{"minimum":0,"title":"Version","type":"integer"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/geometry-scenes/{scene_id}/versions/{version}/validate`
**Purpose:** Validate
**Tags:** `geometry-scenes`, `geometry-scenes`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`validate`](../../../mathbank-geometry-engine/src/geometry_scene/api.py#L106)
**Operation ID:** `validate_v1_geometry_scenes__scene_id__versions__version__validate_post`
**Parameters:** `scene_id` (path, required; `{"pattern":"^[A-Za-z][A-Za-z0-9_]{0,63}$","title":"Scene Id","type":"string"}`); `version` (path, required; `{"minimum":0,"title":"Version","type":"integer"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/instructor/live/{sid}/commands`
**Purpose:** Instructor Nl
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`instructor_nl`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L340)
**Operation ID:** `instructor_nl_v1_instructor_live__sid__commands_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `NLIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Instructor Nl V1 Instructor Live  Sid  Commands Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/instructor/live/{sid}/handoff`
**Purpose:** Handoff
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`handoff`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L360)
**Operation ID:** `handoff_v1_instructor_live__sid__handoff_get`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `scope` (query, optional; default `SESSION`; `{"default":"SESSION","enum":["SESSION","STUDENT","GROUP"],"title":"Scope","type":"string"}`); `scope_id` (query, optional; default `*`; `{"default":"*","title":"Scope Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Handoff V1 Instructor Live  Sid  Handoff Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/instructor/live/{sid}/overrides`
**Purpose:** Override
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`override`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L334)
**Operation ID:** `override_v1_instructor_live__sid__overrides_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `OverrideIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Override V1 Instructor Live  Sid  Overrides Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/instructor/live/{sid}/recommendations`
**Purpose:** Recommendations
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`recommendations`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L346)
**Operation ID:** `recommendations_v1_instructor_live__sid__recommendations_get`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `status` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Status"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Recommendations V1 Instructor Live  Sid  Recommendations Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/instructor/live/{sid}/recommendations/{rid}`
**Purpose:** Decide
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`decide`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L351)
**Operation ID:** `decide_v1_instructor_live__sid__recommendations__rid__post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `rid` (path, required; `{"title":"Rid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `DecisionIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Decide V1 Instructor Live  Sid  Recommendations  Rid  Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/learner/agent-sessions`
**Purpose:** My Agent Sessions
**Tags:** `agent-sessions`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`my_agent_sessions`](../../../mathbank-rest/src/mathbank_rest/routers/agent_sessions.py#L43)
**Operation ID:** `my_agent_sessions_v1_learner_agent_sessions_get`
**Parameters:** `limit` (query, optional; default `50`; `{"default":50,"maximum":200,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response My Agent Sessions V1 Learner Agent Sessions Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/learner/agent-sessions`
**Purpose:** Link Agent Session
**Tags:** `agent-sessions`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`link_agent_session`](../../../mathbank-rest/src/mathbank_rest/routers/agent_sessions.py#L36)
**Operation ID:** `link_agent_session_v1_learner_agent_sessions_post`
**Request body:** required; `application/json`: `AgentSessionLinkRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Link Agent Session V1 Learner Agent Sessions Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/learner/agent-sessions/{agent_session_id}/transcript`
**Purpose:** My Agent Transcript
**Tags:** `agent-sessions`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`my_agent_transcript`](../../../mathbank-rest/src/mathbank_rest/routers/agent_sessions.py#L50)
**Operation ID:** `my_agent_transcript_v1_learner_agent_sessions__agent_session_id__transcript_get`
**Parameters:** `agent_session_id` (path, required; `{"title":"Agent Session Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response My Agent Transcript V1 Learner Agent Sessions  Agent Session Id  Transcript Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/learner/attempts`
**Purpose:** Get Attempts
**Tags:** `learner`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`get_attempts`](../../../mathbank-rest/src/mathbank_rest/routers/learner.py#L137)
**Operation ID:** `get_attempts_v1_learner_attempts_get`
**Parameters:** `limit` (query, optional; default `50`; `{"default":50,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Attempts V1 Learner Attempts Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/learner/attempts`
**Purpose:** Submit Attempt
**Tags:** `learner`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`submit_attempt`](../../../mathbank-rest/src/mathbank_rest/routers/learner.py#L114)
**Operation ID:** `submit_attempt_v1_learner_attempts_post`
**Request body:** required; `application/json`: `AttemptRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Submit Attempt V1 Learner Attempts Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/learner/login`
**Purpose:** Login
**Tags:** `learner`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`login`](../../../mathbank-rest/src/mathbank_rest/routers/learner.py#L90)
**Operation ID:** `login_v1_learner_login_post`
**Request body:** required; `application/json`: `LoginRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `AuthResponse` (in [OpenAPI snapshot](openapi.json)); `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/learner/mastery`
**Purpose:** Get Mastery Summary
**Tags:** `learner`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`get_mastery_summary`](../../../mathbank-rest/src/mathbank_rest/routers/learner.py#L144)
**Operation ID:** `get_mastery_summary_v1_learner_mastery_get`
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Mastery Summary V1 Learner Mastery Get","type":"object"}`

### GET `/v1/learner/mastery/improvement-plan`
**Purpose:** Get Improvement Plan
**Tags:** `learner`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`get_improvement_plan`](../../../mathbank-rest/src/mathbank_rest/routers/learner.py#L149)
**Operation ID:** `get_improvement_plan_v1_learner_mastery_improvement_plan_get`
**Parameters:** `max_focus_areas` (query, optional; default `5`; `{"default":5,"title":"Max Focus Areas","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Improvement Plan V1 Learner Mastery Improvement Plan Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/learner/me`
**Purpose:** Get Me
**Tags:** `learner`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`get_me`](../../../mathbank-rest/src/mathbank_rest/routers/learner.py#L106)
**Operation ID:** `get_me_v1_learner_me_get`
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Me V1 Learner Me Get","type":"object"}`

### GET `/v1/learner/practice-progress`
**Purpose:** Get Practice Progress
**Tags:** `learner`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`get_practice_progress`](../../../mathbank-rest/src/mathbank_rest/routers/learner.py#L62)
**Operation ID:** `get_practice_progress_v1_learner_practice_progress_get`
**Documented responses:** `200` Successful Response: `application/json` `PracticeProgressResponse` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/learner/register`
**Purpose:** Register
**Tags:** `learner`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`register`](../../../mathbank-rest/src/mathbank_rest/routers/learner.py#L74)
**Operation ID:** `register_v1_learner_register_post`
**Request body:** required; `application/json`: `RegisterRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `AuthResponse` (in [OpenAPI snapshot](openapi.json)); `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/live/sessions`
**Purpose:** List Sessions
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`list_sessions`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L202)
**Operation ID:** `list_sessions_v1_live_sessions_get`
**Parameters:** `limit` (query, optional; default `50`; `{"default":50,"maximum":200,"title":"Limit","type":"integer"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response List Sessions V1 Live Sessions Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/live/sessions`
**Purpose:** Create Session
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`create_session`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L197)
**Operation ID:** `create_session_v1_live_sessions_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `SessionIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Create Session V1 Live Sessions Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/live/sessions/join`
**Purpose:** Join
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`join`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L207)
**Operation ID:** `join_v1_live_sessions_join_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `JoinIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Join V1 Live Sessions Join Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/live/sessions/{sid}/activities`
**Purpose:** Open Activity
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`open_activity`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L268)
**Operation ID:** `open_activity_v1_live_sessions__sid__activities_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `ActivityIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Open Activity V1 Live Sessions  Sid  Activities Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/live/sessions/{sid}/activities/{aid}/aggregate`
**Purpose:** Activity Aggregate
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`activity_aggregate`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L280)
**Operation ID:** `activity_aggregate_v1_live_sessions__sid__activities__aid__aggregate_get`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `aid` (path, required; `{"title":"Aid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Activity Aggregate V1 Live Sessions  Sid  Activities  Aid  Aggregate Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/live/sessions/{sid}/activities/{aid}/close`
**Purpose:** Close Activity
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`close_activity`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L290)
**Operation ID:** `close_activity_v1_live_sessions__sid__activities__aid__close_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `aid` (path, required; `{"title":"Aid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `VersionedIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Close Activity V1 Live Sessions  Sid  Activities  Aid  Close Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/live/sessions/{sid}/activities/{aid}/responses`
**Purpose:** Respond
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`respond`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L274)
**Operation ID:** `respond_v1_live_sessions__sid__activities__aid__responses_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `aid` (path, required; `{"title":"Aid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `ResponseIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Respond V1 Live Sessions  Sid  Activities  Aid  Responses Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/live/sessions/{sid}/activities/{aid}/reveal`
**Purpose:** Reveal Activity
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`reveal_activity`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L296)
**Operation ID:** `reveal_activity_v1_live_sessions__sid__activities__aid__reveal_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `aid` (path, required; `{"title":"Aid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `VersionedIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Reveal Activity V1 Live Sessions  Sid  Activities  Aid  Reveal Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/live/sessions/{sid}/commands`
**Purpose:** Command
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`command`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L232)
**Operation ID:** `command_v1_live_sessions__sid__commands_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `CommandIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Command V1 Live Sessions  Sid  Commands Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/live/sessions/{sid}/events`
**Purpose:** Events
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`events`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L222)
**Operation ID:** `events_v1_live_sessions__sid__events_get`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `after_sequence` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"After Sequence","type":"integer"}`); `limit` (query, optional; default `500`; `{"default":500,"maximum":1000,"minimum":1,"title":"Limit","type":"integer"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Events V1 Live Sessions  Sid  Events Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/live/sessions/{sid}/pause`
**Purpose:** Pause
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`pause`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L244)
**Operation ID:** `pause_v1_live_sessions__sid__pause_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `VersionedIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Pause V1 Live Sessions  Sid  Pause Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/live/sessions/{sid}/resume`
**Purpose:** Resume
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`resume`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L249)
**Operation ID:** `resume_v1_live_sessions__sid__resume_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `VersionedIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Resume V1 Live Sessions  Sid  Resume Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/live/sessions/{sid}/state`
**Purpose:** State
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`state`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L214)
**Operation ID:** `state_v1_live_sessions__sid__state_get`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response State V1 Live Sessions  Sid  State Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/live/sessions/{sid}/time`
**Purpose:** Time State
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`time_state`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L254)
**Operation ID:** `time_state_v1_live_sessions__sid__time_get`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Time State V1 Live Sessions  Sid  Time Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/live/sessions/{sid}/transition`
**Purpose:** Transition
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`transition`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L238)
**Operation ID:** `transition_v1_live_sessions__sid__transition_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `TransitionIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Transition V1 Live Sessions  Sid  Transition Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/live/sessions/{sid}/widgets`
**Purpose:** Show Widget
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`show_widget`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L304)
**Operation ID:** `show_widget_v1_live_sessions__sid__widgets_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `WidgetIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Show Widget V1 Live Sessions  Sid  Widgets Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### DELETE `/v1/live/sessions/{sid}/widgets/{wid}`
**Purpose:** Hide Widget
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`hide_widget`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L325)
**Operation ID:** `hide_widget_v1_live_sessions__sid__widgets__wid__delete`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `wid` (path, required; `{"title":"Wid","type":"string"}`); `expected_session_version` (query, optional; `{"anyOf":[{"minimum":1,"type":"integer"},{"type":"null"}],"title":"Expected Session Version"}`); `client_command_id` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Client Command Id"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Hide Widget V1 Live Sessions  Sid  Widgets  Wid  Delete","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PATCH `/v1/live/sessions/{sid}/widgets/{wid}/state`
**Purpose:** Widget State
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`widget_state`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L319)
**Operation ID:** `widget_state_v1_live_sessions__sid__widgets__wid__state_patch`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `wid` (path, required; `{"title":"Wid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `WidgetStateIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Widget State V1 Live Sessions  Sid  Widgets  Wid  State Patch","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/micro-courses`
**Purpose:** List Student Courses
**Tags:** `micro-courses`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`list_student_courses`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L453)
**Operation ID:** `list_student_courses_v1_micro_courses_get`
**Parameters:** `limit` (query, optional; default `50`; `{"default":50,"maximum":200,"minimum":1,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Student Courses V1 Micro Courses Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/micro-courses/enrollments/{enrollment_id}`
**Purpose:** Get Enrollment
**Tags:** `micro-courses`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`get_enrollment`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L505)
**Operation ID:** `get_enrollment_v1_micro_courses_enrollments__enrollment_id__get`
**Parameters:** `enrollment_id` (path, required; `{"format":"uuid","title":"Enrollment Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Enrollment V1 Micro Courses Enrollments  Enrollment Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/micro-courses/enrollments/{enrollment_id}/activity-responses`
**Purpose:** Submit Activity Response Endpoint
**Tags:** `micro-courses`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`submit_activity_response_endpoint`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L537)
**Operation ID:** `submit_activity_response_endpoint_v1_micro_courses_enrollments__enrollment_id__activity_responses_post`
**Parameters:** `enrollment_id` (path, required; `{"format":"uuid","title":"Enrollment Id","type":"string"}`)
**Request body:** required; `application/json`: `SubmitActivityResponse` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Submit Activity Response Endpoint V1 Micro Courses Enrollments  Enrollment Id  Activity Responses Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/micro-courses/enrollments/{enrollment_id}/advance`
**Purpose:** Advance Enrollment
**Tags:** `micro-courses`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`advance_enrollment`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L512)
**Operation ID:** `advance_enrollment_v1_micro_courses_enrollments__enrollment_id__advance_post`
**Parameters:** `enrollment_id` (path, required; `{"format":"uuid","title":"Enrollment Id","type":"string"}`)
**Request body:** required; `application/json`: `AdvanceEnrollment` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Advance Enrollment V1 Micro Courses Enrollments  Enrollment Id  Advance Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/micro-courses/enrollments/{enrollment_id}/interaction-events`
**Purpose:** Record Interaction Event Endpoint
**Tags:** `micro-courses`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`record_interaction_event_endpoint`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L550)
**Operation ID:** `record_interaction_event_endpoint_v1_micro_courses_enrollments__enrollment_id__interaction_events_post`
**Parameters:** `enrollment_id` (path, required; `{"format":"uuid","title":"Enrollment Id","type":"string"}`)
**Request body:** required; `application/json`: `RecordInteractionEvent` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Record Interaction Event Endpoint V1 Micro Courses Enrollments  Enrollment Id  Interaction Events Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/micro-courses/enrollments/{enrollment_id}/item-help`
**Purpose:** Get Item Help
**Tags:** `micro-courses`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`get_item_help`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L567)
**Operation ID:** `get_item_help_v1_micro_courses_enrollments__enrollment_id__item_help_post`
**Parameters:** `enrollment_id` (path, required; `{"format":"uuid","title":"Enrollment Id","type":"string"}`)
**Request body:** required; `application/json`: `ItemHelpRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Item Help V1 Micro Courses Enrollments  Enrollment Id  Item Help Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/micro-courses/enrollments/{enrollment_id}/responses`
**Purpose:** Submit Response
**Tags:** `micro-courses`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`submit_response`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L524)
**Operation ID:** `submit_response_v1_micro_courses_enrollments__enrollment_id__responses_post`
**Parameters:** `enrollment_id` (path, required; `{"format":"uuid","title":"Enrollment Id","type":"string"}`)
**Request body:** required; `application/json`: `SubmitLearningItemResponse` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Submit Response V1 Micro Courses Enrollments  Enrollment Id  Responses Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/micro-courses/{canonical_code}`
**Purpose:** Get Student Course
**Tags:** `micro-courses`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_student_course`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L461)
**Operation ID:** `get_student_course_v1_micro_courses__canonical_code__get`
**Parameters:** `canonical_code` (path, required; `{"title":"Canonical Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Student Course V1 Micro Courses  Canonical Code  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/micro-courses/{canonical_code}/assets/{asset_id}/content`
**Purpose:** Get Student Asset
**Tags:** `micro-courses`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_student_asset`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L466)
**Operation ID:** `get_student_asset_v1_micro_courses__canonical_code__assets__asset_id__content_get`
**Parameters:** `canonical_code` (path, required; `{"title":"Canonical Code","type":"string"}`); `asset_id` (path, required; `{"format":"uuid","title":"Asset Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/micro-courses/{canonical_code}/enroll`
**Purpose:** Enroll In Course
**Tags:** `micro-courses`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`enroll_in_course`](../../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py#L496)
**Operation ID:** `enroll_in_course_v1_micro_courses__canonical_code__enroll_post`
**Parameters:** `canonical_code` (path, required; `{"title":"Canonical Code","type":"string"}`)
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Enroll In Course V1 Micro Courses  Canonical Code  Enroll Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/notifications/me`
**Purpose:** List My Notifications
**Tags:** `notifications`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`list_my_notifications`](../../../mathbank-rest/src/mathbank_rest/routers/notifications.py#L25)
**Operation ID:** `list_my_notifications_v1_notifications_me_get`
**Parameters:** `limit` (query, optional; default `25`; `{"default":25,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/notifications/{notification_id}/read`
**Purpose:** Mark Notification Read
**Tags:** `notifications`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`mark_notification_read`](../../../mathbank-rest/src/mathbank_rest/routers/notifications.py#L40)
**Operation ID:** `mark_notification_read_v1_notifications__notification_id__read_post`
**Parameters:** `notification_id` (path, required; `{"format":"uuid","title":"Notification Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/problem-images/{image_id}`
**Purpose:** Get Problem Image
**Tags:** `step-runtime`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_problem_image`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L443)
**Operation ID:** `get_problem_image_v1_problem_images__image_id__get`
**Parameters:** `image_id` (path, required; `{"format":"uuid","title":"Image Id","type":"string"}`)
**Documented responses:** `200` Successful Response: no response schema declared; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/problems`
**Purpose:** Get Problems
**Tags:** `corpus`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_problems`](../../../mathbank-rest/src/mathbank_rest/routers/v1.py#L56)
**Operation ID:** `get_problems_v1_problems_get`
**Parameters:** `competition` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Competition"}`); `year_min` (query, optional; `{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Year Min"}`); `year_max` (query, optional; `{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Year Max"}`); `concept` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Concept"}`); `technique` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Technique"}`); `limit` (query, optional; default `25`; `{"default":25,"maximum":200,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Problems V1 Problems Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/problems/by-code/{canonical_code}`
**Purpose:** Get Problem
**Tags:** `corpus`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_problem`](../../../mathbank-rest/src/mathbank_rest/routers/v1.py#L77)
**Operation ID:** `get_problem_v1_problems_by_code__canonical_code__get`
**Parameters:** `canonical_code` (path, required; `{"title":"Canonical Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Problem V1 Problems By Code  Canonical Code  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/problems/by-code/{code}/diagrams`
**Purpose:** List Problem Diagrams
**Tags:** `step-runtime`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`list_problem_diagrams`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L383)
**Operation ID:** `list_problem_diagrams_v1_problems_by_code__code__diagrams_get`
**Parameters:** `code` (path, required; `{"title":"Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Problem Diagrams V1 Problems By Code  Code  Diagrams Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/problems/by-code/{code}/source`
**Purpose:** Get Problem Source
**Tags:** `step-runtime`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_problem_source`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L390)
**Operation ID:** `get_problem_source_v1_problems_by_code__code__source_get`
**Parameters:** `code` (path, required; `{"title":"Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"anyOf":[{"additionalProperties":true,"type":"object"},{"type":"null"}],"title":"Response Get Problem Source V1 Problems By Code  Code  Source Get"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/problems/by-code/{code}/source-highlight`
**Purpose:** Get Problem Source Highlight
**Tags:** `step-runtime`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_problem_source_highlight`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L410)
**Operation ID:** `get_problem_source_highlight_v1_problems_by_code__code__source_highlight_get`
**Parameters:** `code` (path, required; `{"title":"Code","type":"string"}`); `page` (query, optional; `{"anyOf":[{"minimum":1,"type":"integer"},{"type":"null"}],"title":"Page"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/problems/by-code/{code}/source-marked-pdf`
**Purpose:** Get Problem Source Marked Pdf
**Tags:** `step-runtime`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_problem_source_marked_pdf`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L428)
**Operation ID:** `get_problem_source_marked_pdf_v1_problems_by_code__code__source_marked_pdf_get`
**Parameters:** `code` (path, required; `{"title":"Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/problems/by-code/{code}/source-pdf`
**Purpose:** Get Problem Source Pdf
**Tags:** `step-runtime`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_problem_source_pdf`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L399)
**Operation ID:** `get_problem_source_pdf_v1_problems_by_code__code__source_pdf_get`
**Parameters:** `code` (path, required; `{"title":"Code","type":"string"}`)
**Documented responses:** `200` Successful Response: no response schema declared; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz-integration/difficulty-distribution`
**Purpose:** Difficulty Distribution
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`difficulty_distribution`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L295)
**Operation ID:** `difficulty_distribution_v1_quiz_integration_difficulty_distribution_get`
**Parameters:** `concept_slug` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Concept Slug"}`); `technique_slug` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Technique Slug"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Difficulty Distribution V1 Quiz Integration Difficulty Distribution Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/quiz-integration/papers`
**Purpose:** Import Paper
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`import_paper`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L134)
**Operation ID:** `import_paper_v1_quiz_integration_papers_post`
**Request body:** required; `application/json`: `ImportPaperRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Import Paper V1 Quiz Integration Papers Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz-integration/papers/mine`
**Purpose:** List My Papers
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`list_my_papers`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L195)
**Operation ID:** `list_my_papers_v1_quiz_integration_papers_mine_get`
**Parameters:** `student_id` (query, required; `{"format":"uuid","title":"Student Id","type":"string"}`); `limit` (query, optional; default `20`; `{"default":20,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List My Papers V1 Quiz Integration Papers Mine Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/quiz-integration/papers/start`
**Purpose:** Start Paper
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`start_paper`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L149)
**Operation ID:** `start_paper_v1_quiz_integration_papers_start_post`
**Request body:** required; `application/json`: `StartPaperRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Start Paper V1 Quiz Integration Papers Start Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz-integration/papers/{quiz_id}`
**Purpose:** Get Paper
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_paper`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L204)
**Operation ID:** `get_paper_v1_quiz_integration_papers__quiz_id__get`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`); `student_id` (query, required; `{"format":"uuid","title":"Student Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Paper V1 Quiz Integration Papers  Quiz Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz-integration/papers/{quiz_id}/diagnosis`
**Purpose:** Get Diagnosis
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_diagnosis`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L329)
**Operation ID:** `get_diagnosis_v1_quiz_integration_papers__quiz_id__diagnosis_get`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`); `student_id` (query, required; `{"format":"uuid","title":"Student Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Diagnosis V1 Quiz Integration Papers  Quiz Id  Diagnosis Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/quiz-integration/papers/{quiz_id}/diagnosis`
**Purpose:** Write Diagnosis
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`write_diagnosis`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L276)
**Operation ID:** `write_diagnosis_v1_quiz_integration_papers__quiz_id__diagnosis_post`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`)
**Request body:** required; `application/json`: `WriteDiagnosisRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Write Diagnosis V1 Quiz Integration Papers  Quiz Id  Diagnosis Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz-integration/papers/{quiz_id}/diagnosis-input`
**Purpose:** Diagnosis Input
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`diagnosis_input`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L261)
**Operation ID:** `diagnosis_input_v1_quiz_integration_papers__quiz_id__diagnosis_input_get`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`); `student_id` (query, required; `{"format":"uuid","title":"Student Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Diagnosis Input V1 Quiz Integration Papers  Quiz Id  Diagnosis Input Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz-integration/papers/{quiz_id}/events`
**Purpose:** Get Events
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_events`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L418)
**Operation ID:** `get_events_v1_quiz_integration_papers__quiz_id__events_get`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`); `student_id` (query, required; `{"format":"uuid","title":"Student Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Events V1 Quiz Integration Papers  Quiz Id  Events Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/quiz-integration/papers/{quiz_id}/finalize`
**Purpose:** Finalize Paper
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`finalize_paper`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L168)
**Operation ID:** `finalize_paper_v1_quiz_integration_papers__quiz_id__finalize_post`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`)
**Request body:** required; `application/json`: `FinalizePaperRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Finalize Paper V1 Quiz Integration Papers  Quiz Id  Finalize Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz-integration/papers/{quiz_id}/generation-events`
**Purpose:** Get Generation Events
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`get_generation_events`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L190)
**Operation ID:** `get_generation_events_v1_quiz_integration_papers__quiz_id__generation_events_get`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`); `student_id` (query, required; `{"format":"uuid","title":"Student Id","type":"string"}`); `since_ordinal` (query, optional; default `0`; `{"default":0,"title":"Since Ordinal","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Generation Events V1 Quiz Integration Papers  Quiz Id  Generation Events Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/quiz-integration/papers/{quiz_id}/generation-events`
**Purpose:** Post Generation Event
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`post_generation_event`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L178)
**Operation ID:** `post_generation_event_v1_quiz_integration_papers__quiz_id__generation_events_post`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`)
**Request body:** required; `application/json`: `GenerationEventRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Post Generation Event V1 Quiz Integration Papers  Quiz Id  Generation Events Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### PUT `/v1/quiz-integration/papers/{quiz_id}/progress`
**Purpose:** Save Exam Progress
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`save_exam_progress`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L218)
**Operation ID:** `save_exam_progress_v1_quiz_integration_papers__quiz_id__progress_put`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`)
**Request body:** required; `application/json`: `SaveExamProgressRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Save Exam Progress V1 Quiz Integration Papers  Quiz Id  Progress Put","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/quiz-integration/papers/{quiz_id}/questions/{question_id}/events`
**Purpose:** Log Event
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`log_event`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L409)
**Operation ID:** `log_event_v1_quiz_integration_papers__quiz_id__questions__question_id__events_post`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`); `question_id` (path, required; `{"format":"uuid","title":"Question Id","type":"string"}`)
**Request body:** required; `application/json`: `LogEventRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Log Event V1 Quiz Integration Papers  Quiz Id  Questions  Question Id  Events Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/quiz-integration/papers/{quiz_id}/questions/{question_id}/respond`
**Purpose:** Respond
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`respond`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L238)
**Operation ID:** `respond_v1_quiz_integration_papers__quiz_id__questions__question_id__respond_post`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`); `question_id` (path, required; `{"format":"uuid","title":"Question Id","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__exam_integration__RespondRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Respond V1 Quiz Integration Papers  Quiz Id  Questions  Question Id  Respond Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz-integration/papers/{quiz_id}/review`
**Purpose:** Review
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`review`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L251)
**Operation ID:** `review_v1_quiz_integration_papers__quiz_id__review_get`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`); `student_id` (query, required; `{"format":"uuid","title":"Student Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Review V1 Quiz Integration Papers  Quiz Id  Review Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/quiz-integration/papers/{quiz_id}/submit`
**Purpose:** Submit Exam
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`submit_exam`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L256)
**Operation ID:** `submit_exam_v1_quiz_integration_papers__quiz_id__submit_post`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`); `student_id` (query, required; `{"format":"uuid","title":"Student Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Submit Exam V1 Quiz Integration Papers  Quiz Id  Submit Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz-integration/students/by-cognito-sub/{cognito_sub}`
**Purpose:** Student By Cognito Sub
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`student_by_cognito_sub`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L362)
**Operation ID:** `student_by_cognito_sub_v1_quiz_integration_students_by_cognito_sub__cognito_sub__get`
**Parameters:** `cognito_sub` (path, required; `{"title":"Cognito Sub","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Student By Cognito Sub V1 Quiz Integration Students By Cognito Sub  Cognito Sub  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/quiz-integration/students/onboard`
**Purpose:** Onboard Student
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`onboard_student`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L348)
**Operation ID:** `onboard_student_v1_quiz_integration_students_onboard_post`
**Request body:** required; `application/json`: `OnboardStudentRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Onboard Student V1 Quiz Integration Students Onboard Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz-integration/students/{student_id}`
**Purpose:** Student Profile
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`student_profile`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L370)
**Operation ID:** `student_profile_v1_quiz_integration_students__student_id__get`
**Parameters:** `student_id` (path, required; `{"format":"uuid","title":"Student Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Student Profile V1 Quiz Integration Students  Student Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz-integration/students/{student_id}/mastery-summary`
**Purpose:** Mastery Summary
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`mastery_summary`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L286)
**Operation ID:** `mastery_summary_v1_quiz_integration_students__student_id__mastery_summary_get`
**Parameters:** `student_id` (path, required; `{"format":"uuid","title":"Student Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Mastery Summary V1 Quiz Integration Students  Student Id  Mastery Summary Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/quiz-integration/students/{student_id}/mint-session-token`
**Purpose:** Mint Session Token
**Tags:** `quiz-integration`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`mint_session_token`](../../../mathbank-rest/src/mathbank_rest/routers/exam_integration.py#L378)
**Operation ID:** `mint_session_token_v1_quiz_integration_students__student_id__mint_session_token_post`
**Parameters:** `student_id` (path, required; `{"format":"uuid","title":"Student Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Mint Session Token V1 Quiz Integration Students  Student Id  Mint Session Token Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/quiz/generate`
**Purpose:** Generate
**Tags:** `quiz`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`generate`](../../../mathbank-rest/src/mathbank_rest/routers/quiz_runtime.py#L51)
**Operation ID:** `generate_v1_quiz_generate_post`
**Request body:** required; `application/json`: `GenerateQuizRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Generate V1 Quiz Generate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz/mine`
**Purpose:** Mine
**Tags:** `quiz`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`mine`](../../../mathbank-rest/src/mathbank_rest/routers/quiz_runtime.py#L65)
**Operation ID:** `mine_v1_quiz_mine_get`
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Mine V1 Quiz Mine Get","type":"array"}`

### GET `/v1/quiz/{quiz_id}`
**Purpose:** Get Quiz
**Tags:** `quiz`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`get_quiz`](../../../mathbank-rest/src/mathbank_rest/routers/quiz_runtime.py#L70)
**Operation ID:** `get_quiz_v1_quiz__quiz_id__get`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Quiz V1 Quiz  Quiz Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/quiz/{quiz_id}/questions/{question_id}/respond`
**Purpose:** Respond
**Tags:** `quiz`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`respond`](../../../mathbank-rest/src/mathbank_rest/routers/quiz_runtime.py#L82)
**Operation ID:** `respond_v1_quiz__quiz_id__questions__question_id__respond_post`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`); `question_id` (path, required; `{"format":"uuid","title":"Question Id","type":"string"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__quiz_runtime__RespondRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Respond V1 Quiz  Quiz Id  Questions  Question Id  Respond Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/quiz/{quiz_id}/review`
**Purpose:** Review
**Tags:** `quiz`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`review`](../../../mathbank-rest/src/mathbank_rest/routers/quiz_runtime.py#L95)
**Operation ID:** `review_v1_quiz__quiz_id__review_get`
**Parameters:** `quiz_id` (path, required; `{"format":"uuid","title":"Quiz Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Review V1 Quiz  Quiz Id  Review Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/realtime/sessions/{sid}`
**Purpose:** Realtime Info
**Tags:** `live-sessions`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`realtime_info`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L398)
**Operation ID:** `realtime_info_v1_realtime_sessions__sid__get`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`); `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Realtime Info V1 Realtime Sessions  Sid  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/recovery-plans/{plan_id}`
**Purpose:** Get Recovery Plan
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`get_recovery_plan`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L294)
**Operation ID:** `get_recovery_plan_v1_recovery_plans__plan_id__get`
**Parameters:** `plan_id` (path, required; `{"format":"uuid","title":"Plan Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Recovery Plan V1 Recovery Plans  Plan Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/recovery-plans/{plan_id}/abort`
**Purpose:** Abort Recovery
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`abort_recovery`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L338)
**Operation ID:** `abort_recovery_v1_recovery_plans__plan_id__abort_post`
**Parameters:** `plan_id` (path, required; `{"format":"uuid","title":"Plan Id","type":"string"}`); `Idempotency-Key` (header, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}`)
**Request body:** required; `application/json`: `VersionedRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Abort Recovery V1 Recovery Plans  Plan Id  Abort Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/recovery-plans/{plan_id}/items/{item_id}/responses`
**Purpose:** Answer Recovery Item
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`answer_recovery_item`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L306)
**Operation ID:** `answer_recovery_item_v1_recovery_plans__plan_id__items__item_id__responses_post`
**Parameters:** `plan_id` (path, required; `{"format":"uuid","title":"Plan Id","type":"string"}`); `item_id` (path, required; `{"format":"uuid","title":"Item Id","type":"string"}`); `Idempotency-Key` (header, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}`)
**Request body:** required; `application/json`: `RecoveryItemResponse` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Answer Recovery Item V1 Recovery Plans  Plan Id  Items  Item Id  Responses Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/recovery-plans/{plan_id}/next`
**Purpose:** Next Recovery Item
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`next_recovery_item`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L301)
**Operation ID:** `next_recovery_item_v1_recovery_plans__plan_id__next_get`
**Parameters:** `plan_id` (path, required; `{"format":"uuid","title":"Plan Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Next Recovery Item V1 Recovery Plans  Plan Id  Next Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/recovery-plans/{plan_id}/resume`
**Purpose:** Resume From Recovery
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`resume_from_recovery`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L331)
**Operation ID:** `resume_from_recovery_v1_recovery_plans__plan_id__resume_post`
**Parameters:** `plan_id` (path, required; `{"format":"uuid","title":"Plan Id","type":"string"}`); `Idempotency-Key` (header, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}`)
**Request body:** required; `application/json`: `VersionedRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Resume From Recovery V1 Recovery Plans  Plan Id  Resume Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/search/concepts`
**Purpose:** Search Concepts
**Tags:** `search`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`search_concepts`](../../../mathbank-rest/src/mathbank_rest/routers/v1.py#L138)
**Operation ID:** `search_concepts_v1_search_concepts_post`
**Request body:** required; `application/json`: `ConceptSearchRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Search Concepts V1 Search Concepts Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/search/problems`
**Purpose:** Search Problems
**Tags:** `search`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`search_problems`](../../../mathbank-rest/src/mathbank_rest/routers/v1.py#L175)
**Operation ID:** `search_problems_v1_search_problems_post`
**Request body:** required; `application/json`: `ProblemSearchRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Search Problems V1 Search Problems Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/solution-steps/{step_id}/practice`
**Purpose:** Practice For Step
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Operation ID:** `practice_for_step_v1_solution_steps__step_id__practice_get`
**Parameters:** `step_id` (path, required; `{"title":"Step Id","type":"string"}`); `limit` (query, optional; default `5`; `{"default":5,"maximum":20,"minimum":1,"title":"Limit","type":"integer"}`); `same_skill` (query, optional; default `True`; `{"default":true,"title":"Same Skill","type":"boolean"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Practice For Step V1 Solution Steps  Step Id  Practice Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/students/{student_id}/events`
**Purpose:** List Events
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`list_events`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L366)
**Operation ID:** `list_events_v1_students__student_id__events_get`
**Parameters:** `student_id` (path, required; `{"format":"uuid","title":"Student Id","type":"string"}`); `attempt_id` (query, optional; `{"anyOf":[{"format":"uuid","type":"string"},{"type":"null"}],"title":"Attempt Id"}`); `limit` (query, optional; default `100`; `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response List Events V1 Students  Student Id  Events Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/students/{student_id}/problems/{problem_ref}/attempts`
**Purpose:** Start Attempt
**Tags:** `step-runtime`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`start_attempt`](../../../mathbank-rest/src/mathbank_rest/routers/step_runtime.py#L88)
**Operation ID:** `start_attempt_v1_students__student_id__problems__problem_ref__attempts_post`
**Parameters:** `student_id` (path, required; `{"format":"uuid","title":"Student Id","type":"string"}`); `problem_ref` (path, required; `{"title":"Problem Ref","type":"string"}`); `Idempotency-Key` (header, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Idempotency-Key"}`)
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Start Attempt V1 Students  Student Id  Problems  Problem Ref  Attempts Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/techniques`
**Purpose:** Get Techniques
**Tags:** `taxonomy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_techniques`](../../../mathbank-rest/src/mathbank_rest/routers/v1.py#L106)
**Operation ID:** `get_techniques_v1_techniques_get`
**Parameters:** `q` (query, optional; `{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Q"}`); `limit` (query, optional; default `50`; `{"default":50,"maximum":200,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Techniques V1 Techniques Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/techniques/{slug}/problems`
**Purpose:** Get Technique Problems
**Tags:** `taxonomy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_technique_problems`](../../../mathbank-rest/src/mathbank_rest/routers/v1.py#L115)
**Operation ID:** `get_technique_problems_v1_techniques__slug__problems_get`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`); `limit` (query, optional; default `25`; `{"default":25,"maximum":200,"title":"Limit","type":"integer"}`); `offset` (query, optional; default `0`; `{"default":0,"minimum":0,"title":"Offset","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"items":{"additionalProperties":true,"type":"object"},"title":"Response Get Technique Problems V1 Techniques  Slug  Problems Get","type":"array"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/theorems/by-taxonomy/{taxonomy_node_id}`
**Purpose:** List Student Theorems For Taxonomy
**Tags:** `theorems`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`list_student_theorems_for_taxonomy`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L266)
**Operation ID:** `list_student_theorems_for_taxonomy_v1_theorems_by_taxonomy__taxonomy_node_id__get`
**Parameters:** `taxonomy_node_id` (path, required; `{"title":"Taxonomy Node Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response List Student Theorems For Taxonomy V1 Theorems By Taxonomy  Taxonomy Node Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/theorems/by-technique/{technique_slug}`
**Purpose:** List Student Theorems For Technique
**Tags:** `theorems`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`list_student_theorems_for_technique`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L271)
**Operation ID:** `list_student_theorems_for_technique_v1_theorems_by_technique__technique_slug__get`
**Parameters:** `technique_slug` (path, required; `{"title":"Technique Slug","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response List Student Theorems For Technique V1 Theorems By Technique  Technique Slug  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/theorems/search`
**Purpose:** Search Student Theorems
**Tags:** `theorems`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`search_student_theorems`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L245)
**Operation ID:** `search_student_theorems_v1_theorems_search_get`
**Parameters:** `q` (query, required; `{"maxLength":200,"minLength":1,"title":"Q","type":"string"}`); `field` (query, optional; default ``; `{"default":"","title":"Field","type":"string"}`); `kind` (query, optional; default ``; `{"default":"","title":"Kind","type":"string"}`); `limit` (query, optional; default `10`; `{"default":10,"maximum":50,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Search Student Theorems V1 Theorems Search Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/theorems/{slug}`
**Purpose:** Get Student Theorem
**Tags:** `theorems`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_student_theorem`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L256)
**Operation ID:** `get_student_theorem_v1_theorems__slug__get`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Student Theorem V1 Theorems  Slug  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/theorems/{slug}/prerequisites`
**Purpose:** Get Student Theorem Prerequisites
**Tags:** `theorems`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`get_student_theorem_prerequisites`](../../../mathbank-rest/src/mathbank_rest/routers/theorems.py#L261)
**Operation ID:** `get_student_theorem_prerequisites_v1_theorems__slug__prerequisites_get`
**Parameters:** `slug` (path, required; `{"title":"Slug","type":"string"}`); `max_depth` (query, optional; default `4`; `{"default":4,"maximum":10,"minimum":1,"title":"Max Depth","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Get Student Theorem Prerequisites V1 Theorems  Slug  Prerequisites Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/tutor/check-subproblem`
**Purpose:** Check Subproblem
**Tags:** `tutor`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`check_subproblem`](../../../mathbank-rest/src/mathbank_rest/routers/tutor.py#L35)
**Operation ID:** `check_subproblem_v1_tutor_check_subproblem_post`
**Request body:** required; `application/json`: `CheckSubproblemRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Check Subproblem V1 Tutor Check Subproblem Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/tutor/coach`
**Purpose:** Coach
**Tags:** `pedagogy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`coach`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L159)
**Operation ID:** `coach_v1_tutor_coach_post`
**Request body:** required; `application/json`: `CoachRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Coach V1 Tutor Coach Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/tutor/decompose`
**Purpose:** Decompose
**Tags:** `tutor`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`decompose`](../../../mathbank-rest/src/mathbank_rest/routers/tutor.py#L27)
**Operation ID:** `decompose_v1_tutor_decompose_post`
**Request body:** required; `application/json`: `DecomposeRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Decompose V1 Tutor Decompose Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/tutor/feedback`
**Purpose:** Feedback
**Tags:** `pedagogy`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`feedback`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L73)
**Operation ID:** `feedback_v1_tutor_feedback_post`
**Request body:** required; `application/json`: `FeedbackRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Feedback V1 Tutor Feedback Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/tutor/format-math`
**Purpose:** Format Math
**Tags:** `fluid-widgets`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`format_math`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L169)
**Operation ID:** `format_math_v1_tutor_format_math_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `FormatBody` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Format Math V1 Tutor Format Math Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/tutor/guidance-plan`
**Purpose:** Guidance Plan
**Tags:** `pedagogy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`guidance_plan`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L134)
**Operation ID:** `guidance_plan_v1_tutor_guidance_plan_post`
**Request body:** required; `application/json`: `GuidancePlanRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Guidance Plan V1 Tutor Guidance Plan Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/tutor/learning-context/{problem_code}`
**Purpose:** Learning Context
**Tags:** `pedagogy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`learning_context`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L104)
**Operation ID:** `learning_context_v1_tutor_learning_context__problem_code__get`
**Parameters:** `problem_code` (path, required; `{"title":"Problem Code","type":"string"}`); `enrich` (query, optional; default `True`; `{"default":true,"title":"Enrich","type":"boolean"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Learning Context V1 Tutor Learning Context  Problem Code  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/tutor/micro-check`
**Purpose:** Micro Check
**Tags:** `pedagogy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`micro_check`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L140)
**Operation ID:** `micro_check_v1_tutor_micro_check_post`
**Request body:** required; `application/json`: `MicroCheckRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Micro Check V1 Tutor Micro Check Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/tutor/practice/{problem_code}`
**Purpose:** Practice
**Tags:** `pedagogy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`practice`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L154)
**Operation ID:** `practice_v1_tutor_practice__problem_code__get`
**Parameters:** `problem_code` (path, required; `{"title":"Problem Code","type":"string"}`); `limit` (query, optional; default `5`; `{"default":5,"maximum":20,"minimum":1,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Practice V1 Tutor Practice  Problem Code  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/tutor/prerequisites/{skill_slug}`
**Purpose:** Prerequisites
**Tags:** `pedagogy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`prerequisites`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L149)
**Operation ID:** `prerequisites_v1_tutor_prerequisites__skill_slug__get`
**Parameters:** `skill_slug` (path, required; `{"title":"Skill Slug","type":"string"}`); `max_depth` (query, optional; default `4`; `{"default":4,"maximum":8,"minimum":1,"title":"Max Depth","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Prerequisites V1 Tutor Prerequisites  Skill Slug  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/tutor/route-attempts`
**Purpose:** Start
**Tags:** `tutoring-routes`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`start`](../../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py#L172)
**Operation ID:** `start_v1_tutor_route_attempts_post`
**Request body:** required; `application/json`: `StartRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/tutor/route-attempts/{attempt_id}`
**Purpose:** Current
**Tags:** `tutoring-routes`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`current`](../../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py#L177)
**Operation ID:** `current_v1_tutor_route_attempts__attempt_id__get`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/tutor/route-attempts/{attempt_id}/assist`
**Purpose:** Assist
**Tags:** `tutoring-routes`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`assist`](../../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py#L187)
**Operation ID:** `assist_v1_tutor_route_attempts__attempt_id__assist_post`
**Parameters:** `attempt_id` (path, required; `{"format":"uuid","title":"Attempt Id","type":"string"}`)
**Request body:** required; `application/json`: `AssistRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` unspecified; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/tutor/sessions/{sid}/actions`
**Purpose:** Tutor Action
**Tags:** `live-sessions`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`tutor_action`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L373)
**Operation ID:** `tutor_action_v1_tutor_sessions__sid__actions_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`)
**Request body:** required; `application/json`: `TutorActionIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Tutor Action V1 Tutor Sessions  Sid  Actions Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/tutor/sessions/{sid}/context`
**Purpose:** Tutor Context
**Tags:** `live-sessions`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`tutor_context`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L368)
**Operation ID:** `tutor_context_v1_tutor_sessions__sid__context_get`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`); `participant_id` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Participant Id"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Tutor Context V1 Tutor Sessions  Sid  Context Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/tutor/sessions/{sid}/messages`
**Purpose:** Tutor Message
**Tags:** `live-sessions`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`tutor_message`](../../../mathbank-rest/src/mathbank_rest/routers/live.py#L379)
**Operation ID:** `tutor_message_v1_tutor_sessions__sid__messages_post`
**Parameters:** `sid` (path, required; `{"title":"Sid","type":"string"}`)
**Request body:** required; `application/json`: `TutorMessageIn` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Tutor Message V1 Tutor Sessions  Sid  Messages Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/tutor/topic-plan`
**Purpose:** Topic Plan
**Tags:** `pedagogy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`topic_plan`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L41)
**Operation ID:** `topic_plan_v1_tutor_topic_plan_get`
**Parameters:** `q` (query, required; `{"maxLength":200,"minLength":1,"title":"Q","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Topic Plan V1 Tutor Topic Plan Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/tutor/topic-practice`
**Purpose:** Topic Practice
**Tags:** `pedagogy`
**OpenAPI security:** `HTTPBearer`
**Handler:** [`topic_practice`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L63)
**Operation ID:** `topic_practice_v1_tutor_topic_practice_post`
**Request body:** required; `application/json`: `TopicPracticeRequest` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Topic Practice V1 Tutor Topic Practice Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/tutor/workspace/{problem_code}`
**Purpose:** Workspace
**Tags:** `pedagogy`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`workspace`](../../../mathbank-rest/src/mathbank_rest/routers/pedagogy.py#L114)
**Operation ID:** `workspace_v1_tutor_workspace__problem_code__get`
**Parameters:** `problem_code` (path, required; `{"title":"Problem Code","type":"string"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Workspace V1 Tutor Workspace  Problem Code  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/widgets/generate`
**Purpose:** Widget Generate
**Tags:** `fluid-widgets`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`widget_generate`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L86)
**Operation ID:** `widget_generate_v1_widgets_generate_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `mathbank_rest__routers__fluid__GenerateBody` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Widget Generate V1 Widgets Generate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/widgets/registry`
**Purpose:** Widget Registry
**Tags:** `fluid-widgets`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`widget_registry`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L74)
**Operation ID:** `widget_registry_v1_widgets_registry_get`
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Widget Registry V1 Widgets Registry Get","type":"object"}`

### GET `/v1/widgets/specs`
**Purpose:** Widget Specs
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`widget_specs`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L117)
**Operation ID:** `widget_specs_v1_widgets_specs_get`
**Parameters:** `lifecycle` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Lifecycle"}`); `persistence` (query, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Persistence"}`); `limit` (query, optional; default `50`; `{"default":50,"maximum":200,"title":"Limit","type":"integer"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Widget Specs V1 Widgets Specs Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/widgets/specs`
**Purpose:** Widget Store
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`widget_store`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L105)
**Operation ID:** `widget_store_v1_widgets_specs_post`
**Parameters:** `x-actor-id` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}`)
**Request body:** required; `application/json`: `StoreBody` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `201` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Widget Store V1 Widgets Specs Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### GET `/v1/widgets/specs/{spec_id}`
**Purpose:** Widget Spec
**Tags:** `fluid-widgets`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`widget_spec`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L129)
**Operation ID:** `widget_spec_v1_widgets_specs__spec_id__get`
**Parameters:** `spec_id` (path, required; `{"title":"Spec Id","type":"string"}`); `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Widget Spec V1 Widgets Specs  Spec Id  Get","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/widgets/specs/{spec_id}/review`
**Purpose:** Widget Review
**Tags:** `fluid-widgets`
**OpenAPI security:** `APIKeyHeader`
**Handler:** [`widget_review`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L140)
**Operation ID:** `widget_review_v1_widgets_specs__spec_id__review_post`
**Parameters:** `spec_id` (path, required; `{"title":"Spec Id","type":"string"}`)
**Request body:** required; `application/json`: `ReviewBody` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Widget Review V1 Widgets Specs  Spec Id  Review Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))

### POST `/v1/widgets/validate`
**Purpose:** Widget Validate
**Tags:** `fluid-widgets`
**OpenAPI security:** none declared (implementation may enforce dependencies/ownership).
**Handler:** [`widget_validate`](../../../mathbank-rest/src/mathbank_rest/routers/fluid.py#L79)
**Operation ID:** `widget_validate_v1_widgets_validate_post`
**Parameters:** `authorization` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Authorization"}`); `x-admin-api-key` (header, optional; `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Admin-Api-Key"}`)
**Request body:** required; `application/json`: `SpecBody` (in [OpenAPI snapshot](openapi.json))
**Documented responses:** `200` Successful Response: `application/json` `{"additionalProperties":true,"title":"Response Widget Validate V1 Widgets Validate Post","type":"object"}`; `422` Validation Error: `application/json` `HTTPValidationError` (in [OpenAPI snapshot](openapi.json))
