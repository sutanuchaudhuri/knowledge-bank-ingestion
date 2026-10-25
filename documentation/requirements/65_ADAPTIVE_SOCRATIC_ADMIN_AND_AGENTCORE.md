# 65. Adaptive Socratic Studio: admin control plane and AgentCore requirements

## 0. Status, scope and evidence

| Field | Value |
|---|---|
| Status | **Requirements baseline; admin UI partial, staff sessions and owned draft/source persistence implemented. Additive migration 053 applied to authorized Neon; isolated API/SPA deployed. Successful Cognito staff/protected-cloud acceptance, evaluation and AgentCore/Step Functions remain pending.** |
| Date | 2026-10-25 |
| Request | Reconcile the complete adaptive Socratic framework and UI prototype; decide whether a root-level admin project is needed; specify AgentCore, Step Functions, Lambda and PostgreSQL integration. |
| Confirmed scope | Initial requirements/report phase expanded to implementation. User requires the supplied UI's features, styling and detail as a minimum; additions are allowed, feature removal is not. |
| Source baseline | Git `a0041e2bc53818b9d06e67d836a5b6d701872fb0`; the supplied framework directory was untracked. Source inspection only, not a deployment audit. |
| Companion | [66: AWS storage, database alternatives and cost report](66_AWS_STORAGE_DATABASE_COST_AND_MIGRATION_REPORT.md). Storage experiments are not prerequisites for the Studio pilot. |
| Implementation handoff | [67: dependency-ordered execution ledger](67_SOCRATIC_IMPLEMENTATION_HANDOFF.md), updated before work and after verification. Offline tests are not live acceptance. |

