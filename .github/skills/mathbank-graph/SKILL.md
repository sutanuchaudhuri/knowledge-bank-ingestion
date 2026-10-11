---
name: mathbank-graph
description: 'Working in mathbank-graph: the Neo4j projection ETL (project_from_postgres.py, project_textbook_steps.py). Use when editing a projector script or asked about graph node/relationship shapes.'
argument-hint: 'Optional: projector script name to focus on'
---

# mathbank-graph conventions

Full detail: [mathbank-graph/README.md](../../../mathbank-graph/README.md). The authoritative graph
reference is [documentation/requirements/reference/GRAPH_SCHEMA.md](../../../documentation/requirements/reference/GRAPH_SCHEMA.md)
(and the dated live-catalog appendix in the same folder) — regenerate it (via the
**update-architecture-docs** skill) after a schema change rather than hand-maintaining prose here.

## Non-negotiables

- Neo4j is **derived and rebuildable**, never canonical — PostgreSQL always wins if the two
  disagree; re-project, don't hand-edit the graph.
- Every node MERGEs on a PostgreSQL-sourced UUID as `canonical_id` — this is what makes re-running
  a projector idempotent; never introduce a node keyed on anything else.
- **Never project learner-specific evidence** (misconception/mastery state) into this graph — it
  must stay private PostgreSQL state. This is a hard, repeatedly-stated rule across multiple
  requirements docs (40/42/44/49), not a style preference.
- `mathbank-rest`'s `db/graph.py` only *reads* from this Neo4j instance for structural projections
  — all writes go through this project's ETL scripts, keeping graph-mutation to one place.

## Before changing anything

1. `mathbank-rest/.venv/bin/python -m pytest -q mathbank-graph/tests` (the Makefile's own `test`
   target is a Neo4j connectivity check, not this pytest suite — run both).
2. `make project-remote`/`textbook-graph-dry-run-remote` (via `mathbank-db`) before any real write
   against the shared remote AuraDB target.
3. Two relationship types are explicitly marked not-yet-implemented in the textbook projector:
   `SolutionStep-[:USES_TECHNIQUE]->Technique` (`NYI-3`) and `LearningItem-[:TARGETS_CONCEPT/
   TARGETS_SUBCONCEPT]` (`NYI-ATB-7`) — don't assume they're already wired.

## Known pitfalls (confirmed live, requirements/50)

- **Never interrupt `mathbank_rest.route_projection.project()`/`_project()` once started
  against the remote AuraDB target.** Its delete-then-recreate cycle commits **per batch**
  (one transaction per ~500-row chunk, iterating node labels then each relationship-type
  shape one at a time) — it is **not** one atomic transaction. Stopping it partway through
  (impatience, a dropped connection, a killed shell) leaves the delete already committed and
  only *some* relationship types re-created, silently zeroing out the rest until the exact
  same call is re-run **to full, undisturbed completion**. Launch it as a detached/`nohup`
  background process up front so an impatient interruption can't happen. Full incident and
  recovery: [GOTCHAS.md §23](../../../documentation/GOTCHAS.md).
- **A companion projector's edges are NOT protected by giving them their own distinct
  `projection_kind` tag — confirmed false, the hard way** (requirements/51 ENR-1/ENR-4): a
  routine, fully-uninterrupted `project()` re-run silently zeroed a companion script's
  82,019 `RELATES_TO` edges from 82,019 to 0, because `_project()`'s node cleanup is
  `MATCH (n) WHERE n.projection_kind=$kind DETACH DELETE n` — `DETACH DELETE` on a *node*
  removes every relationship attached to it regardless of **that relationship's own**
  `projection_kind`. Any edge touching a node this projector manages (`RouteRelease`,
  `RouteStep`, `Claim`, `Misconception`, `TheoryItem`, `LearningItem`) will be destroyed on
  every rebuild unless `_project()` itself is the one recreating it. **Do not write a
  separate companion script against any of these labels — fold the projection directly into
  `route_projection.py`'s `metadata()`/`_project()` instead.** Full incident and fix:
  [GOTCHAS.md §24](../../../documentation/GOTCHAS.md).
- ~~The AuraDB free/low-memory tier can raise `Neo.TransientError.General.MemoryPoolOutOfMemoryError`
  on `project()`'s single unbatched bulk `DELETE` once the `tutoring_routes` layer passes
  roughly 1M relationships. That specific failure mode *does* roll back cleanly (confirmed:
  node/edge counts unchanged) — it is the mid-run-interruption case above that is dangerous,
  not this one.~~ **Fixed** (requirements/51 ENR-2, hit live once edges passed 1.55M): the
  unbatched `DELETE`/`DETACH DELETE` statements now use Neo4j 5's `CALL (var) { ... } IN
  TRANSACTIONS OF N ROWS`, called via plain `session.run()` (not `execute_write()` — `IN
  TRANSACTIONS` manages its own transaction boundaries and cannot nest inside one). Full
  incident and fix: [GOTCHAS.md §25](../../../documentation/GOTCHAS.md). If this threshold
  is hit again at a much larger edge count, lower the `ROWS` batch size, don't raise it.
- **A `project()` call that raises `psycopg.errors.AdminShutdown` on `pg_advisory_unlock` at
  the very end did not necessarily fail** — confirmed live twice: Neon transiently killed
  only the dedicated advisory-lock connection, after the real rebuild had already completed
  and been recorded `COMPLETED` in `pipeline.graph_projection`. Check that table
  (`ORDER BY started_at DESC`) before assuming a traceback means lost work.
- **Do not add Neo4j-native vector indexes / enable Aura's "vector-optimized configuration"**
  without a specific, demonstrated need for a single query that combines ANN vector search
  *with* graph traversal. This project's embedding store is Postgres/pgvector
  (`search.embedding`, `artifact_runtime.artifact_embedding`), and requirements/51's ENR-2
  explicitly extends that same store, not a Neo4j one — see that document's "why not Neo4j
  vector indexes" note before reopening this.

## Available tooling

- `.agents/skills/neo4j-*` — the official Neo4j agent skills (installed via `npx skills add
  https://github.com/neo4j-contrib/neo4j-skills`), including `neo4j-gds-skill` (Graph Data
  Science — community detection, PageRank, similarity algorithms; directly relevant to doc
  50 §8's "what would make this graph useful for clustering" research report),
  `neo4j-query-tuning-skill`, `neo4j-cypher-skill`, and `neo4j-modeling-skill`. Consult these
  before hand-rolling a Cypher pattern this project hasn't needed before.
- `neo4j-cli` (installed via `pipx install neo4j-cli --backend pip`) has this instance's
  credentials registered under the name `MathTutor-Active` (`neo4j-cli credential dbms
  list`), pointed at the same live AuraDB instance (`8ff1398e.databases.neo4j.io`) this
  project's own Python driver connects to — confirmed via `mathbank_rest.config.settings`.
  Note: `mathbank-graph/Neo4j-7b2bff52-Created-2026-10-04.txt` is a **stale, unused**
  Aura-exported credentials file for a *different*, no-longer-active instance — don't reuse
  it for anything; the live instance's credentials live in `mathbank-graph/remote.env`.
