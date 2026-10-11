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
