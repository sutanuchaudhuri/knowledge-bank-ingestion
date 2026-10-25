# 11 — Human + GitHub Copilot execution protocol

## Workflow
Human architect owns ADRs; mathematical SME owns correctness and discovery rubric; pedagogy SME owns misconceptions/hints and AR questions; security owner owns access matrix; developer pairs with Copilot on one bounded PR at a time. Copilot reads 00 + the specific file + actual current README/source/schema tests before changing code. Every PR must state what is existing vs new, exact migration and files, commands run, evidence and known gaps. Require real reviewers and no production secrets/calls.

## Work packages and acceptance
WP00 Baseline inventory: generate `CURRENT_STATE.md` with exact migration/table/API/graph inventory and SHA, status matrix and ADR sign-offs. READ ONLY.
WP01 Typed IR & domain catalog: JSON Schemas, seed 8 domains/20 strategies, parent composition, unit validation fixtures. No runtime writes.
WP02 PostgreSQL migrations: additive strategy, workflow and learner tables; immutability, access constraints, event/outbox/CAS tests and rollback plan. No source overwrite.
WP03 Assessments: AR1–AR5, free form/symbolic/geometry adapter, server-side safe payload contract and wrong-answer evidence boundaries; golden fixtures.
WP04 Admin authoring: catalog, focused editor, node insert/delete/split/merge/reorder/diff, AI patch proposals and audit. Student preview uses actual safe runtime.
WP05 Compiler: IR validator/reachability/bounded loops/refs/hashes; deterministic rules and fallback; mock AWS compilation test.
WP06 REST + auth: admin/student/internal endpoints, Pydantic/OpenAPI, ownership, idempotency, CAS and capability-based permissions.
WP07 Agent tools: separate draft authoring/critic/student decision policies, scoped REST-backed MCP, structured decision output, no publish/mutate mastery tools.
WP08 Step Functions/AgentCore: CDK, Standard authoring approval, student short transition execution, region/API support check, retries and fallback.
WP09 Neo4j projector: published-only, additive, scoped and idempotent with parity/lag metrics.
WP10 Web UX & gamification: domain-specific student stepper, mixed assessment renderer, badges optional, accessibility.
WP11 Simulations/security: strong/novice/guessing student suites; answer-leak property checks; reviewer acceptance.
WP12 Pilot and rollout: Construction 8.1, Loci 7.3, Stars/Bars and Probability; feature flag/shadow decisions, compare policy with Bedrock suggestion, rollback, human sign-off.

## Copyable Copilot task template
```
Read 00_README.md, 01_BASELINE_AND_DECISIONS.md, and the named WP document. Inspect the current repository schema, API, migrations, service README and tests. First report existing/partial/missing capabilities and exact touched files. Implement only WP__ in a feature branch. Preserve canonical table/route/graph ownership. Add automated tests for positive, invalid, concurrency, leakage, authorization and rollback cases. Do not use paid APIs, edit remote DBs, publish content, change IAM or run deployment unless separately authorized. Return: diff summary, migration plan, commands/results, sample sanitized request/response, remaining gaps, questions requiring human sign-off. Never mark a feature delivered unless tests actually ran.
```

## Human PR checklist
- [ ] Mathematical source/claim checked
- [ ] Correct teaching process for mathematical domain/technique
- [ ] No future step/answer leakage in payload, diagrams, accessibility text
- [ ] Existing REST/DB/graph boundaries kept
- [ ] Reviewer identity and exact hash pinned
- [ ] Invalid/alternative learner paths tested
- [ ] AWS cost, region, retry and fallback documented
- [ ] All outputs and docs labeled delivered/proposed accurately
