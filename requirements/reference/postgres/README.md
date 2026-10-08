# Complete PostgreSQL catalog and access index

Observed **2026-10-08T01:57:54.421824+00:00** on the user-selected **REST-configured PostgreSQL** target.
Source revision `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7` plus implementation worktree changes.
PostgreSQL `18.6 (4e955f5)`. Metadata only; no corpus, learner, credential or session row values were read.
No migrations, grants, models, indexing, publication, service restarts or application code changes were performed.

This catalog supersedes old condensed column inventories for this selected deployment. It includes every
non-system schema and relation visible to the configured role. PostgreSQL internal `pg_*` and
`information_schema` objects are server-owned metadata, not application tables, and are excluded.
A table's existence does not prove populated content, correct mathematics, application ownership or a working UI.

Incremental full-corpus migration source updates the compiler run/job sections
in [pedagogy](pedagogy.md): uncapped positive cohort size, frozen bulk approval
identity, QUEUED jobs and persisted safe validation diagnostics. These later
source-derived changes are distinguished from the timestamped catalog above;
see [requirement 39](../../39_PRECOMPILED_TUTORING_ROUTES.md) for operational results.

## Schema index

| Schema | Tables | Views | Sequences | Purpose and access |
|---|---:|---:|---:|---|
| [activity](activity.md) | 3 | 0 | 0 | Live activities and responses; Live activity start/respond/close/result routes; `/v1/live/*`, mathbank-live classroom widgets. |
| [agent_sessions](agent_sessions.md) | 5 | 0 | 0 | ADK-managed framework storage; ADK agent service plus `/v1/learner/agent-sessions/*` and `/v1/admin/agent-sessions/*` transcript reads; logical learner.agent_session_link, no cross-schema FK. |
| [analytics](analytics.md) | 1 | 0 | 0 | Derived learner aggregates; Outbox worker internal access; no dedicated direct-table public REST endpoint. |
| [artifact_runtime](artifact_runtime.md) | 11 | 0 | 0 | Declarative artifact bundles; `/v1/artifacts/*`; staff generate/publish/index; authenticated preview/read/requests with route-specific ownership. |
| [attempt_media](attempt_media.md) | 9 | 4 | 0 | Private learner evidence; `/v1/attempt-media/*`; JWT ownership, staff review; private bytes via authenticated handlers. |
| [audit](audit.md) | 0 | 0 | 0 | Reserved application namespace; No table/API access to document; audits currently live in knowledge/ingest/learner/live. |
| [auth](auth.md) | 0 | 0 | 0 | Observed empty namespace; No checked-in MathBank access found. Do not infer an authentication implementation from its name. |
| [authoring](authoring.md) | 5 | 0 | 1 | Versioned presentation authoring; `/v1/authoring/*`; shared admin API key. This is not a canonical atomic-step editor. |
| [core](core.md) | 7 | 0 | 0 | Canonical corpus; Public corpus `/v1/problems`, `/v1/competitions`; admin corpus/import/textbook routes; private tutor reference reads. |
| [geometry_scene](geometry_scene.md) | 4 | 0 | 0 | Private geometry scenes; `/v1/geometry-scenes/*`; learner JWT ownership or explicit staff operations. |
| [ingest](ingest.md) | 8 | 0 | 4 | Staging and human review; `/v1/admin/imports/*`, `/v1/admin/corpus/*`; import CLI. Shared admin key, browser signed admin session. |
| [knowledge](knowledge.md) | 15 | 0 | 0 | Canonical reviewed teaching metadata; Corpus filters/search, `/v1/concepts`, `/v1/techniques`, `/v1/tutor/*`, `/v1/admin/pedagogy/*`; enrichment/projector jobs. |
| [learner](learner.md) | 11 | 0 | 0 | Authenticated learner data; `/v1/learner/*`, `/v1/students/{student_id}/problems/{problem_ref}/attempts`, `/v1/attempts/*`; JWT ownership checks. |
| [live](live.md) | 7 | 0 | 0 | Live teaching orchestration; `/v1/live/*` through the mathbank-live socket gateway; staff commands and session-scoped access. |
| [neon_auth](neon_auth.md) | 9 | 0 | 0 | Provider-managed authentication; No checked-in MathBank REST consumer found. Current learner JWT/shared admin login does not thereby use Neon Auth. |
| [pedagogy](pedagogy.md) | 30 | 0 | 0 | Imported steps and released instructional routes; `/v1/admin/textbooks/*`, `/v1/admin/tutoring-routes/*`, `/v1/tutor/*`; source compiler and metadata projector. |
| [pipeline](pipeline.md) | 7 | 0 | 0 | Operational work and publications; `/v1/admin/pipeline/*`, `/v1/admin/papers`, `/v1/admin/imports/projection-requests`; CLI workers/projectors. |
| [public](public.md) | 0 | 0 | 0 | Default/extension namespace; Extension functions/operators are used indirectly by UUID, trigram and vector operations. |
| [search](search.md) | 7 | 0 | 0 | Derived search representations; `/v1/search/*`, similar-step and recovery retrieval; explicit corpus/step embedding jobs. |
| [tutor](tutor.md) | 1 | 0 | 0 | Durable step-runtime state; `/v1/attempts/*`; step/recovery runtime functions, scoped by JWT-owned attempt. |
| [visual](visual.md) | 3 | 0 | 0 | Declarative widget registry/state; `/v1/widgets/*`, live widget operations; stored-spec mutations are admin-only. No step-widget attachment REST resource. |

