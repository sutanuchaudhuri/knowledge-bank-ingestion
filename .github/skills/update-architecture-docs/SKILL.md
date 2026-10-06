---
name: update-architecture-docs
description: 'Refresh evergreen MathBank documentation from current implementation: Neo4j node/edge properties and directions, PostgreSQL tables/DDL/DML/relationships, and REST OpenAPI/Swagger contracts. Use when asked to update schema, graph, database or API reference documentation. Documentation-only; never migrate, ingest, publish graphs or call paid models.'
argument-hint: 'Optional scope: all (default), graph, postgres, rest; optional live verification with an explicit local/remote target'
---

# Evergreen MathBank Architecture Documentation

Every invocation performs a fresh implementation-grounded documentation
refresh. Do not treat prior conversation summaries, historical diagrams or
previous generated reference files as authoritative schema evidence.

## Contract and boundaries

- Default scope is **all**: graph, PostgreSQL and REST. If the user supplies a
  narrower scope, update its cross-links but do not claim full-system coverage.
- This skill updates documentation only. Never change application code,
  migrations, dependency manifests, configuration, credentials or runtime data.
- Never execute DDL/DML writes, migrations, ingestion, embeddings, graph
  publication, admin mutations, service restarts or paid model requests.
- Default evidence is checked-in implementation. Live database verification
  requires an explicit user-selected target; do not guess local vs Neon/Aura
  from a file that happens to exist. If requested but unavailable, record the
  verification gap and still complete source-derived documentation.
- Respect existing worktree edits. Do not revert or overwrite unrelated changes.
  Do not commit unless explicitly requested.
- Never copy `.env`, credentials, connection strings, learner records, session
  contents, provider error bodies or database row samples into documentation.
  Do not inspect or edit shell profiles. Use only schema metadata for live checks.
- Do not install dependencies or start services merely to generate documentation.
  Use existing tools/environments; disclose unavailable verification.

## Where documentation lives today

Use these as navigation and context, not proof that their content is current:

- [Database README](../../../mathbank-db/README.md):
  migration/ETL ownership and database operational guidance.
- [Graph README](../../../mathbank-graph/README.md):
  projection behavior, node/edge properties, review filtering and dated audits.
- [Database overview](../../../DATABASES.md): local/remote database boundaries.
- [Requirements index](../../../requirements/00_INDEX.md),
  [glossary](../../../requirements/17_DOMAIN_AND_TECHNICAL_GLOSSARY.md),
  [pipeline/retrieval requirements](../../../requirements/16_PIPELINE_JOB_CONSOLE_AND_HYBRID_RAG.md).
- [Historical architecture plans](../../../mathematics_tutor_db_plan/README.md):
  useful design intent, but distinguish implemented, planned and historical.
- FastAPI automatically serves `/docs`, `/redoc` and `/openapi.json`
  (normally at `http://127.0.0.1:8000`). These update with the **running
  application version**; a stale server can disagree with checked-in code.

## Persistent outputs when this skill is invoked

Reuse and refresh the following canonical reference files, creating them on
the first documentation-refresh invocation if absent:

| Output | Contents |
|---|---|
| `requirements/reference/README.md` | Navigation, authoritative sources, generation procedure, evidence/version coverage and drift limitations. |
| `requirements/reference/GRAPH_SCHEMA.md` | Every implemented label, node property, relationship type, endpoint pair, direction, edge property, constraint and projection rule. |
| `requirements/reference/POSTGRES_SCHEMA.md` | All application tables, columns/types/defaults/nullability, keys, relationships, indexes, checks, triggers/functions/views and migration ownership. |
| `requirements/reference/POSTGRES_DML.md` | Implemented reads/writes, conflict/idempotency rules, approval/audit effects, deletion behavior and safe parameterized examples. |
| `requirements/reference/REST_API.md` | Complete endpoint/security/request/response/error inventory and Swagger/OpenAPI access/version guidance. |
| `requirements/reference/openapi.json` | Deterministic source-generated OpenAPI snapshot, when generation succeeds without side effects. |

Add concise links to relevant existing READMEs, the requirements index and
glossary. Do not duplicate entire reference tables across several documents.
Preserve historical audits as dated observations rather than replacing them
with undated current facts. Only create outputs within the requested scope.

Each refreshed reference must identify:

1. Source revision (Git HEAD when available), whether relevant worktree changes
   were included, and files examined.
2. Evidence mode: source-derived, running API, or explicitly selected live
   schema; these are not interchangeable.
3. Verification date only for an actual observation, with UTC timezone.
4. Unavailable evidence, drift, uncertain defaults and unimplemented plans.