Staff authentication now also supports **explicit loopback-only local mode**
for non-AWS testing, with real local-browser cookie/CSRF/logout/replay checks
and a visible local identity warning. Existing Cognito configuration has been
privately reused and read-only prerequisites checked; successful real staff
Cognito login/revocation and protected hosted persistence remain separate
acceptance gates. The deployed isolated draft surface does not imply a
delivered tutor or model workflow.
See the [local testing runbook](../../mathbank-rest/README.md#interactive-non-aws-testing).

All thirteen Markdown documents in the
[framework pack](../copilot-instructions/mathbank-adaptive-socratic-framework/00_README.md),
the [prototype README](../copilot-instructions/mathbank-adaptive-socratic-framework/UI/README.md)
and the complete [HTML/JavaScript prototype](../copilot-instructions/mathbank-adaptive-socratic-framework/UI/index.html)
were read. The prototype has three views: Designer + Simulator, Rules by topic,
and Resource library. It uses localStorage, a phrase parser, browser-side answer
keys and a synthetic session. None is evidence of production persistence,
Bedrock integration, secure grading or authenticated student impersonation.

This document expands that pack into implementable requirements. It does not
certify its illustrative IDs, schema names, mathematics or AWS assumptions.
Sources retain their history; this document controls the proposed new work.

### 0.1 Reconciled baseline

| Surface | Source evidence and present capability | Gap for this project |
|---|---|---|
| Corpus and semantic ownership | [Core migration](../../mathbank-db/sql/001_schema.sql), [pedagogy migration](../../mathbank-db/sql/006_pedagogy.sql), [step-generator requirement](36_STEP_GENERATOR_AND_AUTHORING.md). Canonical problems/solutions, knowledge taxonomy and imported teaching steps exist. | No universal atomic authoring engine is established by this proposal. |
| Released mathematical routes | [Migration 026](../../mathbank-db/sql/026_tutoring_routes.sql), [route contracts](../../mathbank-rest/src/mathbank_rest/route_contracts.py), [route API](../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py), [requirement 39](39_PRECOMPILED_TUTORING_ROUTES.md). Reviewed snapshots, hints, route attempts and review/publish operations exist in source. | Discovery strategies, equivalence-approved alternative route joins and complete Socratic workflows are new. |
| Micro-course composition | [Migration 032](../../mathbank-db/sql/032_micro_course_platform.sql), [course service](../../mathbank-rest/src/mathbank_rest/micro_course_service.py), [course API](../../mathbank-rest/src/mathbank_rest/routers/micro_courses.py), [requirements 40](40_MICRO_COURSE_PLATFORM.md), [42](42_MICRO_COURSE_STUDENT_NAVIGATION.md), [43](43_ADMIN_MICRO_COURSE_AUTHORING_UI.md). Versioned states, bindings, transitions, enrollment and admin workspace exist. | Adaptive policy overlay must reuse composition; do not build a competing course engine. |
| Quiz bank and bindings | [Activity API](../../mathbank-rest/src/mathbank_rest/routers/admin_activities.py), [quiz service](../../mathbank-rest/src/mathbank_rest/quiz_service.py), [requirement 46](46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md). CRUD, canonical mappings and course bindings exist in source; doc 46 records earlier live acceptance. | Structured Assertion-Reason, domain-constrained symbolic and other new kinds need explicit adapters, schemas and fixtures. |
| Interaction and visuals | [Requirement 41](41_INTERACTION_TEMPLATE_LIBRARY.md), existing [widgets package](../../mathbank-widgets/README.md), [geometry engine](../../mathbank-geometry-engine/README.md). | Host-neutral template parity, no-leak serialization and accessible fallbacks require capability-by-capability verification. A target contract is not a delivered feature. |
| Learner safety and progress | [Security module](../../mathbank-rest/src/mathbank_rest/security.py), [route runtime](../../mathbank-rest/src/mathbank_rest/route_runtime.py), [outbox migration](../../mathbank-db/sql/012_step_runtime.sql). Bearer ownership, route versioning and transactional outbox patterns exist. | Workflow-specific CAS, replay, evidence policy and synthetic preview isolation need implementation. |
| Admin identity | Legacy REST uses shared `X-Admin-Api-Key`; some existing request bodies accept actor/reviewer strings. New [Socratic staff sessions](../../mathbank-rest/src/mathbank_rest/socratic_auth.py) use Cognito identity, fresh groups, distinct capabilities and scoped HttpOnly cookies; tested offline. | Real pool/client configuration, sign-in/revocation acceptance and enforcing capabilities on future review/publication routes remain release blockers. Legacy operations are not retroactively upgraded by this boundary. |
| Existing agents | [Tutor](../../mathbank-agent/README.md) uses ADK; [exam agent](../../mathbank-exam-agent/README.md) uses Strands; [exam requirement 64](64_AWS_BEDROCK_MOCK_EXAM_AGENT.md) records a historical OpenAI workaround. | User now reports AgentCore access. That does not independently verify a specific Bedrock model, region, quota or runtime permission. Do not silently change existing providers. |
| AWS infrastructure | Existing [CDK entrypoint](../../mathbank-infra-aws/app.py) is retained. Separate opt-in [Socratic entrypoint](../../mathbank-infra-aws/socratic_app.py) in the same project deploys only the draft API/SPA stack; see [67](67_SOCRATIC_IMPLEMENTATION_HANDOFF.md). | AgentCore/Step Functions integration is still pending; shared REST is not redeployed by this increment. |
| Graph | [Graph reference](reference/GRAPH_SCHEMA.md), [graph project](../../mathbank-graph/README.md). Rebuildable structural projections exist. | A published-only, ownership-scoped Socratic projection is new. No private learner graph is permitted. |

Original requirements-baseline inventory (before the Step 02 increment):
52 numbered root SQL migrations, through
[052](../../mathbank-db/sql/052_quiz_question_pool.sql); 27 REST router Python files;
77 REST test files. A literal scan found 205 distinct `CREATE TABLE` names in root
SQL and four in packaged REST migrations, **not a live catalog count**.
The [catalog](reference/postgres/README.md) is a dated observation and its
later quiz additions are source-only. Do not repeat old 35-migration/68-test
README counts or infer all 52 migrations are applied.
Step 02 adds migration 053's four draft tables; its scoped deployment evidence
is in [67](67_SOCRATIC_IMPLEMENTATION_HANDOFF.md) and the
[orchestration catalog](reference/postgres/orchestration.md), not a refresh of
every previous migration's application state.

Specific reconciliation points:

- `pedagogy.solution_route_release.route_release_id` is a UUID PK.
  `pedagogy.route_step` has composite PK `(route_release_id, step_index)` and
  a separate unique `step_id`. Hints and requirements use that composite FK.
  Do not invent a generic `route_step.id`.
- Imported `pedagogy.solution_step`, canonical `core.solution`, generated
  `pedagogy.route_step` and learner-written work have different ownership.
  Resolve any `core.solution_step` reference against source, not the pack.
- Existing activity kinds include `MCQ`, `MULTISELECT`, `NUMERIC`,
  `SHORT_RESPONSE`, `STEP_ORDERING`, `ERROR_DIAGNOSIS` and others.
  Proposed educational labels must map explicitly, not overwrite these enums.
- Requirements 45 and 46 now have **implemented** status sections despite stale
  index/README descriptions saying their entire API surfaces are missing.
- Historical PostgreSQL 16 descriptions coexist with a documented PostgreSQL
  18.6 local snapshot. Inspect the authorized target and extension versions
  before any migration; this pass made no database connection.

## 1. Product objective and non-goals

Subject experts author reusable, domain-specific discovery strategies, bind
approved mathematics and activities, inspect proposed AI changes, simulate
learner paths, attest correctness and pedagogy, and publish immutable learning
workflows. AgentCore may propose a next step only among server-approved choices.

The first production milestone is an **admin Studio with safe synthetic preview**,
not a replacement for every existing student screen.

Non-goals:

- Replacing canonical corpus, mathematical routes, quiz/exam generation,
  micro-course composition, interaction evaluation or mastery algorithms.
- Migrating Neon/Aura as part of implementing the Studio.
- Running arbitrary admin-authored ASL, SQL, Python, tool names or IAM.
- Automatically publishing AI mathematics, diagnosing a misconception from one
  wrong answer, or claiming learning efficacy from a simulator.
- Impersonating a real learner by passing an arbitrary `student_id`.

## 2. Project decision and service ownership

### ADR-SOC-01: create a separate admin frontend, not a separate database API

**Recommendation, awaiting architect approval:** create
`mathbank-socratic-admin` as an independent root-level React + Vite + TypeScript
admin SPA. Its scope is Socratic authoring, review, synthetic simulation and
operations, not migration of all existing admin pages.

Reasons:

1. The supplied prototype is a focused admin product; a separately released
   workspace avoids coupling it to the legacy tutor UI or ADK agent.
2. A static build can use the existing private S3 + CloudFront hosting pattern,
   avoiding another continuously running Next.js/Fargate process.
3. It can reuse shared widgets/math presentation and REST contracts while the
   existing micro-course workspace remains available.
4. TypeScript provides a typed consumer for the new strict workflow contracts;
   do not convert unrelated existing JavaScript applications.

Alternative: add a workspace inside `mathbank-web`. This creates fewer packages
and reuses its server-side session/proxy, but couples release/hosting and expands
an already broad admin product. Choose it instead if independent deployment is
not valuable; keep the backend contracts below unchanged.

### ADR-SOC-02: isolate agent code; keep one infrastructure project

Recommend a second new root package, `mathbank-socratic-agent`, for the
AgentCore-deployed Python agent entrypoint, prompts, structured outputs, policy
contracts, agent tests and thin Lambda task adapters. Use Strands as the initial
implementation candidate, reusing REST/MCP client patterns, **not** the existing
exam generator or its OpenAI workaround.

AgentCore hosts agent reasoning. Lambda hosts bounded orchestration adapters.
Neither package gets a PostgreSQL/Neo4j connection or an independent FastAPI
database service. AgentCore is not a synonym for a Lambda invoking Bedrock.

If a supported managed harness supplies all required reasoning/tool behavior,
this package holds the reviewed configuration, contracts and adapters instead
of deploying an unnecessary second custom runtime.

| Project | Responsibility |
|---|---|
| Proposed `mathbank-socratic-admin` | Static admin UI, generated REST types, synthetic preview shell, browser tests. |
| Proposed `mathbank-socratic-agent` | AgentCore reasoning/configuration, bounded role-specific tools, Lambda adapters, prompt/model provenance and offline evaluations. |
| Existing `mathbank-rest` | All runtime database access, authorization, drafts, validation, evaluation, policy eligibility, transaction/CAS, publication and safe materialization. |
| Existing `mathbank-db` | Additive migrations, DB invariants and migration tests. No new database project. |
| Existing `mathbank-graph` | Published structural projection, ownership-scoped reconciliation and lag/parity evidence. |
| Existing `mathbank-widgets` | Shared safe math, composer and interaction rendering; fix necessary compatibility here rather than copying renderers. |
| Existing `mathbank-web` | Later student workflow host and a link to the Studio; existing admin/student routes remain functional. |
| Existing `mathbank-mcp-competitions` | Reuse canonical retrieval; add scoped Gateway targets for Socratic tools rather than immediately creating another MCP service. |
| Existing `mathbank-infra-aws` | **Only CDK app**: proposed Socratic hosting/orchestration/AgentCore resources, IAM, alarms and outputs. |

Future package deliverables, **not created in this documentation pass**:

```text
mathbank-socratic-admin/
  README.md           purpose, architecture, auth, local setup, tests, deploy boundary
  package.json        existing repository package-manager conventions
  src/                catalog, rules, designer, review, operations, preview
  tests/
mathbank-socratic-agent/
  README.md           agents vs Lambda, tools, budgets, local stubs, live opt-in
  pyproject.toml
  src/                contracts, agent entrypoint/config, REST client, task adapters
  tests/
mathbank-infra-aws/stacks/
  socratic_*          proposed additions to the existing CDK app
```

Each new deployable needs its own README, install/test/build commands, versioned
environment example without secrets, root command delegation and skill reference.
Choose a nonconflicting local port at implementation; no port is reserved here.
Do not create empty directories/README-only projects and label them implemented.

## 3. Admin information architecture and prototype traceability

The Studio must follow [design requirement 30](30_MODERN_UI_DESIGN_SYSTEM.md):
wide low-clutter workspace, Inter, shared tokens/icons, breadcrumbs, paginated
catalog/master-detail, focused inspector, keyboard navigation and KaTeX math.
Do not transplant the prototype's large inline script or its grading logic.

**Feature-preservation rule:** the supplied
[UI](../copilot-instructions/mathbank-adaptive-socratic-framework/UI/README.md)
is an acceptance floor, not permission to replace it with a reduced form.
Retain all three views, detailed annotated rule cards, editable natural-language
proposal review, map/simulator layout, activity cards, answer/hint interactions,
restart/reset and routing traces. Schemas and REST contracts must expand to
support those interactions; a narrow initial schema must not redefine them out
of scope. Move insecure execution to REST/AgentCore while preserving the UI
capability. Safety changes (synthetic identity, explicit preview-from-node,
server evaluation, no local phrase-parser fallback) do not waive features.

The current [frontend](../../mathbank-socratic-admin/README.md) restores the
two-column desktop layout, dark token-based shell, dotted map, annotated rules
in both views, editable proposal drawer, resource cards, current safe-activity
responses, hints/reveal, branch highlighting and decision history. Its
[typed contracts](../../mathbank-socratic-admin/src/contracts.ts) include the
full node vocabulary and additive public preview fields. They are frontend
contracts, **not implemented REST endpoints or migration-ready DDL**.
Remaining inspector/review/visual/assessment/graph-transformation capabilities
below remain required. See the README's prototype traceability and backend gates;
passing fixture tests is not live AWS/Neon acceptance.

| ID | Screen / interaction | Production requirement |
|---|---|---|
| SOC-UI-01 | Catalog and resource library | Search/filter domain, subdomain, strategy, problem, release and review/deployment state; stable pagination. Show source, structural validity and human reviews as separate badges. |
| SOC-UI-02 | Designer + Simulator | Side-by-side graph/outline, selected-node inspector and current synthetic student screen. Editing selection and live simulation position are separate state. |
| SOC-UI-03 | Rules by topic | Maintain plain-language explanation beside typed source, outcome/guard, destination, priority, fallback and budget. Typed rule is executable authority; annotation drift is visible. |
| SOC-UI-04 | Natural-language rule proposal | AgentCore returns a proposed typed patch with base hash, resource IDs, evidence, warnings and cost estimate. Show before/after diff. Explicit Accept/Edit/Reject; acceptance changes only a draft. |
| SOC-UI-05 | Draft graph editing | Add/delete/split/merge/reorder/branch instructional nodes; transactionally rebind dependencies and activities. Canonical mathematical-move edits use doc 36/39's authoring service, not this graph. Dangling edges, stale refs and changed reviews block validation/publication. |
| SOC-UI-06 | Node inspector | Objective, source claim/provenance, strategy phase, activity/rubric, H1-H5 policy, before/after visuals, allowed transitions, fallback, accessibility and budgets. Private answers are staff-only, never part of preview payload. |
| SOC-UI-07 | Review cockpit | Structural report, critic findings, disclosure audit, math/pedagogy attestations, synthetic traces, diff, exact release hash, reviewer identities and publish decision. AI pass is not human approval. |
| SOC-UI-08 | Versions and audit | New draft from release; immutable history; diff and tombstones; expected-hash conflicts; retirement/rollback controls. In-use releases cannot be deleted. |
| SOC-UI-09 | Operations and analytics | Run status, proposal progress, deploy/activation, projection lag, fallback frequency, latency and estimated/actual token cost. No raw learner transcripts in global dashboards. |
| SOC-UI-10 | Synthetic student preview | Same safe runtime serializer, evaluator and policy service as student mode, with synthetic identity/draft scope and no real mastery writes. Restart creates a new isolated execution. |
| SOC-UI-11 | Preview path evidence | Highlight selected edge; display approved reason code, authoritative outcome and permitted evidence references. Never show model reasoning traces or hidden future answers in student mode. |
| SOC-UI-12 | Usability/error behavior | Loading/empty/error/retry states; preserve unsaved draft on safe retries; 409 offers reload/diff, never silent overwrite. Keyboard graph alternative, reduced motion, screen-reader labels and responsive layout. |

Prototype corrections required before promotion:

- Its `chooseNode` also moves the synthetic learner. In production, node
  inspection must not advance a session; explicit preview-from-node creates a
  new synthetic context with declared prerequisite evidence.
- Its first-matching-rule behavior has neither a complete tie policy nor bounded
  cycles. Reject ambiguous mandatory edges and require reviewed budgets/exits.
- The phrase parser can misunderstand source/destination and must not become an
  apparent Bedrock success fallback. A provider failure remains explicit.
- Editing rules cannot mutate an ongoing simulation silently. Pin the old draft
  hash or mark the session stale and require restart.
- Demo resource IDs, browser answer keys, direct DOM rendering and localStorage
  are not server authority, authentication, durable state or secure evaluation.
- "Log in as student" becomes **Synthetic preview**, not real impersonation.
  Real student login remains a separate owner-scoped flow.

### 3.1 Admin corpus batches and continuous metadata enrichment

The resource library must support recurring document/question **insert, edit,
reimport, withdraw and delete**, not only selecting a static imported corpus.
Detailed lifecycle, AWS service trade-offs and acceptance are in
[report 66 sections 12-17](66_AWS_STORAGE_DATABASE_COST_AND_MIGRATION_REPORT.md#12-recurring-admin-ingestion-correction-and-batch-reindexing).
These are proposed requirements, not existing automatic indexing behavior.

| ID | Required behavior |
|---|---|
| SOC-DATA-01 | Bulk upload creates a private immutable manifest and staging/conflict report; show per-item intent, base revision, source rights and diff before authorized approval. Reuse existing import/corpus-draft surfaces. |
| SOC-DATA-02 | Canonical accepted mutations, audit, invalidation/tombstone and outbox commit together through the approved REST/import boundary. Stable identity survives edits/reimports; published releases and attempted exam scoring snapshots do not mutate. |
| SOC-DATA-03 | Batch operations distinguish delta reindex, metadata reenrichment, failed-item retry, deletion reconciliation and full/model rebuild. Scope, estimated paid work, progress/counts, errors, cancellation and retry controls are visible. |
| SOC-DATA-04 | Persist chunk/source/hash/parser/model/taxonomy lineage, agent proposals/evidence and field-level human overrides separately. Reruns preserve human locks; old enrichment cannot overwrite newer revisions. Trusted ownership/disclosure fields are not model-controlled. |
| SOC-DATA-05 | Coalesce dirty scopes, reuse unchanged embedding inputs, bound task concurrency/retries/tokens and reconcile every projection. A partial or cancelled run cannot activate; broad reembedding requires explicit cost approval. |
| SOC-DATA-06 | Eligibility denies withdrawn/deleted/stale content before it reaches any model/student. Track physical deletion separately across objects/versions, vectors, graph, caches, analytics and training exports; TTL/sync status is not proof of erasure. |
| SOC-DATA-07 | Activate only verified generation membership with source-version CAS and retrieval probes. Test concurrent edit/delete, stale callbacks, interrupted rebuild and rollback; no hidden-answer leakage through full-document expansion. |
| SOC-DATA-08 | Choose one accepted retrieval path behind a controlled adapter. Managed KB is not currently listed in Ohio; region/residency, per-chunk metadata, filter/recall and pricing gates precede selection. No automatic provider migration. |

Model/training/analytics work reuses the existing ML projects and retains
their separate readiness/deployment approvals; the Studio does not need
another root-level ingestion, database or analytics project.

### 3.2 One step-authoring and Socratic admin journey

[Requirement 36 section 8.0](36_STEP_GENERATOR_AND_AUTHORING.md#80-integration-with-the-socratic-admin)
is the canonical integration contract, **STEP-SOC-01..08**. Requirement 36 owns
atomic mathematical moves, source lineage and attachments; this document owns
their instructional overlay, staff control plane and agent orchestration.
Neither document authorizes a duplicate step editor, scorer or learner runtime.

The Resource library selects one problem and explicit reference-solution
revision. Carry that selection into the existing reviewed-route workspace,
then bind the exact route/claim versions in the Designer. Preserve the context
through synthetic preview, distinct mathematics/pedagogy review and separately
gated publication/activation. Use shared renderers, asset pickers, source
comparison and safe resolvers, not copied canonical content.

For the first prototype, link to existing route editing rather than claim a
new universal atomic generator. Atomic-decomposition jobs and natural-language
rule proposals are distinct typed tasks under the same identity, provenance,
budget and stale-result policy; accepting a rule changes only a draft.
Source correction and reindexing follow SOC-DATA-01..08. Changed dependencies
invalidate affected draft reviews; old published attempts remain pinned.
A simulation that accepts staff-selected outcomes is explicitly synthetic,
not evidence that shared production evaluation or publication is complete.

## 4. Strategy and assessment requirements

### 4.1 Strategy registry

`SOC-DOM-01`: distinguish instructional **Socratic strategy** from canonical
mathematical **technique**. Doc 45's older colloquial strategy=technique mapping
must not collapse this new entity into a renamed knowledge table.

`SOC-DOM-02`: seed eight domains and at least twenty reviewed candidate strategies:
arithmetic; algebra; combinatorics; probability; number theory; complex numbers;
planar geometry; solid geometry. Preserve provenance and mark seeds DRAFT until
human review, not mathematically certified because they came from this pack.

`SOC-DOM-03`: versioned strategy contains code/domain, parent, canonical bindings,
phases/objectives, assessment/template allowlists, hint policy, misconception
probes, success evidence, fallback/transfer and review hash.

`SOC-DOM-04`: composition roles PRIMARY/SUPPORT/REMEDIATION/TRANSFER; explicit
return-to-claim mapping; maximum nesting, retry and event/time budget.
Equivalent-claim joins require reviewed mapping, never name/vector similarity.

### 4.2 Evaluation and disclosure

| ID | Required behavior |
|---|---|
| SOC-ASMT-01 | Map proposed SINGLE_CHOICE/MULTI_SELECT/NUMERIC/ORDERING/ERROR_IDENTIFY to existing kinds when semantically equivalent. Add schema/evaluator support for genuinely missing kinds; no parallel score engine. |
| SOC-ASMT-02 | Support AR1-AR5: A/R true and explanatory; A/R true but not explanatory; A true/R false; A false/R true; both false. Retain separate truth and entailment judgments. Five human-approved golden cases required. |
| SOC-ASMT-03 | Exact numeric, tolerance with units/domain, matching, ordering and choices are deterministic. Symbolic equivalence must enforce domain/exceptions and abstain when unsupported. |
| SOC-ASMT-04 | Geometry uses structured semantic actions and deterministic constraints. Vision/LLM interpretation is a proposal, not correctness evidence by itself. |
| SOC-ASMT-05 | Free-form rubric assistance returns SUPPORTED/PARTIAL/UNCERTAIN with authorized response-span references; uncertain means clarification/review, not invented certainty or automatic mastery. |
| SOC-ASMT-06 | Distinguish orientation, discovery, justification, diagnosis, practice and transfer from existing binding-purpose enums using an explicit mapping/extension. Require meaningful attempt, justification and transfer, not a fixed quiz quota. |
| SOC-ASMT-07 | Explicit hint/reveal is allowed and recorded as assisted. One wrong answer is tentative evidence; approved probes/accumulation precede misconception intervention. |
| SOC-ASMT-08 | Pre-answer allowlisted DTO includes current prompt, safe options, response contract and authorized current visual only. Exclude answers, hidden predicates/error mappings, future hints/steps and answer-bearing media, alt text, URLs or metadata. |

A release pins an immutable activity revision or private scoring snapshot.
Existing mutable `activity.definition` rows cannot be treated as immutable
merely because a workflow stores their UUID. Decide whether to reuse a supported
versioning mechanism or add one; publication tests must detect later key changes.
Publication/review changes to shared content must preserve existing consumers.

## 5. Workflow IR, persistence and single-runtime contract

### ADR-SOC-03: educational policy overlay, not arbitrary ASL

Start with a centrally versioned **generic transition machine** interpreting
validated immutable educational IR. One state-machine version can serve many
releases. A per-release ASL compiler is a later option only if a benchmark
demonstrates value; no administrator can submit executable AWS definitions.

Micro-courses remain the composition model. Bind a workflow release to an
immutable course release/state set, and optionally to mathematical route
releases. Workflow nodes reference approved course states/activities or control
operations; they do not copy course content or own a second quiz scorer.

Before adding `learner.workflow_execution`, determine whether existing enrollment
and `tutor.micro_course_runtime` can own the required CAS/version. If companion
tables are needed, they reference that enrollment and store adaptive metadata,
pending decisions and nested return state only. **There is one transition commit
service and one authoritative position/version per session.** Existing direct
course progression cannot independently advance a workflow-owned enrollment.
Implement an explicit execution mode/adapter and test legacy course behavior.

### 5.1 Proposed logical records, not migration-ready DDL

| Owner | Proposed addition / reuse |
|---|---|
| `pedagogy` | Socratic domain, strategy, immutable strategy version, canonical semantic-binding junctions and release-specific reviewed claim mappings. |
| Proposed `orchestration` namespace | Workflow identity/revision/release, typed nodes/edges, private policy refs, validation/simulation results and immutable content manifests. Namespace/names await schema review. |
| Existing `learner`/`tutor` | Enrollment-backed adaptive execution companion if required; append-only event/decision records with source evidence refs, expected version, idempotency and assisted flags. |
| Existing `pipeline` | Transactional outbox intent, publication/projection requests and consumer receipts; no independent second outbox without demonstrated need. |
| Existing `audit` | Reuse attributable `audit.action_log` for edits/reviews/publication. Add specialized records only for data that cannot fit its semantics. |
| Separate deployment metadata | Manifest hash, compiler/template version, state-machine version ARN, AgentCore deployment/prompt/model policy, activation/error and graph projection checkpoint. Never mutate published content to update operations state. |

Exact FKs must resolve to actual canonical UUID/text PKs. Use composite
`(release_id, node_key)` references or equivalent constraints so an edge cannot
cross releases. Source and activity versions/hashes must be explicit.

### 5.2 Release and transition invariants

`SOC-IR-01`: node kinds: START, DISCOVERY, QUIZ, INTERACTION, HINT, FEEDBACK,
AI_DECISION, DETERMINISTIC_GATE, PREREQUISITE_PROBE, REMEDIATION, BRANCH, RETURN,
TRANSFER, REFLECT, COMPLETE, HUMAN_REVIEW. Each has a typed config and allowed
references/disclosure/budgets. No arbitrary tool ARN, code or unreviewed assets.

`SOC-IR-02`: exactly one start; no dangling/cross-release edges; reachable
completion; priority/guard ambiguity rejected; bounded loops/nested returns;
mandatory assessment/review cannot be bypassed; fallback eligible and safe.
Cycles require explicit maximum visits and an exhausted-budget exit.

`SOC-IR-03`: DRAFT -> VALIDATED -> HUMAN_REVIEWED -> PUBLISHED.
Any content/dependency/policy change invalidates validation and attestations.
Retirement blocks new starts, not already-pinned resumptions.
Operational activation has a separate PENDING/ACTIVE/FAILED/PAUSED status.

`SOC-IR-04`: canonical hash is defined over normalized IR, exact dependencies,
strategy/activity/private policy hashes and schema version. Deploy manifest
binds this hash to infrastructure and model policy versions. A human reviews
the exact same hash; no post-review mutation of publication children.

`SOC-IR-05`: evaluation result, accepted event, transition decision, next
position/version and outbox enqueue commit in one PostgreSQL transaction.
No network call to AWS occurs inside that transaction.

`SOC-IR-06`: idempotency is scoped by principal/execution/action and normalized
payload hash. Same key+payload returns the same durable result; different
payload returns 409. Concurrent expected-version updates permit one winner.
Retries/replay cannot double-score, double-award or silently replace decisions.

`SOC-IR-07`: pending asynchronous decisions retain their input state version,
release hash, request ID and evidence checkpoint. A late recommendation for
an advanced session is rejected, not applied to its new state.

`SOC-IR-08`: prerequisite, cost, disclosure and mandatory rules run before AI.
One mandatory eligible edge or one eligible destination requires no model call.
Multiple permitted optional choices may invoke AgentCore. No eligible approved
fallback means explicit PAUSED/NEEDS_REVIEW, not a fabricated destination.

## 6. API, identity and authorization contract

All paths below are **proposed**, subject to collision/source OpenAPI checks.
Routers delegate to shared service functions, following existing REST patterns.

| Caller | Proposed operations |
|---|---|
| Staff author | `/v1/admin/socratic/strategies` and `/workflows`: catalog/create/read; draft patch with expected hash; AI proposal job; validate; simulate; diff; audit. |
| Reviewer | Hash-bound math and pedagogy attestations, findings/reject/request revision. Distinct capability checks; no self-granted role from request fields. |
| Publisher/operator | Publish reviewed hash; request deploy/activate/retire/pause; read deployment/projection readiness. Deployment is an operator action, not an AI tool. |
| Synthetic preview | Create/get/respond/assist/reveal/transition/history under a staff-scoped preview resource. Explicit draft hash and synthetic principal; same core runtime as student, no real learner effects. |
| Student | `/v1/learning/workflows/{release_id}/start`; `/v1/learning/executions/{id}` and `/respond`, `/assist`, `/reveal`, `/transition`, `/history`. Bearer-derived owner, published ACTIVE release on new start. |
| AWS adapters | `/v1/internal/socratic/decisions/context` and `/commit`; request/job read/status. Machine authentication plus narrow service scopes; load authoritative evidence server-side. |

Mutations carry `Idempotency-Key` plus expected content hash/state version.
Proposal/deploy jobs return 202 and an authorized pollable job ID, not a
long-held browser request or untracked background thread.

Example **student submission**, not a trusted score:

```json
{
  "current_node_key": "justify",
  "activity_revision_id": "immutable-revision-reference",
  "response": {
    "assertion_true": true,
    "reason_true": true,
    "reason_explains": false
  },
  "expected_state_version": 4
}
```

Response: status, correlation/request ID, current version, sanitized current
node, allowed feedback/actions and pending-job status. Never serialize a raw
staff workflow/activity object into the student response.

### 6.1 Identity release gate

Use verified Cognito/OIDC staff identity with explicit author, math reviewer,
pedagogy reviewer, publisher and operator capabilities. Reuse the existing pool
only after issuer/audience/group and app-client suitability checks. An SPA uses
authorization-code + PKCE without a client secret; no shared admin key or AWS
credential in its bundle/localStorage.

The selected API front door/BFF must validate issuer, audience, expiry and
capabilities and preserve staff subject. Existing shared-key APIs remain
compatible for legacy callers, but **a shared key plus arbitrary actor text is
insufficient for Studio approval/publication**. New routes enforce identity at
REST/service boundary, not just the UI or API Gateway.

Internal endpoints need a reviewed signed service identity path (for example
IAM-authorized gateway plus validated identity forwarding, or scoped short-lived
service JWT). A Function URL configured for public access does not implicitly
authenticate an internal caller. No task token/shared admin credential in model
context. Synthetic preview is not authorization to read any real student's work.

Error contract: 401 unauthenticated, 403 insufficient capability, 404 missing or
nonowned resource using established anti-enumeration convention, 409 stale/conflict,
422 schema/policy failure, 429 quota, 503 dependency unavailable. Include safe
`code`, `message`, `correlation_id`, `retryable`; log server errors without private
answers. Do not broadly rewrite unrelated legacy error handlers.

## 7. AWS architecture and deployment requirements

```text
Admin SPA (private S3 + CloudFront) -> authenticated API front door -> mathbank-rest
                                                                  |
                         PostgreSQL draft/review/runtime + transactional outbox
                                                                  |
                   leased outbox dispatcher Lambda -> Step Functions
                                                       |         |
                                             adapter Lambda   AgentCore
                                                       |         |
                                                       +-> authorized REST tools
                                                                  |
                                            CAS commit + safe result + outbox
                                                                  |
                                status polling / published structural projection
```

### 7.1 AgentCore integration decision

Current official [regional matrix](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html)
lists harness, Runtime microVMs and Gateway support in **us-east-2**.
Do not preserve the pack's launch-era four-region assumption as a current
restriction. Account/model access and the exact API/CDK deployment path still
need an operator-authorized smoke test.

Supported design choices:

1. **Managed harness:** Step Functions optimized
   `arn:aws:states:::bedrockagentcore:invokeHarness`, if supported and approved
   in the target environment. The [integration reference](https://docs.aws.amazon.com/step-functions/latest/dg/connect-bedrockagentcore.html)
   specifies Request Response only, a 900-second maximum, and final assistant
   text output; parse/validate that text as strict JSON before use.
2. **Custom agent runtime:** deploy the bounded agent to AgentCore Runtime;
   a Lambda adapter invokes its supported SDK API and normalizes the result.
   Validate the exact SDK/streaming/result contract instead of assuming
   `InvokeAgentRuntime` and `InvokeHarness` have identical payloads.

Do not deploy both by default. Choose the cheapest supported path that passes
tool authorization, schema, budget and privacy tests. Use consumption-based
runtime rather than an always-on AgentCore Instance for the pilot.

**Important timeout behavior:** stopping a Step Functions task does not stop a
harness already running. Align harness/task deadlines, max iterations, token
budgets and retry policy. Reconcile timed-out jobs before another paid invocation;
do not create retry storms or assume a timeout cancels billing.

### 7.2 Workflows

| Workflow | Required behavior |
|---|---|
| Authoring | Standard: load hash-pinned source -> bounded parallel proposals -> structural/math/disclosure critics -> persist proposal -> simulation -> secure human approval -> recheck hash/attestations -> REST publish -> deploy/verify -> activate. Rejection/timeouts create revision-required status. |
| Human callback | A distinct callback task, not the AgentCore invocation. Store token server-side with TTL/job ownership; browser sends approval ID and expected hash. Approval service rechecks identity, capability and content before completing callback. |
| Student transition | Short execution: load trusted context -> deterministic rules -> conditional AgentCore -> validate candidate/evidence -> REST CAS commit -> safe result. No AWS Wait state for days of student inactivity. PostgreSQL owns resume. |
| Outbox/projection | Lease/retry delivery with stable request ID; reconcile start-before-ack failures; DLQ/alerts for exhaustion. Public graph update only after committed publication, scoped to its projection owner. |

Initial recommendation: short **Standard** transition executions for traceability,
then benchmark Express as an explicit cost/latency option. Express delivery
semantics, retention and callback restrictions require separate acceptance;
business correctness always comes from PostgreSQL CAS/idempotency.
Do not claim Step Functions execution semantics make downstream side effects
exactly-once.

### 7.3 CDK and operational gates

`SOC-AWS-01`: add stacks to the existing CDK app; versioned state machine and
deployment manifest, task Lambdas, required queue/DLQ, logs/retention/alarms,
AgentCore config/runtime and optional scoped Gateway targets. No per-admin
arbitrary infrastructure deployment.

`SOC-AWS-02`: IAM separates proposal, review, publish, deployment and transition
roles; scope model/tool/resource ARNs. Do not grant model tools publication,
SQL/Cypher writes, mastery awards or unrestricted state-machine execution.

`SOC-AWS-03`: runtime secrets use existing SSM cold-start conventions; never
CloudFormation secure dynamic references inside Lambda env vars. No secrets
in SPA, image, prompt, task payload or traces. Preserve reserved AWS env-key
alias handling and existing ARM64 build/runtime alignment.

`SOC-AWS-04`: with public TLS Neon/Aura, do not add NAT/VPC by default. An
Aurora/Neptune migration changes that network design and must be priced in doc 66.
Keep user-facing auth/CORS/CSP and all internal service paths explicitly designed.

`SOC-AWS-05`: metrics: deterministic-vs-AI decisions, fallback/rejection reason,
tokens/cost estimate versus actual, latency, CAS conflicts, duplicate delivery,
outbox age, deployment/projection lag and quota exhaustion. Exclude raw learner
answers, hidden keys and chain-of-thought from UI/logging.

`SOC-AWS-06`: implement model/tool/iteration/time limits, per-run token budgets,
concurrency throttles and a pause switch before a paid pilot. AWS Budgets alarms
notify; they are not a hard real-time spending cap.

## 8. Agent roles and permitted tools

Roles: authoring planner, assessment designer, mathematical critic, disclosure
auditor, synthetic student simulator, next-step selector and current-node tutor.
Use separate policies/tool scopes, not seven unconstrained autonomous services.

Read tools reuse canonical REST/MCP retrieval: strategies, reviewed route,
approved activities/claims, workflow release, current disclosure, minimized
owned context and eligible transitions. Staff draft tools create **proposals**
and run validation/simulation; they cannot approve themselves.

Next-step output:

```json
{
  "selected_node_key": "bijection_remediation",
  "reason_code": "JUSTIFICATION_GAP",
  "evidence_event_ids": ["owned-event-reference"],
  "alternatives": ["approved_probe"],
  "uncertainty": "MEDIUM",
  "explanation_for_audit": "The approved probe targets the recorded justification gap."
}
```

REST checks exact eligible node set, evidence ownership/checkpoint, release hash,
state version, allowed reason and policy budgets. Unknown fields/IDs, unsupported
certainty or stale evidence cause recorded rejection and approved fallback/pause.
Provider confidence is never write authority. The audit explanation is a short
reason summary, not requested internal model reasoning.

No model tools: `self_publish`, `approve_mathematics`, `award_mastery`,
`execute_sql`, `run_cypher_write`, unrestricted AWS deployment, future-answer
retrieval or real-student impersonation. Existing corpus tools do not thereby
gain access to learner-private evidence.

## 9. Delivery plan and acceptance gates

The work-package table defines the complete required scope. Baseline
reconnaissance (WP00) and frontend work (WP06) are in progress/partial; no work
package is certified complete by the UI increment. REST, database, production
runtime and cloud acceptance remain outstanding. Dependencies define order,
not permission to deploy or drop unfinished features.

| WP | Deliverable and owner | Prerequisites | Exit evidence |
|---|---|---|---|
| WP00 | Signed baseline/ADRs, target catalog delta and identity design | None | Exact source/target distinction; actual FK/versioning plan; human approvals. This document is source reconnaissance, not target certification. |
| WP01 | Typed IR, schema, strategy catalog and offline fixtures | WP00 | Strict schemas, eight domains/20 strategy drafts, invalid graph/unknown-control tests; doc 36 STEP-SOC source/solution/route identity contract. |
| WP02 | Additive DB migrations and enrollment adapter | WP01 | Immutability, FK, CAS, idempotency, outbox and rollback tests; no live DB without approval. |
| WP03 | Assessment adapters and safe serialization | WP01, WP02 | AR1-AR5 and numeric/symbolic/geometry/free-form fixtures; pre-answer leak properties. |
| WP04 | REST admin/preview/student/internal contracts and attributable auth | WP02, WP03 | Owner/role denials, generated OpenAPI/types, job API and replay/concurrency tests. |
| WP05 | IR compiler/interpreter and deterministic simulator | WP01, WP04 | Bounded reachability, priority/fallback/return tests; hash-pinned mocked orchestration. |
| WP06 | New admin package and focused authoring/review UX | WP04, WP05 | Prototype traceability SOC-UI-01..12; unified doc 36 source/atomic-route/strategy journey; real safe runtime preview; keyboard/browser tests. |
| WP07 | AgentCore agent/config and scoped REST-backed tools | WP04, WP05 | Bedrock stubs, injection/eligibility rejection, source/prompt/model provenance and budgets. |
| WP08 | CDK, Lambda and Step Functions integration | WP07 | `make synth`, ASL validation, IAM assertions, explicit live opt-in and cost tags; account/model smoke evidence. |
| WP09 | Published structural graph projection | WP02, WP05 | Ownership isolation, idempotent rebuild, count/edge parity, lag and failure tests. |
| WP10 | Student host integration and accessibility | WP03, WP04, WP05 | Current/done/locked navigation, resume pinned release, hint/reveal assisted behavior; legacy runtime unchanged. |
| WP11 | Full scenario acceptance and pilot | WP06..WP10 | All S01-S22 below; independent SME reviews; measured costs/latency and rollback rehearsal. |
| WP12 | Recurring corpus-batch and metadata controls, reusing ingestion/DB/REST/projector owners | WP02, WP04, WP07, WP08 | SOC-DATA-01..08 and report 66 DATA-01..08; current-provider delta pipeline first. Any pilot using mutable corpus resources also requires these gates; storage migration remains separately approved. |

### 9.1 Scenario coverage

Preserve the pack's [full scenario definitions](../copilot-instructions/mathbank-adaptive-socratic-framework/10_SCENARIOS_AND_TESTS.md);
each fixture needs source permission/provenance, exact dependencies, expected
responses/edges, no-leak assertions, trace, idempotency and SME sign-off.

| Scenarios | Acceptance focus |
|---|---|
| S01-S02 | Construction 8.1 progressive discovery and Loci 7.3 necessity/converse; reviewed alternate construction; two-line interaction and accessible alternative. |
| S03-S04 | Stars and Bars representation/bijection/transfer; PIE overcount and Assertion-Reason remediation. |
| S05-S09 | Graph invariant, conditional probability, roots of unity, solid slices and number-theory counterexample. Domain strategies cannot be a geometry-only implementation. |
| S10-S12 | All AR1-AR5, verified alternative symbolic/free-form answer, uncertain abstention, independent versus assisted evidence. |
| S13-S14 | Resume days later on pinned release; concurrent/duplicate submission yields one durable effect. |
| S15-S17 | Invalid/timeout AI fallback; missing/stale human review blocks publish; draft split/merge leaves published content unchanged. |
| S18-S20 | Graph ownership/privacy, nonowner/future-answer tool denial, keyboard/screen-reader/reduced-motion paths. |
| S21-S22 | AWS start-before-ack recovery; quotas/unsupported integration pause or verified approved alternative, never unauthorized provider substitution. |

Additional release gates:

- Doc 36 [integrated admin acceptance](36_STEP_GENERATOR_AND_AUTHORING.md#101-integrated-admin-acceptance):
  exact source/solution/route selection, no duplicate canonical editor, stale
  generation rejection, dependency-review invalidation and separate simulated
  versus graded preview.
- Zero private learner events, scores, answers or confidence edges in shared
  Neo4j; published structural projection only.
- Zero answer/predicate/future-content leakage across JSON, accessibility text,
  assets and errors before permission.
- Stale review/content hashes and unapproved mathematical dependencies fail closed.
- One authoritative state/version and one score effect across legacy/adaptive
  course endpoints, Lambda retries and late agent callbacks.
- No paid model invocation for a deterministic unique transition.
- Failed deployment never appears ACTIVE; PostgreSQL history survives rollback.
- Tests run offline by default; shared-DB and paid AWS suites require explicit
  operator opt-in. No claim of delivery solely from generated code or diagrams.

Pilot: Construction 8.1, Loci 7.3, Stars and Bars and conditional probability;
start with synthetic runs and shadow recommendations, then limited opt-in
learners. Measure validated outcomes; do not infer educational improvement from
path coverage alone.

## 10. Decisions requiring human approval

| Decision | Recommended starting point | Required approver |
|---|---|---|
| New packages vs existing UI | Separate admin SPA + scoped AgentCore package; reuse all data/runtime services. | Product + architect |
| Composition/CAS ownership | Micro-course composition with one adaptive transition service/enrollment mode. | REST/data architect |
| Staff roles and independent attestations | Verified principal; separate math/pedagogy capabilities and publish permission; explicit self-review policy. | Security/product + SMEs |
| Activity immutability | Pin immutable revision/scoring snapshot; do not trust a mutable UUID alone. | Data + assessment owner |
| AgentCore path | Managed harness if verified; otherwise custom Runtime + Lambda adapter. No automatic non-Bedrock fallback. | AI/cloud owner |
| Region/model | Prefer us-east-2 co-location; verify exact model/access/quotas without moving existing workloads by assumption. | Cloud/operator |
| Workflow execution type | Generic versioned machine, Standard first; benchmark Express separately. | Cloud + runtime owner |
| Privacy and retention | No raw private evidence in shared graph/traces; explicit minors/retention/deletion policy before real learners. | Privacy/product owner |
| Budgets and SLOs | Set numeric run/month/token/concurrency budgets and p95 latency targets from pilot measurements before rollout. | Product + operator |
| Mathematics fixtures | Source rights and independent mathematical/pedagogical review, no automatic certification. | SMEs |

These are recorded open approvals, not permission to run migrations, deploy IAM,
publish lessons, move data or invoke paid inference.

## 11. Source-pack coverage and related documents

| Pack file | Expanded here |
|---|---|
| 00 README | Scope, boundaries and ownership: sections 0-2. |
| 01 Baseline/decisions | Source audit and ADRs: sections 0, 2, 5, 10. |
| 02 Domain strategies | Registry/composition: section 4. |
| 03 Learning graph | Actual FK reconciliation, logical model, transactions and projection: sections 0, 5, 9. |
| 04 Assessments | Evaluator mapping, AR1-AR5 and no-leak rules: section 4. |
| 05 Workflow IR | Typed graph, bounded returns, hash and CAS: section 5. |
| 06 AWS orchestration | Current region check, integration options, callbacks, Lambda and CDK: section 7. |
| 07 Agents/MCP | Roles, scopes, proposed tools and strict output: section 8. |
| 08 REST/security | Contracts, identity gaps, error/replay semantics: section 6. |
| 09 Admin/student | Prototype traceability and phased student host: sections 3, 9. |
| 10 Scenarios/tests | S01-S22 and release gates: section 9. |
| 11 Copilot execution | Narrow, dependency-ordered WPs and human approvals: sections 9-10. |
| 12 Schema examples | Illustrative examples reconciled to actual IDs; normalized submission/decision and deployment contracts: sections 0, 5-8. |
| UI README + complete HTML | All three views and parser/selection/localStorage/grading limitations: sections 0, 3. |

Also read with [guided workspace 34](34_GUIDED_PROBLEM_WORKSPACE.md),
[atomic authoring 36](36_STEP_GENERATOR_AND_AUTHORING.md),
[routes 39](39_PRECOMPILED_TUTORING_ROUTES.md),
[micro-course 40](40_MICRO_COURSE_PLATFORM.md),
[interactions 41](41_INTERACTION_TEMPLATE_LIBRARY.md),
[navigation 42](42_MICRO_COURSE_STUDENT_NAVIGATION.md),
[admin 43](43_ADMIN_MICRO_COURSE_AUTHORING_UI.md),
[API 45](45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md),
[activity 46](46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md),
[AWS 62](62_AWS_SERVERLESS_DEV_HOSTING_COST_RESEARCH.md),
[deployment 63](63_AWS_SERVERLESS_DEPLOYMENT_IMPLEMENTATION.md) and
[exam 64](64_AWS_BEDROCK_MOCK_EXAM_AGENT.md).