## Source/deployment reconciliation

Project SQL through 026 plus packaged REST migrations declare **129 project tables**; the selected deployment exposes **143 tables**.
Missing declared tables: **0**. Additional tables: **14**, explicitly listed below.
This comparison checks relation identities and column-name sets, including dynamic approval columns in migration 008.
It is not a PostgreSQL DDL interpreter or a claim that every type/default/constraint exactly matches source:
the live per-table catalog above documents those details independently.

- Deployment/framework table: `agent_sessions.adk_internal_metadata`.
- Deployment/framework table: `agent_sessions.app_states`.
- Deployment/framework table: `agent_sessions.events`.
- Deployment/framework table: `agent_sessions.sessions`.
- Deployment/framework table: `agent_sessions.user_states`.
- Deployment/framework table: `neon_auth.account`.
- Deployment/framework table: `neon_auth.invitation`.
- Deployment/framework table: `neon_auth.jwks`.
- Deployment/framework table: `neon_auth.member`.
- Deployment/framework table: `neon_auth.organization`.
- Deployment/framework table: `neon_auth.project_config`.
- Deployment/framework table: `neon_auth.session`.
- Deployment/framework table: `neon_auth.user`.
- Deployment/framework table: `neon_auth.verification`.

### Column-name differences

No column-name differences for source-declared project tables.

## Installed extensions

| Extension | Observed version |
|---|---|
| `pg_session_jwt` | `0.5.0` |
| `pg_trgm` | `1.6` |
| `plpgsql` | `1.0` |
| `vector` | `0.8.6` |

## Coverage and boundaries

- Every observed non-system schema has a page; every table/view has purpose, ownership, all columns, constraints, indexes, triggers, incoming FKs and access evidence.
- Empty namespaces are documented rather than silently omitted. Sequences are listed without reading sequence values.
- ADK and Neon Auth objects are explicitly separated from project migrations and learner account APIs.
- Grant metadata is role-redacted; no credentials, auth tokens, session JSON, private evidence or corpus row samples are exported.
- System catalogs, cluster-global roles, other databases/branches and targets not selected by the user are outside this inspection.
- Step generation/admin/widget behavior: [complete workflow and design boundary](../../36_STEP_GENERATOR_AND_AUTHORING.md).
- Full HTTP inventory: [REST reference](../REST_API.md); durable SQL side effects: [DML reference](../POSTGRES_DML.md).
