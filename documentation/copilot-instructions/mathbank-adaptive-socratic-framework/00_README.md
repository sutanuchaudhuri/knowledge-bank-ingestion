# MathBank Adaptive Learning Graph & Socratic Reasoning Framework (ALGS)
Version: design proposal 0.1 · 2026-10-24 · Status: NOT IMPLEMENTED

## Goal
A human-reviewed, Copilot-implementable framework where subject experts author reusable mathematical reasoning strategies and immutable adaptive learning workflows; Bedrock/AgentCore proposes among approved next activities; deterministic policy and MathBank REST control execution, persistence and disclosure.

## Non-negotiable boundaries
- `core.*` holds original mathematical sources. `knowledge.*` holds canonical concepts/skills/techniques. `pedagogy.solution_route_release` and `route_step` are the existing released mathematical execution layer. Do not replace them.
- Micro-course is composition/orchestration, interaction instances own deterministic visual evaluation, `learner.*` owns private learner evidence. Extend them; no competing quiz/runtime engine.
- MathBank REST remains the only direct application Postgres/Neo4j boundary. Agents and MCP call authorized REST tools. Private learner data never enters shared Neo4j.
- AI output is proposed, never mathematically certified; human attests mathematical and pedagogical quality separately. DRAFT → VALIDATED → HUMAN_REVIEWED → PUBLISHED; immutable publication and pinned attempts.
- Student pre-answer payload never contains answer, hidden predicate, future hints/steps, or answer-bearing visual assets.
- A new workflow graph is logical educational IR, not arbitrary user-provided ASL. Compiled Step Functions infrastructure is centrally reviewed and version-pinned.

## Read/order and accountable deliverables
| File | Human reviewer | Copilot deliverable |
|---|---|---|
| 01_BASELINE_AND_DECISIONS | Architect | Gap audit / ADRs |
| 02_DOMAIN_STRATEGIES | Math SME | Strategy registry and seed examples |
| 03_LEARNING_GRAPH | Data architect | Schema/graph migrations and projections |
| 04_ASSESSMENTS | Pedagogy SME | Activity contracts and evaluators |
| 05_WORKFLOW_IR | Product + architect | Typed authoring IR, compiler and simulator |
| 06_AWS_ORCHESTRATION | Cloud architect | CDK, ASL templates, task adapters |
| 07_AGENTS_AND_MCP | AI lead | Agent tools, structured outputs and policies |
| 08_REST_AND_SECURITY | API lead | REST/OpenAPI, auth, idempotency |
| 09_ADMIN_AND_STUDENT | UX lead | Workflow studio, stepper, previews |
| 10_SCENARIOS_AND_TESTS | QA + math SME | Golden end-to-end tests |
| 11_COPILOT_EXECUTION | Engineering lead | PR-by-PR build checklist |
| 12_SCHEMAS_EXAMPLES | Engineering lead | Example JSON and pseudo-ASL |

**Baseline:** repository `sutanuchaudhuri/knowledge-bank-ingestion` README; requirements 34, 36–43; `documentation/requirements/reference/{POSTGRES_SCHEMA.md,REST_API.md,GRAPH_LIVE_CATALOG.md}`; per-service README. Re-read live files before migration. Previous conversation's Loci 7.3 and Construction 8.1 discovery-first approach are candidate fixtures, not proof of deployment state.

## Collaboration rules
Human signs off on every ADR, schema migration, accepted mathematical fixture, route pedagogical rubric, access-control matrix and publication. Copilot may generate implementation in narrow PRs with tests; it must report exact files changed, migration reversibility, validation evidence, uncovered assumptions and deviations. Never mark a phase done from generated code alone. No production DB writes or paid inference without explicit operator authorization.