Avoid timestamp-only churn when source-derived content is unchanged.

## Procedure

### 1. Inspect and establish scope

Read the existing canonical references and relevant READMEs/index. Inspect
worktree status and available tooling. Inventory source files before editing;
batch independent reads. Follow definitions/callers directly rather than
delegating a single continuous schema trace.

Use these starting points, discovering newly added files rather than assuming
the current list is exhaustive:

| Surface | Implementation sources |
|---|---|
| Postgres DDL | `mathbank-db/sql/*.sql`, migration Makefile targets, any additional schema-creation SQL in Python/scripts. |
| Postgres DML | `mathbank-db/etl/`, ingestion importers, `mathbank-rest/src/mathbank_rest/db/`, teaching/review/mastery workers and actual query callers. |
| Agent session schema | `mathbank-agent/session_config.py`, `server.py`, installed ADK/SQLAlchemy model definitions/version if needed. Clearly distinguish framework-owned tables from project migrations. |
| Agent session link + transcripts | Project-owned `learner.agent_session_link` (`mathbank-db/sql/016_agent_session_link.sql`), `mathbank-rest/src/mathbank_rest/agent_transcripts.py`, `routers/agent_sessions.py`, web `app/api/agent/session/route.js`, `lib/agentIdentity.mjs`, `lib/conversationsProxy.mjs`, conversations pages. Document the logical (non-FK) link into `agent_sessions`, server-derived identity, ownership 404/409 rules, naive-UTC timestamp handling and student vs admin transcript visibility. |
| Browser regression | `mathbank-web/playwright.config.mjs`, `mathbank-web/e2e/*.spec.mjs` ([23](../../../requirements/23_E2E_REGRESSION_SUITE.md)). Read to confirm documented page/proxy routes and response shapes; do not edit specs from this skill. |
| Neo4j projection | `mathbank-graph/etl/project_from_postgres.py` and any other graph-writing code discovered in the workspace. |
| Graph read/UI contract | REST graph/pedagogy queries, `mathbank-web/lib/graphConfig.js`, `graphMetadata.mjs`, graph API routes and views. |
| REST contract | `mathbank-rest/src/mathbank_rest/main.py`, every registered router, Pydantic models/dependencies and endpoint implementation/tests. |
| Web/agent HTTP surfaces | Next.js proxy routes and ADK server configuration; document separately from the FastAPI OpenAPI inventory. |

### 2. Refresh the graph reference

Enumerate **every** implemented node label and relationship endpoint pair,
including corpus, skills, taxonomy and any actually implemented learner
projection. A relationship name alone is insufficient: `TESTS` with a Concept
target differs from `TESTS` with a Skill target.

For each node/property document name, value type, required/optional status,
identity/merge key, source table/column or calculation, and whether exposed
through REST/UI. Mark types inferred from code rather than enforced by Neo4j.
For each edge document:

- Source label -> relationship -> target label, precise semantic direction.
- Identity/merge key including role/type where relevant.
- Properties, provenance, review/approval fields and null handling.
- Exact normalization rules, including reversed `HAS_SUBCONCEPT` -> `PART_OF`.
- Projection ownership, reconciliation/removal behavior and constraints/indexes.
- Default review filtering and answer/solution visibility boundaries.

Distinguish supported schema from observed populated inventory. A sampled
graph cannot prove a label/property is unsupported. Zero visible edges may
mean no authored data, a filter, missing publication or unavailable observation.
Never invent attributes from UI display labels or planned diagrams.

### 3. Refresh PostgreSQL DDL and relationships

Reconstruct the final schema by applying migrations **conceptually in their
actual order**, including `ALTER`, dropped/replaced constraints, triggers,
extensions and indexes. Never execute migrations for documentation.

For each table list schema-qualified name, purpose, owner/migration, columns,
SQL type, default, nullable status, primary/unique keys, foreign keys and
ON DELETE/UPDATE actions. Also document:

- CHECK constraints, partial/expression indexes and required extensions.
- Views/materialized views, functions, triggers and schema grants if implemented.
- Join tables, composite keys, cardinality and nullable relationships.
- Logical UUID links without enforced foreign keys, labelled explicitly.
- Vector dimensions/model/index coupling and representation versioning.
- Approval triggers, human protection and audit/outbox behavior.
- `agent_sessions` framework-managed ownership/version and creation mechanism,
  and the project-owned `learner.agent_session_link` that maps students to it.

Do not equate schema existence with migration application on a target server.
Do not present a historic reference DDL file as the current composite schema.

### 4. Refresh DML behavior

