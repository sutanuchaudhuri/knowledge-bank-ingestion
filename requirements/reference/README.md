# MathBank implementation reference

This folder is the canonical source-derived architecture reference for the checked-in MathBank implementation.
It was refreshed from repository sources only; no migrations, ingestion, graph publication, service start, live schema probes, or paid model/API calls were run.

## Evidence and revision

- Evidence mode: **source-derived only**.
- Source revision: `43c3316d5b6f8a838874de4aa384cb28ef00aa1a` (refreshed 2026-10-06 for migration 020 and the fluid/live/widget surfaces).
- Worktree state included: yes. The 2026-10-06 refresh added the uncommitted files `mathbank-db/sql/020_live_fluid_platform.sql`, `mathbank-rest/src/mathbank_rest/{widgets,math_format,authoring,live_runtime}.py`, `routers/fluid.py`, `routers/live.py`, `mathbank-agent/agents/mathbank_tutor/tools/widget_tools.py`, `mathbank-widgets/src/*`, `mathbank-live/` (custom server, `lib/*`, `app/api/*`), `mathbank-web/app/api/{voice,format-math}`, `mathbank-web/app/admin/(protected)/widgets`. Earlier refreshes covered `mathbank-db/sql/010_textbook_import.sql`, `011_step_vector_metadata.sql`, `012_step_runtime.sql`, `013_step_hints.sql`, `014_gap_diagnosis.sql`, `015_recovery_runtime.sql`, `016_agent_session_link.sql`, `017_step_techniques.sql`, `018_outbox_consumers.sql`, `019_admin_import_review.sql`, `mathbank-db/etl/derive_step_techniques.py`, `run_projection_requests.py`, `mathbank-rest/src/mathbank_rest/outbox_worker.py`, `db/import_admin.py`, `routers/admin_imports.py`, `mathbank-agent/agents/mathbank_tutor/tools/step_runtime_tools.py`, `mathbank-web/app/api/rest/admin/imports/[[...path]]/route.js`, `lib/adminImportsProxy.mjs`, `app/admin/(protected)/imports`, `mathbank-db/etl/import_textbook_package.py`, `embed_textbook_steps.py`, `mathbank-graph/etl/project_textbook_steps.py`, `mathbank-rest/src/mathbank_rest/db/step_search.py`, `mathbank-rest/src/mathbank_rest/step_runtime.py`, `mathbank-rest/src/mathbank_rest/step_tutor.py`, `mathbank-rest/src/mathbank_rest/step_diagnosis.py`, `mathbank-rest/src/mathbank_rest/routers/step_runtime.py`, `agent_transcripts.py`, `routers/agent_sessions.py`, `mathbank-web/app/api/rest/solve/[...path]/route.js`, `mathbank-web/lib/solveProxy.mjs`, `mathbank-web/app/learn/solve/[code]`, and edits to `mathbank-rest/src/mathbank_rest/main.py`, graph, database and requirements files.
- OpenAPI snapshot: generated in-process from `mathbank_rest.main:app.openapi()` with `mathbank-rest/.venv/bin/python`; no server was started. Module-level import side effects were checked first: imports instantiate settings, SQLAlchemy and Neo4j client objects, but do not call endpoint handlers or connect until used. The 2026-10-06 snapshot (137 paths, 63 schemas; adds 47 fluid/live/widget/authoring paths to the previous 90) was scanned for obvious credential/connection-string patterns before writing.
- No live database/Neo4j/API parity is claimed.

## Files

| File | Purpose |
|---|---|
| [GRAPH_SCHEMA.md](GRAPH_SCHEMA.md) | Neo4j labels, node properties, relationship endpoint pairs, projection/reconciliation rules, constraints, and UI exposure. |
| [POSTGRES_SCHEMA.md](POSTGRES_SCHEMA.md) | Composite PostgreSQL DDL after migrations `001` through `020`, including schemas, tables, columns, constraints, indexes, triggers/functions, and framework-owned agent sessions. |
| [POSTGRES_DML.md](POSTGRES_DML.md) | Implemented read/write paths, upsert keys, idempotency, approval/audit effects, deletion/cascade behavior, and cross-store publication boundaries. |
| [REST_API.md](REST_API.md) | FastAPI endpoint inventory, auth, request/response model references, OpenAPI generation, exposed step runtime, Phase 9 diagnoses, Phase 10 recovery routes, admin gap/recovery views, step-practice search, web proxy routes, and ADK agent surface, fluid/live/authoring/widget routes (doc 27/28), and the `mathbank-live` Next.js + Socket.IO surface. |
| [openapi.json](openapi.json) | Deterministic source-generated FastAPI OpenAPI snapshot. |

## Source files examined

Primary evidence came from:

- PostgreSQL DDL: `mathbank-db/sql/001_schema.sql` through `020_live_fluid_platform.sql`, plus `mathbank-db/Makefile` migration targets and the operator DML script `mathbank-db/sql/ops/approve_learning_items_auto.sql`.
- ETL/write paths: `mathbank-db/etl/load_corpus.py`, `pdf_pipeline.py`, `import_pedagogy.py`, `embed_corpus.py`, `import_textbook_package.py`, `embed_textbook_steps.py`, `derive_step_techniques.py`, `run_projection_requests.py`, `mathbank-rest/src/mathbank_rest/outbox_worker.py`, `db/import_admin.py`, plus batch/archive helpers by reference.
- Graph projection: `mathbank-graph/etl/project_from_postgres.py`, `project_textbook_steps.py`, `mathbank-web/lib/graphConfig.js`, `mathbank-web/lib/graphMetadata.mjs`, REST graph/pedagogy readers.
- REST: `mathbank-rest/src/mathbank_rest/main.py`, routers under `mathbank-rest/src/mathbank_rest/routers/`, DB modules under `mathbank-rest/src/mathbank_rest/db/`, `security.py`, `mastery.py`, `enrichment.py`, `relationship_enrichment.py`, `step_runtime.py`, `step_tutor.py`, `step_diagnosis.py`, `step_recovery.py`, `db/step_search.py`, `widgets.py`, `math_format.py`, `authoring.py`, `live_runtime.py`, `routers/fluid.py` and `routers/live.py`.
- Agent/web: `mathbank-agent/session_config.py`, `mathbank-agent/server.py`, `mathbank-web/app/api/**`, including `app/api/rest/solve/[...path]/route.js`, `app/api/rest/admin/knowledge-gaps/route.js`, `mathbank-web/app/admin/(protected)/knowledge-gaps/page.jsx`, `mathbank-web/app/learn/solve/[code]`, `mathbank-web/lib/*.js`, and `mathbank-web/lib/*.mjs`, including `lib/solveProxy.mjs` and `lib/adminGapsProxy.mjs` with Phase 10 recovery/admin proxy allow-list entries; `mathbank-web/app/api/{voice,format-math}`, `mathbank-widgets/src/server.mjs`, and `mathbank-live/{server.mjs,lib/*.mjs,app/api/**}`.

## Regeneration procedure

1. Inspect `git status --short` and record `git rev-parse HEAD`.
2. Read the architecture-doc skill and source files above.
3. Generate the OpenAPI snapshot from source only:

   ```sh
   mathbank-rest/.venv/bin/python - <<'PY'
   import json, re
   from pathlib import Path
   from mathbank_rest.main import app
   schema = app.openapi()
   text = json.dumps(schema, sort_keys=True, indent=2)
   # Scan text for connection strings, API-key/password/secret-looking values, and provider keys before writing.
   Path('requirements/reference/openapi.json').write_text(text + '\n')
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
