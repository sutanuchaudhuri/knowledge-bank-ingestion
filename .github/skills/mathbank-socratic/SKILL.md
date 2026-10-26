---
name: mathbank-socratic
description: 'Working on the Adaptive Socratic Studio: mathbank-socratic-admin (React/Vite staff SPA), the Socratic API in mathbank-rest (socratic_auth, socratic_service, routers/socratic.py, socratic_app), migration 053 orchestration.socratic_* tables, and the isolated MathBankSocraticStack in mathbank-infra-aws. Use when starting/stopping the Studio locally (with or without AWS), running its tests, migrating, deploying, verifying or tearing down its AWS stack, or resuming the step-by-step implementation ledger.'
argument-hint: 'Optional: local | test | migrate | deploy | verify | destroy | ledger step number'
---

# mathbank-socratic conventions

Sources of truth, read in this order before changing anything:
[ledger 67](../../../documentation/requirements/67_SOCRATIC_IMPLEMENTATION_HANDOFF.md) (step status,
evidence, next action), [requirement 65](../../../documentation/requirements/65_ADAPTIVE_SOCRATIC_ADMIN_AND_AGENTCORE.md),
[frontend README](../../../mathbank-socratic-admin/README.md),
[REST README — interactive non-AWS testing](../../../mathbank-rest/README.md#interactive-non-aws-testing),
[schema reference](../../../documentation/requirements/reference/postgres/orchestration.md) and the
root [README Socratic quick start](../../../README.md#socratic-studio-admin-authoring--local-and-aws).

## Moving parts

| Piece | Where | Local port | AWS |
|---|---|---|---|
| Studio SPA | `mathbank-socratic-admin/` (React 19 + Vite + TS) | 5186 | Bundled `dist/` served same-origin by the Lambda |
| Socratic API | `mathbank-rest` — `routers/socratic.py`, `socratic_auth.py`, `socratic_local_auth.py`, `socratic_service.py`, `socratic_contracts.py`, `socratic_app.py` | 8000 (full REST) or 8019 (standalone local staff API) | `MathBankSocraticStack` Lambda Function URL |
| Draft tables | `mathbank-db/sql/053_socratic_drafts.sql` → `orchestration.socratic_{strategy,workflow,revision,command}` | Neon (REST-configured) | same Neon |
| Preview tables + scorer | `054_socratic_previews.sql` → `socratic_preview`, `socratic_preview_event`; `socratic_preview.py`; shared `activity_scoring.py` (also used by micro-courses) | Neon | same Neon |
| Agent package | `mathbank-socratic-agent/` | — | **Placeholder** until ledger steps 04–05 (AgentCore + Step Functions) |

## Commands (root Makefile; `make help | grep socratic`)

```bash
# Test — no AWS, no paid model calls
make socratic-test            # UI vitest + typecheck + REST Socratic pytest (DB cases: SOCRATIC_DB_TESTS=1)
make socratic-e2e             # Playwright: 8 prototype checks + 2 real loopback local-auth (own ports 8018/5188)

# Local, non-AWS
make socratic-password        # generate/rotate local-author password into mathbank-rest/.env (SOCRATIC_LOCAL_PASSWORD); keeps Cognito mode
make socratic-setup-local     # alternative: the OPERATOR types a password at the prompt
make socratic-start           # local staff API :8019 (auth only) + UI :5186 proxied to it
make socratic-start DRAFTS=1  # + real draft persistence in REST's configured Postgres
make socratic-status          # also: socratic-access, socratic-stop, socratic-restart
make socratic-api-start       # API alone (also -stop/-status); socratic-ui-start for the UI alone
make rest-start && make socratic-ui-start   # UI against the full REST on :8000 (Cognito mode)

# Database
make socratic-migrate         # additive, idempotent migrations 053 + 054 (direct Neon endpoint)

# AWS — profile aws-sutanu-admin, account 848941468793, us-east-2
make socratic-seed            # 3 SSM SecureStrings from mathbank-rest/.env, values never printed
make socratic-diff            # builds SPA first
make socratic-deploy          # builds SPA, deploys ONLY MathBankSocraticStack, prints StudioUrl
make socratic-verify          # read-only acceptance; auto-resolves StudioUrl (or URL=...)
make socratic-outputs
make socratic-destroy         # teardown of this stack only
```

Per-project equivalents: `mathbank-socratic-admin` (`make start|stop|status|e2e|e2e-local-auth`),
`mathbank-rest` (`make start-socratic-local|stop-socratic-local|status-socratic-local|test-socratic|
migrate-socratic-drafts|verify-socratic-deployment URL=...`), `mathbank-infra-aws`
(`make synth-socratic|diff-socratic|deploy-socratic|seed-socratic|outputs-socratic|destroy-socratic`).

Logs: `mathbank-rest/.socratic.log` (local staff API), `mathbank-socratic-admin/.server.log` (UI).
A start failure prints the exact path; read it before guessing.

## Non-negotiables

- **REST is the only database boundary.** The SPA calls only same-origin `/v1/admin/socratic/*`
  with `credentials: include`; no browser API key, localStorage, mock fallback, embedded answer
  key or client-side grading. Unavailable routes must fail visibly.
- **Roles are server-enforced and only narrow access.** Studio entry requires `Admins`;
  `student` role (capability `preview` only) is offered to Admins who are also in `Students`.
  Active role = HttpOnly `mathbank_socratic_role` cookie, validated against current groups on every
  request. `manage_users` routes (`/users*`) call Cognito with the Lambda role (pool-scoped IAM) and
  guard self-lockout. Access events go to `audit.action_log` (entity `STAFF_USER`) only when
  `SOCRATIC_ACCESS_AUDIT=true` (hosted, `DRAFTS=1`) — keep it off in offline tests; never log
  passwords or full IPs. Cognito's own auth-event history needs the Plus tier (pool is Essentials).
- **Local auth is explicit, loopback-only, never a Cognito fallback.** It rejects non-loopback
  hosts and Lambda/ECS runtimes; `local:` principals are not Cognito attestations. Never set,
  ask for a staff password in chat or print it in tool output. `make socratic-password` saves a
  generated one in the gitignored mode-600 `mathbank-rest/.env`; read it there in-process (values
  are single-quoted by `set_key`). `LOCAL_STAFF_NOT_CONFIGURED` means no local credentials yet;
  `make sync-env` rewrites that `.env`, so rerun `make socratic-password` after it.
- **Hosted local auth is forbidden;** never deploy workstation profiles, local credentials or
  insecure-cookie settings.
- **Never redeploy the shared `MathBankRestStack` for Socratic work.** The Socratic stack is a
  separate CDK app (`mathbank-infra-aws/socratic_app.py`); `make infra-deploy/destroy/outputs`
  use `app.py` and neither see nor touch it — always use the `socratic-*` targets.
- **Deploy needs a fresh SPA build** (`socratic-deploy`/`-diff`/`-synth` build it). Colima is
  auto-started; an expired AWS session (`aws login --profile aws-sutanu-admin`) is the usual cause
  of unrelated-looking failures (see the `mathbank-infra-aws` skill).
- **Account concurrency:** the stack deliberately has **no reserved concurrency** (account limit
  is 10; AWS requires 10 unreserved). Do not add a reservation without a quota increase.
- **Teardown scope:** `socratic-destroy` deletes the Lambda, Function URL, IAM role and the
  stack-owned `StudioOrigin` SSM parameter. It does **not** delete the seeded SSM secrets, the
  CDK-bootstrap ECR image, the retention-managed CloudWatch log group (one-week retention) or
  Neon `orchestration.*` rows. Revision/strategy/command rows are immutable by trigger — never
  bypass triggers to "clean up"; removing data needs a separately authorized migration.
- **Migration 053 is additive and isolated**; never write canonical `core`/`pedagogy` rows or
  real learner state from Socratic code or tests. DB tests roll back; the concurrency fixture
  (`SOCRATIC_CONCURRENCY_TESTS=1`) leaves labelled `synthetic:socratic-test:*` evidence — opt in
  only when needed.
- **One scorer.** Score activities only through `activity_scoring.py`; never add a second
  evaluator or a client-side grade. Assertion–Reason is an MCQ whose `correct_index` must match
  its `assertion_reason` judgments; free-form abstains (`UNCERTAIN`). Previews score against
  the private snapshot pinned at start and must never expose policies, keys, undisclosed hints
  or future nodes. Preview code must never write learner/mastery/course/activity-response rows.
- **UI baseline is the clean prototype** `documentation/copilot-instructions/mathbank-adaptive-socratic-framework/UI/index (1).html`
  (user direction 2026-10-25): icon rail · searchable sidebar (`src/search.ts`, pure and unit-tested) ·
  one canvas · right detail drawer where all editing happens. The Designer shows the same typed
  program as Flow, Natural language (`src/narrative.ts`) or read-only JSON. Keep screens
  clutter-free: one primary button per region, staff/debug tools collapsed, no explanatory
  paragraphs. Use MathBank tokens, not the prototype's colours. Never drop a capability to
  declutter — move it into the drawer, settings or a collapsed section.
- **Prototype UI is the minimum baseline** — extend schemas/APIs to keep its features; never
  remove a prototype feature to fit the backend (follow the `modern-ui-design` skill for visuals).
- **Structural validation ≠ mathematical/pedagogical approval ≠ publishing.** A model output,
  client outcome or successful AWS job never certifies mathematics.
- **Budget:** the authorized prototype AWS/model spend is **$20** (not an automatic cap); the
  selected model is DeepSeek V3.2 (`deepseek.v3.2`) — no provider substitution.

## Resuming implementation (ledger 67 protocol)

1. `git status`; read the ledger row for the next PENDING step and its dependencies.
2. Mark it `IN PROGRESS` in the ledger with scope/files **before** coding.
3. Reproduce the smallest baseline (`make socratic-test`), separating unrelated failures.
4. Implement through REST services; add contract and failure-case tests (stale hash 409,
   idempotent replay, CSRF/origin denial, owner isolation).
5. Record exact commands/results; mark `COMPLETE (offline)` separately from live verification.
   After deploys run `make socratic-verify`. Refresh OpenAPI/schema references when APIs/DDL change.
