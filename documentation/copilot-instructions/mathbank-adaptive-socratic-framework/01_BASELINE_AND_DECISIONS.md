# 01 — Repository reconciliation and architecture decisions

## Mandatory read-only baseline audit
1. Inspect actual migration order, table definitions and triggers in `mathbank-db/sql/` and generated `reference/postgres/`; enumerate `core.solution_step`, `pedagogy.solution_step`, `pedagogy.solution_route_release`, `pedagogy.route_step`, `pedagogy.route_step_hint`, `solution_step_requirement`, `learner.route_attempt`, `activity.*`, `visual.*`, outbox and graph projection ownership. Do not assume illustrative table names in old docs exist.
2. Inspect `mathbank-rest` routers, admin auth, learner bearer ownership, OpenAPI, agent tools and `mathbank-mcp-competitions` actual tool names; record current tests and branch SHA.
3. Record delivered / partial / scaffolded / proposed separately. Current documents explicitly describe unfinished universal atomic authoring and parts of interaction template library; do not relabel aspirations as existing services.
4. Confirm current PostgreSQL version/target rather than assuming the root README's historical local PG16 notes reflect the active local snapshot. Never read or display secrets.

## ADR-01 canonical ownership
Mathematics source and released mathematical route are independent from the *instructional discovery program*. A single released solution route may bind to multiple reviewed Socratic strategy versions; multiple branches can converge on same reviewed claim through formally or human-verified equivalence.

## ADR-02 release graph
Author drafts freely, but release is immutable and content-addressed. Edits, split, merge, delete create a new version, rewrite dependencies transactionally, retain audit/tombstones, never migrate current learner executions silently.

## ADR-03 workflow engine
Persist educational workflow IR and learner state in Postgres. Compile an approved IR into a centrally managed family of Step Functions definitions/tasks (or one versioned generic transition machine); do not deploy one arbitrary administrator-supplied state machine. Short transition executions; avoid waiting during student idle time. Standard workflows for human authoring approvals. Every transition commit uses optimistic concurrency and idempotency.

## ADR-04 AI authority
Deterministic rules run first. Candidate list generated server-side. AgentCore/Bedrock reasons over minimal evidence and returns proposed node ID/reason/evidence references; REST validates eligibility; unsupported output invokes approved fallback. Neither model nor client grades exact math authoritatively, alters mastery, publishes, reveals hidden keys or creates live branches.

## ADR-05 graph
Shared Neo4j has canonical and published structural projections only; no private answer, event, student, mastery or misconception-confidence edges. Projection is rebuildable, additive and ownership-scoped.

## ADR-06 assessments
Reuse existing `activity.*`/`pedagogy.learning_item`/interaction runtime. Extend schemas for structured Assertion–Reason, free form, numerical and geometric response contracts; avoid duplicate scoring state.

## ADR-07 telemetry/privacy
Record source hashes, model/prompt/tool versions, selected candidate set, validation outcome, fallback, attempt-owned pseudonymous IDs, and trace ID. Minimize sensitive context shared with Bedrock, set retention and access policies, no raw private data in shared logs/graph.

## Decision register for human signature
- [ ] Choose canonical PK names after schema inventory
- [ ] Approve authoring roles and independent reviewer responsibilities
- [ ] Choose generic Step Functions interpreter vs compiled per-release state machine after scaling/cost test
- [ ] Select supported AgentCore integration and regions (harness integration currently preview; SDK runtime integration alternative)
- [ ] Approve learner privacy/age and data retention policy
- [ ] Approve initial reference strategies and mathematics fixtures