Trace actual INSERT/UPDATE/DELETE/UPSERT/read paths and transaction boundaries.
For each operation family record caller, affected tables, scope/keys,
validation/authentication, conflict handling, audit/trigger effects, retry/
idempotency behavior and graph/vector follow-up work.

Cover canonical ingestion, classification import, skills/relationships,
human review, embeddings, pipeline jobs, attempts/mastery, agent sessions and
the agent-session link upsert / read-only transcript rebuild.
Distinguish append-only evidence from mutable caches and derived projections.
Explain automatic/human approval, rejected-record protection, cascade behavior
and cross-database non-atomicity using code evidence.

Examples are illustrative **documentation**, not execution instructions:
parameterized SQL with synthetic placeholders, clear read vs write labels,
and warnings for operator mutations. Do not manufacture DML for unsupported
operations or fill examples with real corpus/learner records.

### 5. Refresh REST and Swagger/OpenAPI

Inventory registered routes, including health/admin/learner/pedagogy/tutor,
not just files named `v1`. Record HTTP method/path, purpose, auth mechanism,
parameters/defaults/validation, request model, success model/status, documented
and implemented errors, pagination/filtering, and relevant side effects.

Generate OpenAPI from the checked-in FastAPI application using the repository's
existing REST interpreter and its normal import configuration, calling
`app.openapi()` without starting a server or executing endpoint handlers.
Configure the Python environment before executing Python. Check module-level
side effects first; do not bypass missing credentials with fake keys, change
runtime files, or trigger paid/network work just to import the application.
If generation is blocked, preserve the last snapshot, clearly mark it stale
and report the exact safe blocker; source-derived endpoint docs can still update.

When generation succeeds:

1. Validate the result has OpenAPI version, paths and schemas.
2. Scan examples/defaults/descriptions for secrets/private data before saving.
   If unsafe, do not persist the snapshot; report the source of the exposure
   without revealing it or changing application code in this docs-only task.
3. Write sorted, consistently formatted JSON using generation tooling.
4. Derive endpoint documentation from this snapshot and implementation.
5. Explain that Swagger is generated automatically, while the committed snapshot
   must be regenerated by this skill when code changes.

If a known running REST service is available, a read-only GET to its
`/openapi.json` may verify deployment drift. Treat it as a separate observation,
not a replacement for the source-derived snapshot. Do not restart stale services.
If OpenAPI omits response schemas/security/errors actually enforced by code,
document the contract gap explicitly instead of inventing OpenAPI guarantees.
Distinguish Next.js proxy endpoints and ADK routes from FastAPI-owned routes.

### 6. Optional live schema verification

Only for an explicitly requested target, use existing connection helpers and
read-only catalog queries (`information_schema`, `pg_catalog`, schema metadata
procedures or supported read-only Neo4j metadata queries). Never invoke
procedures that create/delete indexes or sample private property values.

Compare schema metadata against source expectations. Report missing migrations,
runtime-only objects, property sparsity and version differences separately.
Do not issue a raw schema dump into the repository without checking it for
secrets: function definitions, comments and defaults can embed sensitive data.
Graph observed property types are empirical, not formal constraints.
No live counts are necessary unless the user requests them; date and scope
any counts and never equate them with full pipeline completion.

### 7. Edit, verify and report

Use precise edits and preserve unrelated documentation. Do not rewrite all
historical design plans; add canonical links and flag conflicting current
claims in the directly affected navigation/operational docs.

Before declaring completion:

- Compare documented table inventory with reconstructed migration inventory,
  graph label/edge/property inventory with all projector paths, and API
  method/path inventory with registered OpenAPI routes.
- Verify endpoint directions, property spelling/case, nullability, defaults,
  composite identities, trigger effects and auth claims against implementation.
- Validate JSON snapshots, resolve local Markdown links, and check diffs for
  secrets, accidental source/config changes and whitespace errors.
- Confirm repeat invocation with unchanged evidence produces no substantive
  differences or duplicate sections.
- If creating/editing Mermaid diagrams, use the available syntax documentation,
  validator and preview tools. Otherwise use tables/text; diagrams are optional.
- Documentation-only updates do not require broad builds/tests or paid checks.
  Use existing documentation validation if present.
- Optional, only when the user confirms the local stack is already running:
  `make -C mathbank-web e2e` (Playwright, no paid model calls) is a read-mostly
  check that documented web pages/proxies still respond. Never run `e2e-llm`
  (paid) from this skill, and never start services to make it pass. Report the
  result as a separate observation, not as schema evidence.

Finish with links to refreshed references, a concise change summary, evidence
mode/coverage, any deployment drift and any blocked verification. Never claim
live schema parity when only source files were inspected.
