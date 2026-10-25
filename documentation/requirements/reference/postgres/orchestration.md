# Socratic draft orchestration schema

## Evidence and scope

Source revision `a0041e2bc53818b9d06e67d836a5b6d701872fb0` plus relevant worktree
changes: [migration 053](../../../../mathbank-db/sql/053_socratic_drafts.sql),
[service](../../../../mathbank-rest/src/mathbank_rest/socratic_service.py),
[strict IR](../../../../mathbank-rest/src/mathbank_rest/socratic_contracts.py)
and [router](../../../../mathbank-rest/src/mathbank_rest/routers/socratic.py).
Migration 053 was applied to the explicitly authorized REST-configured **Neon**
target and repeated successfully on **2026-10-25**. Read-only scoped metadata
observed **2026-10-25 UTC** confirmed the four column sets below,
61 constraints (including NOT NULL metadata) and three application triggers.
This is not a refresh of the historical complete database/graph catalogs.

Only draft authoring is implemented. No preview/evaluation/model job, approval,
release, learner-progress or operational activation tables are implied.
Twenty seeded strategies across eight domains are **DRAFT candidates**, not
mathematically/pedagogically approved policies.

Unless marked nullable, columns are NOT NULL. All timestamps use `timestamptz`.
Foreign keys use default NO ACTION for updates; deletion is explicitly
RESTRICT where noted, otherwise default NO ACTION. No new extension or
database grants are introduced.

## `orchestration.socratic_strategy`

| Column | Type/default/constraints |
|---|---|
| `code` | text PK |
| `domain`, `label`, `provenance` | text; seed provenance explicitly identifies unreviewed candidates |
| `status` | text default `DRAFT`; CHECK equals `DRAFT` |
| `phases` | jsonb; CHECK array |

Rows are immutable through a BEFORE UPDATE OR DELETE trigger.

## `orchestration.socratic_workflow`

| Column | Type/default/constraints |
|---|---|
| `workflow_id` | uuid PK, application-generated |
| `owner_id` | text, length 1–200; server-derived staff subject or namespaced local/synthetic test actor |
| `title` | text, trimmed length 1–200 |
| `domain` | text, service validates against the candidate registry |
| `revision` | integer, positive |
| `content_hash` | text, 64 lowercase hexadecimal characters |
| `prototype_only` | boolean default true, CHECK true |
| `created_at`, `updated_at` | default `clock_timestamp()` |

Index `socratic_workflow_owner_idx(owner_id, updated_at DESC, workflow_id)`
supports owned pagination. Composite FK `(workflow_id, revision, content_hash)`
references the exact current revision; **DEFERRABLE INITIALLY DEFERRED** permits
atomic workflow creation and revision append. Workflow identity/title/domain
are not editable through the current API; saves update only the current
revision/hash/timestamp. There is no deletion endpoint.

## `orchestration.socratic_revision`

| Column | Type/default/constraints |
|---|---|
| `workflow_id` | uuid FK workflow, ON DELETE RESTRICT |
| `revision` | positive integer; composite PK `(workflow_id, revision)` |
| `content_hash` | text, 64 lowercase hex; UNIQUE `(workflow_id, revision, content_hash)` |
| `author_id` | text, server-derived |
| `strategy_code` | text FK candidate strategy |
| `program` | jsonb object with explicit `schema_version = socratic.prototype.v1`; missing version rejected, not SQL-NULL accepted |
| `dependencies` | jsonb object; frozen source/strategy hashes and provenance |
| `problem_id` | nullable uuid FK `core.problem`, ON DELETE RESTRICT |
| `solution_id` | nullable uuid FK `core.solution`, ON DELETE RESTRICT |
| `solution_revision` | nullable positive integer |
| `route_release_id` | nullable uuid FK `pedagogy.solution_route_release`, ON DELETE RESTRICT |
| `created_at` | default `clock_timestamp()` |

Checks require solution ID/revision together, a problem for any solution,
and a solution for any route. The solution's **revision number is a logical
version pin**, not a composite FK into a historical solution archive. REST
checks its current exact revision, problem membership, selected route's
solution/problem/published status and content hashes while holding source
rows FOR SHARE. A published route's source hash must equal the existing route
compiler's hash of the current solution/statement/verification state, not
merely share its solution UUID. It snapshots hashes, not private solution bodies.
Same-source changed content must be explicitly reselected; a save cannot
silently adopt new canonical mathematics.

A BEFORE UPDATE OR DELETE trigger rejects revision modification.
`orchestration.socratic_immutable()` raises SQLSTATE `23514`; the same
function protects strategies and command receipts.

## `orchestration.socratic_command`

| Column | Type/default/constraints |
|---|---|
| `owner_id`, `operation` | text; operation is `CREATE` or `UPDATE:<workflow UUID>` in the service |
| `idempotency_key` | text, length 1–128 |
| `request_hash` | text, 64 lowercase hex |
| `workflow_id` | uuid FK workflow, ON DELETE RESTRICT |
| `revision` | integer; composite FK `(workflow_id, revision)` to revision, ON DELETE RESTRICT |
| `created_at` | default `clock_timestamp()` |

PK `(owner_id, operation, idempotency_key)` scopes replay to verified identity
and operation. BEFORE UPDATE OR DELETE rejects mutation.

## Transactions, access and acceptance

REST is the only runtime database boundary. Every route requires a verified
staff session and `author` capability; every mutation also requires the exact
trusted Origin/current CSRF. Nonowned and missing drafts both return 404.
Create/update require `Idempotency-Key`; update additionally requires
`expected_hash`. A transaction-level advisory lock serializes duplicate
commands; workflow row locking plus a fresh read serializes competing saves.
Same command/input replays its exact historical response; different input
under the same key or stale expected hash returns 409.

Workflow/revision/receipt, existing `audit.action_log`, and existing
`pipeline.outbox_event` writes commit together. Injected outbox failure was
verified to roll back the entire save. The new event is
`SOCRATIC_DRAFT_SAVED`; it is **not** an agent job or graph/vector publication.
No consumer, canonical edit, learner update, SQL delete or AWS model call is
introduced by this service.

Structural validation checks dependency freshness/reachability and explicitly
reports `DRAFT_STRUCTURE_ONLY`; it is not a complete workflow compiler,
loop-safety proof, mathematical attestation or publication approval.

Selected-target tests verify transactions, owner isolation, sources, immutable
history, replay, API cookies/CSRF and stale saves. Ordinary fixtures roll back.
A separately opted-in real two-connection concurrency check retained **one
labeled synthetic workflow with two revisions**, two command receipts and
matching audit/outbox evidence. No canonical or learner record was written.
See the [execution/handoff ledger](../../67_SOCRATIC_IMPLEMENTATION_HANDOFF.md)
for commands, counts and hosted acceptance limits.
