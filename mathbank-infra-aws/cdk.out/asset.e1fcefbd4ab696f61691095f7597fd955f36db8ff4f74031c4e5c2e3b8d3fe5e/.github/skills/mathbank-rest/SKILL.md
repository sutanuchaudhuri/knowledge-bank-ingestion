---
name: mathbank-rest
description: 'Working in mathbank-rest: the FastAPI service and only direct database boundary (Postgres + Neo4j) in the MathBank repo. Use when adding/editing routers, service modules, or db/ query functions in mathbank-rest, or when asked about its REST API surface, auth, or migrations.'
argument-hint: 'Optional: router or service module name to focus on'
---

# mathbank-rest conventions

Full detail: [mathbank-rest/README.md](../../../mathbank-rest/README.md). This skill is the
quick-reference; read the README for architecture/data-model diagrams before larger changes.

## Non-negotiables

- This is the **only** project allowed to connect to Postgres/Neo4j directly. Every other service
  (`mathbank-web`, `mathbank-live`, `mathbank-agent`) reaches data through this REST API.
- Every router (`routers/*.py`) delegates to a service module — never embed raw SQL in a router.
- JSON literals in SQLAlchemy `text()` must be bound parameters (`CAST(:policy AS jsonb)`), never
  inlined — inlining misparses `{"correct_index":0}`'s `:0` as a bind parameter.
- `X-Admin-Api-Key` gates all `/v1/admin/*` routes; learner JWT gates learner-owned routes; most of
  `/v1` is anonymous. Visibility in OpenAPI is not a security boundary — every sensitive tool/route
  must independently re-check auth.
- Never return an answer key (`correctness_policy`) before a student has answered — a known,
  tracked gap exists here (doc 43 §7.1); don't introduce a new one.

## Before changing anything

1. Run `make test` (fast) or `ROUTE_DB_TESTS=1 make test` (full, live-DB) first to get a clean
   baseline — 68 test files.
2. Check [documentation/requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md](../../../documentation/requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md)
   before adding a new endpoint — it documents the current tagging/documentation/enum conventions
   (or their absence) you should follow or fix, not repeat.
3. New quiz/activity endpoints: see [doc 46](../../../documentation/requirements/46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md)
   — `attach_activity`/`attach_learning_item` service functions already exist and are fully
   validated; wire a router to them rather than re-implementing the validation.
