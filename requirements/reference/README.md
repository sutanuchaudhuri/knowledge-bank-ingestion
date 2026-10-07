# MathBank implementation reference

This folder is the canonical architecture reference for the checked-in MathBank implementation. Schema, DML, graph and API descriptions are source-derived; separately dated operator-reported deployment observations are labelled as such and are not independent schema or acceptance verification. This documentation refresh did not execute migrations, ingestion, graph publication, service starts, live schema probes, or paid model/API calls.

## Evidence and revision

### Corpus authoring incremental reference

Source revision `77eb6784a000a9cc6077526fa4accc7c4111afac` with relevant
worktree changes; inspected migration 025, authoring runtime/router, private
storage, canonical image readers/serving, source-image upsert protection,
admin proxy/navigation/UI and focused tests. Refreshed the related
[DDL](POSTGRES_SCHEMA.md#corpus-authoring-migration-025),
[DML](POSTGRES_DML.md#reviewed-corpus-authoring),
[HTTP](REST_API.md#admin-corpus-authoring) and
[graph boundary](GRAPH_SCHEMA.md#corpus-authoring-boundary).
This is an incremental implementation-grounded refresh, not a complete new
catalog audit of unrelated tables/projectors.

Screened source OpenAPI has **198 paths / 102 schemas**. Separate implementation
verification on 2026-10-07 UTC: the user explicitly selected REST's configured
database; migration 025 was applied and REST reloaded. Source/running OpenAPI
matched, anonymous access was denied and authenticated read-only authoring
queries worked. No paid models, draft publication or Neo4j writes occurred.
These activation actions were implementation work, not documentation generation.

The [developer query library](../../mathbank_data_ingestion/queries/README.md)
contains 210 explained read-only diagnostics, with indexed categories and
single-query emission. All 210 passed PostgreSQL PREPARE/DEALLOCATE against the
selected target without executing diagnostics or exporting data. Result
semantics, scan cost and privileges on other databases remain unverified.


### Profile theme-coverage incremental reference

Source revision `77eb6784a000a9cc6077526fa4accc7c4111afac` plus relevant worktree changes; inspected `db/learner.py`, shared
corpus evidence in `db/queries.py`, learner route/models and web profile/proxy.
Adds authenticated read-only per-theme distinct available/attempted/remaining
counts. See [REST contract](REST_API.md#profile-practice-coverage-incremental-contract)
and [DML](POSTGRES_DML.md#profile-theme-coverage-read-only).
No schema migration, mastery write or graph projection changes. This is a
narrow REST/DML/UI refresh, not a full-system schema audit.
The screened source OpenAPI now has **190 paths / 97 schemas**. Earlier
snapshot counts and deployment-parity checks below are historical.
Separate verification, 2026-10-07 UTC: after the user-authorized REST-only
reload, running OpenAPI matched source, the anonymous route returned 401 and
a synthetic nonexistent-learner read returned zero attempted coverage without
writing learner data. Sample theme counts matched the exact corpus filters.
Twelve focused REST tests, three desktop/mobile profile browser tests and the
production web build passed. No live schema-parity or mastery-certification
claim accompanies these checks.

### Solution-grounded planning and compact practice incremental reference

Source revision `1582f808a731e571e79b588d4c73e717eefc7956` plus relevant worktree
changes. Newly examined `solution_guidance.py`, coaching/router callers,
`problem_guidance.py`, agent routing/output guards, stream mapper and
`problemPresentation.mjs`; migration 001's solution columns and inventory
001–024 were checked. DDL and projector files are unchanged. This is an
incremental refresh across REST, PostgreSQL and graph boundaries, not a new
full-system catalog audit.

The latest screened source snapshot is **189 paths / 95 schemas**. It adds
explicit `POST /v1/tutor/guidance-plan`; `/coach` privately reads stored
references. Only safe plans/hints return, with source-status/count metadata.
There is no new solution/planning table, projection, artifact or mastery write.
Safe conversation plans use existing ADK session JSON; browser drafts remain
temporary. Display normalization preserves canonical source statements and
does not invoke a paid formatter.

Separate implementation verification, 2026-10-07 UTC: the authorized service
reload activated the new tool; actual AIME planning/ADK routing consulted two
unverified records and returned a roadmap/checkpoint without raw solution or
answer fields. The temporary synthetic session was removed. Source and running
OpenAPI matched 189/95 exactly. Focused REST/agent/browser tests, build and lint
passed; see [34](../34_GUIDED_PROBLEM_WORKSPACE.md). No general provider-quality
or live database/graph schema-parity claim accompanies these observations.
The earlier OpenAPI counts and verifications below are historical.

### Guided-workspace incremental reference

Source revision `1582f808a731e571e79b588d4c73e717eefc7956`, including related
worktree changes. Freshly examined `guided_orientation.py`, `guided_visuals.py`, pedagogy
routes/statement/graph-read helpers, browser workspace/upload/proxy, existing
attempt-media reads and both graph projector ownership paths; migration
inventory remains 001–024. This is an incremental contract refresh, not a
new full-system catalog audit or live-schema verification.

Screened source OpenAPI now has **188 paths / 94 schemas**, adding public
`GET /v1/tutor/workspace/{problem_code}` and `POST /v1/tutor/micro-check`; learning context adds a stateless
`pedagogy_session` envelope. Source generation invokes no endpoint, model or
database query. PostgreSQL DDL and graph projections gain no session object;
temporary workspace state is not the existing persisted ADK topic lesson.
Graph reads use managed read transactions for driver retry. See
[requirement 34](../34_GUIDED_PROBLEM_WORKSPACE.md) for delivery boundaries.
The earlier 186/93 and 187/94 counts below are historical.

Current-object visual update: graph-independent workspace bootstrap returns
authored orientation and source-verified ordered Q31 circumcenter definitions.
Each visual intent names required objects and a level bound; browser geometry
computes/checks both iterations and suppresses mismatched frames. No raw model
SVG/image or generic geometry fallback is introduced. Browser drafts and
stateless intents are not persisted artifacts, learner evidence or mastery.
Context loads independently with a 15-second browser deadline, bootstrap
12 seconds and tutor GET proxy 20 seconds. No schema/projector change or paid
provider call accompanies this visual contract.

Separate implementation verification, 2026-10-07 UTC: workspace bootstrap
returned the canonical visual intent and eight definitions in 0.29 seconds.
The live UI showed A₁/BCD immediately on opening the visual and changed focus
through actual micro-check responses; both construction levels rendered with
no desktop/mobile overflow. Running OpenAPI matched the 188/94 source snapshot.
The focused 38 REST / 18 JavaScript / 19 browser tests and production build
passed. These observations do not establish live schema parity or a generalized
model-driven geometry engine.

Separate implementation observation, 2026-10-07 UTC: after the explicitly
approved REST reload, running OpenAPI matched the source snapshot exactly
(187/94), and both requested learning contexts returned authored checks.
Q31's impossible deeper-prerequisite probe is skipped when the approved
bounded traversal is empty. A read-only timing probe returned context in
2.6 seconds instead of the previously observed over-60-second stall.
This does not establish live database/graph schema parity.

### Latest incremental reference: topic-first lessons and practice

Source revision `c79060ac0771175baa6e04b37bede840f8c30ee1`, including relevant
worktree changes. This is a source-grounded refresh of all three references,
**not a new full-system catalog/projection audit**. Newly examined: migrations
023/024, `db/topic_pedagogy.py`, `db/retrieval_audit.py`, shared
`scripts/power_geometry_evidence.py`, textbook import validation,
`practice_selection.py` / `practice_profiles.json`, pedagogy routers/security,
`session_config.py`, installed ADK 2.11 session DML, tutor lesson/audit/formatter
tools and browser proxies/components/tests. The two graph projectors were
checked for unchanged ownership; feedback and topic plans are not projected.

The current screened, source-generated OpenAPI is **186 paths / 93 schemas**.
Source generation observed 2026-10-07 UTC, without endpoint calls, database
connections, models or service starts. Earlier counts below are historical.
[Requirement 33](../33_TOPIC_FIRST_TUTOR_AND_PRACTICE.md) records delivered
behavior, test evidence and remaining limitations. The application work
separately verified actual ADK PostgreSQL lesson persistence with an exact
synthetic-session cleanup; this is not full live schema parity. Migration 024
was explicitly authorized/applied during implementation, not by this docs skill.

### Interactive lesson and private-work update (source-derived, 2026-10-07 UTC)

At HEAD `c79060ac0771175baa6e04b37bede840f8c30ee1` with this task's relevant
worktree changes included, the ADK tutor now persists stage status/timing and
revision-checked navigation in its existing session JSON. The chat maps a
learner-safe progress payload to the right rail and attaches printed work only
to a canonical code explicitly present in the latest tutor reply. The existing
attempt-media API remains unchanged; explicit student transcription approval
and analysis are still required. Analysis checks problem context and refuses
unrelated or unverified work before critique. No PostgreSQL/Neo4j DDL, graph
projection or REST route changed. Source OpenAPI was regenerated in memory and
matched the committed snapshot exactly (3.1.0, 186 paths, 93 schemas). No live
schema or graph was queried; this is an incremental behavior refresh, not a new
full-catalog audit.

Separate implementation verification (2026-10-07 UTC): reloaded REST and agent
responded on their existing local ports; running REST OpenAPI exactly matched
186 paths / 93 schemas. Six threshold-qualified Power practice candidates
excluded the corrected polygon; invalid supplied bearer/admin/report requests
failed 401. All four private diagram frames rendered safely and a nonexistent
ordinal failed 404. Known-book provenance used `provenance_status=LOCATION_INCOMPLETE`.
A rollback-only synthetic feedback integration test verified pending-only
constraints, duplicate audit retention, positive/negative review labels and
negative practice gating, then verified exact cleanup. These checks did not
publish graph data, train/invoke models or prove full live schema parity.

- Evidence mode: **source-derived** for implementation/schema descriptions, plus separately labelled operator-reported deployment observations (not independently verified).
- Source revision: `3e915d015aa34268996724a3014c850f5892596e` (refreshed 2026-10-06 for migrations 021/022 and multimodal attempt/artifact runtime surfaces).
- Worktree state included: yes. This refresh includes all inspected uncommitted changes at this revision, including `mathbank-db/sql/021_attempt_media.sql` and `022_artifact_runtime.sql`, their REST/runtime modules and routers, the `mathbank-live` private attempt-event relay, and the `mathbank-web` attempt/artifact proxies and pages. The same evidence also includes the uncommitted AMC/AIME source-text repair and preceding implementation additions through migration 020.
- Worktree state included: yes. The 2026-10-06 refresh added the uncommitted files `mathbank-db/sql/020_live_fluid_platform.sql`, `mathbank-rest/src/mathbank_rest/{widgets,math_format,authoring,live_runtime}.py`, `routers/fluid.py`, `routers/live.py`, `mathbank-agent/agents/mathbank_tutor/tools/widget_tools.py`, `mathbank-widgets/src/*`, `mathbank-live/` (custom server, `lib/*`, `app/api/*`), `mathbank-web/app/api/{voice,format-math}`, `mathbank-web/app/admin/(protected)/widgets`. Earlier refreshes covered `mathbank-db/sql/010_textbook_import.sql`, `011_step_vector_metadata.sql`, `012_step_runtime.sql`, `013_step_hints.sql`, `014_gap_diagnosis.sql`, `015_recovery_runtime.sql`, `016_agent_session_link.sql`, `017_step_techniques.sql`, `018_outbox_consumers.sql`, `019_admin_import_review.sql`, `mathbank-db/etl/derive_step_techniques.py`, `run_projection_requests.py`, `mathbank-rest/src/mathbank_rest/outbox_worker.py`, `db/import_admin.py`, `routers/admin_imports.py`, `mathbank-agent/agents/mathbank_tutor/tools/step_runtime_tools.py`, `mathbank-web/app/api/rest/admin/imports/[[...path]]/route.js`, `lib/adminImportsProxy.mjs`, `app/admin/(protected)/imports`, `mathbank-db/etl/import_textbook_package.py`, `embed_textbook_steps.py`, `mathbank-graph/etl/project_textbook_steps.py`, `mathbank-rest/src/mathbank_rest/db/step_search.py`, `mathbank-rest/src/mathbank_rest/step_runtime.py`, `mathbank-rest/src/mathbank_rest/step_tutor.py`, `mathbank-rest/src/mathbank_rest/step_diagnosis.py`, `mathbank-rest/src/mathbank_rest/routers/step_runtime.py`, `agent_transcripts.py`, `routers/agent_sessions.py`, `mathbank-web/app/api/rest/solve/[...path]/route.js`, `mathbank-web/lib/solveProxy.mjs`, `mathbank-web/app/learn/solve/[code]`, and edits to `mathbank-rest/src/mathbank_rest/main.py`, graph, database and requirements files.
- OpenAPI snapshot: generated in-process from `mathbank_rest.main:app.openapi()` with `mathbank-rest/.venv/bin/python`; no server was started. Module imports instantiate settings, a SQLAlchemy engine and a Neo4j driver but do not call endpoint handlers or connect to either database. The 2026-10-06 snapshot is OpenAPI `3.1.0`, 174 paths and 89 component schemas; credential-like patterns were screened before writing. Final frozen-worktree verification regenerated the document in memory and matched the committed snapshot byte-for-byte; source counts are 18 attempt-media, 16 artifacts and 140 other paths.
- Incremental geometry/chat contract refresh (2026-10-07 UTC): inspected `routers/artifacts.py`, `artifact_runtime.py`, tutor `artifact_tools.py`/registry, web private proxy, `TutorAnswer`, `GeometryArtifact` and parser/tests. Source OpenAPI now has 176 paths / 90 schemas (18 attempt-media, 18 artifacts, 140 other). Two authenticated ephemeral preview routes reuse the geometry validator/renderer with exact triangle-incircle construction and no storage/publication/provider calls. `draw_geometry_diagram` is an immediate tutor capability; the previous staff-only artifact publication boundary remains unchanged. The prior full-system observation below remains historical.
- Subsequent incremental subject-specialist refresh: all ten artifact agents are actual ADK agents using AgentTool delegation (`artifact_agents.py` plus tutor registry/tools). Two generic private subject preview routes extend the same deterministic renderer. Current source OpenAPI: 178 paths / 90 schemas (18 attempt-media, 20 artifacts, 140 other). Tested network is acyclic, owner-authorized through invocation-only state, and does not expose remote A2A HTTP endpoints. No database/graph schema change accompanies this topology.
- No live database/Neo4j/API parity is claimed.
- Incremental topic/feedback source refresh (2026-10-07 UTC): revision `c79060ac0771175baa6e04b37bede840f8c30ee1` plus related worktree changes. Inspected migration 023, topic/feedback DB/router contracts, textbook rejection preservation, real ADK pedagogy routing and proxy/activity surfaces. Source OpenAPI now has 184 paths / 92 schemas. No full-system or live schema-parity audit is implied; the feedback table is not projected into Neo4j.
- Separate runtime verification (2026-10-07 UTC): the reloaded REST service's `/openapi.json` matches the source snapshot (184 paths / 92 schemas). Anonymous learner-feedback/admin-queue requests return 401. This verifies deployment contracts, not full database catalog parity or paid-model response quality.
- Incremental source-pane/practice refresh: inspected `db/problem_sources.py`, source routes/proxies, shared source controls/pane, and tutor recommendation tools/tests. Current source snapshot: 180 paths / 90 schemas (18 attempt-media, 20 artifacts, 142 other). Two public read-only routes generate highlighted page/annotated PDF copies from verified locations without modifying original documents. New practice tools exclude unavailable required diagrams and return learner-safe ready-to-display Markdown with known source links. This does not establish paid-model tool selection or PDFs for web-only corpus entries.
- Separate post-deployment observation: running REST also reports 178 paths / 90 schemas, with both generic preview routes; anonymous generic preview POST returns 401. Tutor app discovery and real module import confirm the app and all ten specialists. This does not verify live model quality or database schema parity.

## Reported deployment observations

The deployment operator reported the following on 2026-10-06 (UTC); this documentation refresh did not independently probe the target:

- Migrations 021 and 022 were applied successfully to the explicitly selected Neon production target. This is operator-reported application status, not an independent schema-catalog comparison.
- Rollback-only synthetic workflow tests passed for approval idempotence; pending NULL correctness not treated as wrong; version changes invalidating prior assessment; instructor override preserving AI assessment and stopping retry; ownership-mismatch 404; low-confidence transcription remaining uncertain; and media purge preserving an approved attempt. The reported tests used synthetic data and rolled back.
- The private S3 bucket `mathbank-runtime` was created. After an earlier smoke failure (`ObjectStoreError`), the deployment operator reports successful interface-level put/read/delete checks, unauthorized GET returning 403, and synthetic cleanup. Bucket resolution accepts `AWS_BUCKET_NAME` only when `MATHBANK_OBJECT_BUCKET` is absent; conflicting values fail with a sanitized error, and both absent defaults to `mathbank-runtime`. A separate artifact rollback test used a mocked object store, not live S3. No new production storage calls were made by the latest integration runs; the checks are scoped and do not establish complete storage acceptance.
- Final provider direction is to use official direct OpenAI endpoints and the shared project credential loader used by `mathbank-agent` for new agentic runtime stages; `MATHBANK_RUNTIME_AI_PROVIDER` defaults to `openai`, and Gateway inference is avoided unless explicitly selected. Gateway vision failed with HTTP 403 over a billing-credit blocker; direct OpenAI runtime failed with HTTP 429 `insufficient_quota`. No successful model response/token use or inference is reported; the user chose available tests rather than adding credits. Runtime follows service `MATHBANK_AGENT_MODEL` (default `openai/gpt-4o-mini`); a root model value applies to a service only when synchronized. An explicit `MATHBANK_RUNTIME_AI_MODEL` override is supported and takes precedence over the agent model setting. Current source also reads runtime-specific root/service settings, so the deployed effective override value is not independently verified by this docs refresh. Runtime uses the shared project OpenAI credential loader and honors `OPENAI_API_BASE` / `OPENAI_BASE_URL`; Gateway configuration/credentials remain unchanged. Timestamped speech and artifact-agent embeddings use direct OpenAI (`whisper-1` and `text-embedding-3-small`, 1,536 dimensions by default); configuration does not prove inference success.
- Parent reports that the final REST and agent processes were responsive after restart and exposed 34 new REST paths (18 attempt-media, 16 artifacts), matching the checked-in OpenAPI source snapshot; three anonymous private REST/proxy GETs returned 401. These are operator-reported live observations, not probes performed by this documentation refresh. Five new agent tools are registered and offline-tested: two attempt-media context readers and three artifact search/read/request tools. They do not approve student work, generate/publish artifacts, or call models. Final selected checks reported by the parent: 184 focused REST offline passes (including voiced/silent-video normalization), six media and one artifact rollback-only Neon tests passed, 15 agent-tool tests passed, 25 UI unit tests and 17 mocked E2E cases passed, and the web production build passed. The artifact test used mocked object storage and no AI/provider call or real object bytes. A sanitized constructed client confirmed provider `openai`, the official `api.openai.com` endpoint, and model `gpt-4o-mini`; this configuration observation does not imply inference success. Earlier test selections are omitted from this final result summary. These scoped checks do not mean either implementation pack is complete.

## Files

| File | Purpose |
|---|---|
| [GRAPH_SCHEMA.md](GRAPH_SCHEMA.md) | Neo4j labels, node properties, relationship endpoint pairs, projection/reconciliation rules, constraints, and UI exposure. |
| [POSTGRES_SCHEMA.md](POSTGRES_SCHEMA.md) | Composite PostgreSQL DDL after migrations `001` through `022`, including schemas, tables, columns, constraints, indexes, triggers/functions, and framework-owned agent sessions. |
| [POSTGRES_DML.md](POSTGRES_DML.md) | Implemented read/write paths, upsert keys, idempotency, approval/audit effects, deletion/cascade behavior, and cross-store publication boundaries, including private attempts and reusable artifacts. |
| [REST_API.md](REST_API.md) | FastAPI route inventory, auth, OpenAPI generation, web proxy/agent surfaces, and separate `mathbank-live` Socket.IO behavior, including attempt-media and artifact endpoints. |
| [openapi.json](openapi.json) | Deterministic source-generated FastAPI OpenAPI snapshot. |

## Source files examined

Primary evidence came from:

- PostgreSQL DDL: `mathbank-db/sql/001_schema.sql` through `020_live_fluid_platform.sql`, plus `mathbank-db/Makefile` migration targets and the operator DML script `mathbank-db/sql/ops/approve_learning_items_auto.sql`.
- New PostgreSQL DDL: `mathbank-db/sql/021_attempt_media.sql`, `022_artifact_runtime.sql`; migration target definitions in `mathbank-db/Makefile`.
- ETL/write paths: `mathbank-db/etl/load_corpus.py`, `pdf_pipeline.py`, `import_pedagogy.py`, `embed_corpus.py`, `import_textbook_package.py`, `embed_textbook_steps.py`, `derive_step_techniques.py`, `run_projection_requests.py`, `mathbank-rest/src/mathbank_rest/outbox_worker.py`, `db/import_admin.py`, plus batch/archive helpers by reference.
- Graph projection: `mathbank-graph/etl/project_from_postgres.py`, `project_textbook_steps.py`, `mathbank-web/lib/graphConfig.js`, `mathbank-web/lib/graphMetadata.mjs`, REST graph/pedagogy readers.
- REST: `mathbank-rest/src/mathbank_rest/main.py`, routers under `mathbank-rest/src/mathbank_rest/routers/`, DB modules under `mathbank-rest/src/mathbank_rest/db/`, `security.py`, `mastery.py`, `enrichment.py`, `relationship_enrichment.py`, `step_runtime.py`, `step_tutor.py`, `step_diagnosis.py`, `step_recovery.py`, `db/step_search.py`, `widgets.py`, `math_format.py`, `authoring.py`, `live_runtime.py`, `routers/fluid.py` and `routers/live.py`.
- Multimodal/artifact REST and storage: `attempt_media.py`, `attempt_media_models.py`, `media_processing.py`, `artifact_runtime.py`, `object_store.py`, `runtime_ai.py`, `routers/attempt_media.py`, `routers/artifacts.py`; learner mastery filtering in `db/learner.py` and `mastery.py`.
- Agent/web: `mathbank-agent/session_config.py`, `mathbank-agent/server.py`, `mathbank-agent/agents/mathbank_tutor/tools/{attempt_media_tools,artifact_tools}.py` and their `agent.py` registry wiring, `mathbank-web/app/api/**`, including the allow-listed `app/api/rest/{attempt-media,artifacts}/[[...path]]/route.js` proxies, attempt/artifact pages and components, `lib/privateRuntimeProxy.mjs`, `mathbank-live/server.mjs`, and `mathbank-live/lib/attemptEvents.mjs`.

## Regeneration procedure

1. Inspect `git status --short` and record `git rev-parse HEAD`.
2. Read the architecture-doc skill and source files above.
3. Generate the OpenAPI snapshot from source only:

   ```sh
   PYTHONPATH=mathbank-rest/src mathbank-rest/.venv/bin/python - <<'PY'
   import json
   import re
   from pathlib import Path
   from mathbank_rest.main import app

   schema = app.openapi()
   if not schema.get("openapi") or not schema.get("paths") or not schema.get("components", {}).get("schemas"):
       raise SystemExit("OpenAPI validation failed")
   text = json.dumps(schema, sort_keys=True, indent=2)
   patterns = [
       r"(?i)\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}\b",
       r"\bAKIA[0-9A-Z]{16}\b",
       r"(?i)://[^/@\s:]+:[^/@\s]+@",
       r"(?i)\b(?:password|secret|token|api[_-]?key)\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{12,}",
   ]
   if any(re.search(pattern, text) for pattern in patterns):
       raise SystemExit("OpenAPI snapshot scan blocked")
   Path("requirements/reference/openapi.json").write_text(text + "\n")
   PY
   ```

4. Refresh the Markdown references from checked-in source evidence. Do not run migrations, ETL, graph projection, server start targets, or model-backed enrichment/embedding commands.

## Drift limitations and gaps

- These references describe implemented code and DDL, not whether a target database has applied every migration.
- Neo4j property types are inferred from projector code; Neo4j does not enforce most property schemas.
- Agent session table internals are framework-owned by Google ADK `DatabaseSessionService`; the project creates/selects the `agent_sessions` schema but does not define the framework table DDL in repository migrations.
- `mathbank-rest/src/mathbank_rest/db/step_search.py` implements step-level retrieval; `GET /v1/solution-steps/{step_id:path}/practice` exposes the no-step-text practice lookup. Broader step/item search helpers remain internal. Step and recovery APIs use slash-bearing step IDs via `{step_id:path}` where needed, even though OpenAPI displays the parameter as `{step_id}`.
- `visual.asset` (migration 020) has DDL but no reader/writer in code; live event delivery is REST polling by the `mathbank-live` gateway, not an event bus.
- Automatic enrichment and relationship enrichment code can call paid models when endpoints/workers invoke it; this documentation task inspected source only and did not execute those paths.
- Multimodal `/process` and `/analyse` are explicit model-backed stages. Final direction is direct OpenAI using the shared endpoint/credential loader as `mathbank-agent`; Gateway is an explicitly selected alternative, never a silent fallback. Gateway returned 403 and direct OpenAI returned 429 `insufficient_quota`; no successful inference is claimed. Runtime uses service `MATHBANK_AGENT_MODEL` (`openai/gpt-4o-mini` default); a root value is used by services when synchronized, and explicit `MATHBANK_RUNTIME_AI_MODEL` override is supported. The checked worktree resolver also reads runtime-specific root/REST settings before agent model files, so the effective deployed override value is not independently verified. Speech uses direct OpenAI `whisper-1`; artifact embedding uses the shared direct OpenAI client and defaults to `text-embedding-3-small` at 1,536 dimensions.
- Migrations 021 and 022 application to the explicitly selected Neon production target is operator-reported, not independently checked against live schema metadata. The initial object-store smoke failed; subsequent operator-reported interface checks passed put/read/delete, unauthenticated GET 403 and synthetic cleanup after bucket-alias configuration handling. The artifact rollback test used mocked object storage and does not add live S3 evidence. `AWS_ENDPOINT_URL_S3` is the object-store endpoint, not a Neon Auth or AI Gateway URL.
- Multimodal outbox payloads contain identifiers and sequence/version metadata, not media bytes, transcript text or assessment prose. The checked-in graph projectors do not project attempts, learner media, transcripts or artifact content into Neo4j.
- Worktree implementation evidence does not establish deployed parity or end-to-end acceptance.
