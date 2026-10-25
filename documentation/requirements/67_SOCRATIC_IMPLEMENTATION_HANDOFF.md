# 67. Socratic Studio implementation and agent handoff

## Operating contract

Implement one vertical step at a time. Update this file **before starting** a
step and **after verification**, so another agent can resume without relying on
chat history. `COMPLETE (offline)` means code/contracts/tests passed, not that a
cloud deployment or live-user acceptance occurred. Keep `live verification`
separate; never mark a whole work package complete from fixture results.

Required baseline: [framework](../copilot-instructions/mathbank-adaptive-socratic-framework/00_README.md),
[detailed UI](../copilot-instructions/mathbank-adaptive-socratic-framework/UI/README.md),
[65 requirements](65_ADAPTIVE_SOCRATIC_ADMIN_AND_AGENTCORE.md),
[36 unified authoring](36_STEP_GENERATOR_AND_AUTHORING.md) and
[frontend contracts](../../mathbank-socratic-admin/README.md).
The detailed prototype is a minimum: expand schemas/API to preserve features,
not remove requirements to fit an initial implementation.

## Authorization and guardrails

- Existing Neon: additive isolated tables and synthetic fixtures only; do not
  overwrite canonical content or mutate real learner state.
- AWS prototype: profile `aws-sutanu-admin`, account `848941468793`, Ohio
  `us-east-2`; isolated resources only. Maximum authorized prototype AWS/model
  spend **$20**, not an account-wide hard cap. Exact selected model previously
  disclosed: DeepSeek V3.2, `deepseek.v3.2`. No provider substitution.
- REST is the only runtime database boundary. Reuse course/route/activity
  services, existing outbox and audit where applicable. No duplicate scorer.
- No commits requested. Preserve unrelated dirty worktree changes.
- Staff mathematical/pedagogical review and publishing remain distinct.
  A model, client outcome or successful AWS task cannot certify mathematics.

## Sequential implementation ledger

| Step | Status | Live verification | Exit evidence / next action |
|---|---|---|---|
| 00 Baseline and UI preservation | COMPLETE (offline frontend increment) | Not integrated with workflow backend | 24 unit tests, 8 prototype Playwright checks at 1440/390, TypeScript/build passed. Required unfinished UI remains in scope. |
| 01 REST staff session authentication | **COMPLETE (offline + real local-browser auth)** | **Cognito config/read-only preflight verified; successful staff login/revocation pending** | Explicit loopback-only non-AWS login added; 57 focused auth/setup/security tests, 2 real local-auth browser cases, Ruff and mypy pass. Full REST suite now 804 passed/134 skipped after fixture repairs. No cloud deployment or account mutation. |
| 02 Draft/source persistence | **COMPLETE (implementation, Neon schema/tests and isolated deployment)** | **Hosted readiness/schema/SPA/denial verified; successful Cognito staff/protected-cloud round trip pending** | Migration 053 applied/repeated; owned immutable drafts, source pins, CAS/replay, atomic audit/outbox and concurrent writers tested. 824 REST tests passed/135 skipped; 25 UI unit, 8 prototype browser, 2 real local-auth browser, 3 infra tests passed. Shared REST stack unchanged. |
| 03 Synthetic response/evaluation/help | PENDING; depends on 02 | Pending | Reuse existing scorer/runtime; safe current-node DTO, five AR cases, hints/reveal assistance, preview hash pinning, CAS/idempotency and failure tests. |
| 04 AgentCore proposal package | PENDING; depends on 02 | Pending | Bounded DeepSeek typed proposals, minimal context, exact eligibility, prompt/model provenance, explicit staff acceptance, stale-result rejection. |
| 05 Step Functions/Lambda/CDK | PENDING; depends on 04 | Pending | Isolated optional stack in existing CDK app, scoped IAM, durable intent/reconciliation, token/time/job limits and pause switch; selected-stack synth/test/deploy. |
| 06 Live Neon/AWS vertical acceptance | PENDING; depends on 03 and 05 | Pending | Real authenticated browser → REST → Neon → Step Functions/AgentCore → persisted proposal → explicit accept; receipts, bounded spend, failed-job/replay tests. |
| 07 Complete node inspector/graph editing | PENDING; depends on 02 and 03 | Pending | Full typed configs, source claims/activity/rubric refs, H1-H5 policies, lineage-aware split/merge/reorder/branch/return validation, accessibility and original UI detail. |
| 08 Mathematical/pedagogical review cockpit | PENDING; depends on 06 and 07 | Pending | Separate verified capabilities, exact-hash attestations, no stale/self-authorized publish, immutable release/retirement and operational activation. |
| 09 Visual/attachment integration | PENDING; depends on 03 and 07 | Pending | Reuse widgets/scene/artifact services, immutable reviewed refs, before/after disclosure, source rights/accessibility, safe video adapter; same student/preview resolver. |
| 10 Remaining framework and pilot | PENDING; depends on 08 and 09 | Pending | All node/assessment kinds, published structural graph, operations/projection/reindex controls, eight domains/20 strategies, S01-S22 and independent SME acceptance. |

Steps 07 and 09 may later proceed independently once their listed prerequisites
are satisfied; list order alone does not imply an additional dependency.

## Step 01 execution record

- Follow-up **COMPLETE**: user authorized repairing the live-config blockers
  and regressions, and selected explicit loopback-only local staff login plus
  offline unit/browser tests. See the follow-up verification record below.
- Started: 2026-10-25, source/worktree evidence.
- Scope: staff session boundary only. Do not change legacy admin-key routes or
  student JWT behavior. Do not provision another user pool or request passwords
  through chat.
- Baseline command:
  `cd mathbank-rest && .venv/bin/python -m pytest -q --disable-warnings --maxfail=1`
- Baseline result: **385 passed, 62 skipped, one pre-existing failure**:
  `tests/test_pedagogical_agent_tools.py::test_pedagogical_tools_use_rest_only`.
  Expected URL omits `?enrich=false`; actual tool includes it. Do not fix as
  part of Socratic authentication.
- Prior auth: shared `X-Admin-Api-Key` on old REST admin operations;
  [web Cognito](../../mathbank-web/lib/cognito.js) uses the existing pool,
  `ADMIN_USER_PASSWORD_AUTH`, app-client secret hash and `Admins` group.
- Implementation:
  [authentication service](../../mathbank-rest/src/mathbank_rest/socratic_auth.py),
  [session router](../../mathbank-rest/src/mathbank_rest/routers/socratic.py),
  [configuration](../../mathbank-rest/src/mathbank_rest/config.py),
  [app wiring](../../mathbank-rest/src/mathbank_rest/main.py),
  [legacy scheme wording](../../mathbank-rest/src/mathbank_rest/security.py) and
  [offline tests](../../mathbank-rest/tests/test_socratic_auth.py).
- Delivered `POST/GET/DELETE /v1/admin/socratic/session`; legacy shared-key and
  learner-JWT behavior is unchanged. Fresh Cognito `GetUser` validates the
  actual token; issuer/client/token-use restrictions prevent another pool or
  app client from borrowing local staff groups. Stable provider `sub`, live
  paginated group lookup and independent capabilities are server-derived.
- Scoped HttpOnly/Secure/Strict cookies; dedicated HMAC CSRF plus exact Origin
  checks; no browser provider tokens, self-declared role, or global sign-out.
  Logout uses current-family `RevokeToken` before clearing cookies; provider
  failure remains explicit. Safe errors include correlation IDs/no-store;
  request validation never echoes raw password input. No default grants for
  reviewer/publisher roles and no SDK automatic retry.
- Focused verification:
  - `cd mathbank-rest && .venv/bin/python -m pytest -q tests/test_socratic_auth.py tests/test_security.py --disable-warnings`:
    **39 passed** (35 new cases, 4 existing learner-security cases).
  - `.venv/bin/python -m ruff check src/mathbank_rest/socratic_auth.py src/mathbank_rest/routers/socratic.py tests/test_socratic_auth.py`:
    **passed**.
  - `.venv/bin/python -m mypy --follow-imports=silent src/mathbank_rest/socratic_auth.py src/mathbank_rest/routers/socratic.py`:
    **passed**, two source files.
- Initial broader regression attempts did **not** establish a green whole-service suite
  (superseded by the repaired full-suite result below):
  - Excluding only the initial known failure: **386 passed, 62 skipped,
    1 deselected**, then unrelated AST-based
    `test_agent_registers_all_teaching_tools_and_diagnostic_first_instruction`
    fails on an existing `ListComp` lacking `.id`.
  - Ignoring that pre-existing agent-tool test file: **402 passed, 62 skipped**,
    then `test_pedagogy.py::test_coaching_reads_private_references_without_returning_them`
    fails because the mocked completion client was not called.
  - No files owning those failures were modified. Do not claim these attempts
    as complete baseline comparisons; the initial baseline stopped at its
    first failure.
- [REST configuration/prerequisites](../../mathbank-rest/README.md#socratic-studio-staff-authentication)
  document all variables, existing-client flow/scope/revocation/IAM
  prerequisites and local same-origin proxy requirements. Presence-only check
  initially found no configured pool, client ID, client secret, dedicated CSRF secret or
  trusted Studio origins in the selected REST environment; secure cookies
  remain enabled. No secret values were printed, copied or generated.
- Initial live blocker (configuration now resolved below): load the **existing** approved pool/client and dedicated
  CSRF/origin settings through secure configuration, verify scoped IAM,
  app-client flow/scope/token-revocation prerequisites, then perform a real
  staff browser login → restore → current-session logout → rejected replay.
  Never ask for a password in chat or create accounts without approval.
  MFA/new-password challenge completion and session refresh remain unsupported;
  explicit challenge failures are not successful authentication.
- Source-only [OpenAPI](reference/openapi.json) and
  [operation inventory](reference/REST_ENDPOINTS.md) cover **327 paths /
  351 operations / 184 schemas** from revision
  `a0041e2bc53818b9d06e67d836a5b6d701872fb0` plus worktree changes. This includes
  pre-existing source additions absent from the older snapshot (question-pool
  matching and paper failure); they were not implemented by this auth step.
  No handlers, DB operations, paid calls or server restarts were used to
  generate these references. DDL/graph evidence remains unchanged.
- Next executable implementation: **Step 02**. Read the DB skill, actual next
  migration number, canonical FK targets and existing outbox/audit patterns;
  mark it in progress before editing. Do not deploy or mark Step 01 live
  complete merely because persistence can be tested offline.

### Follow-up: resolved configuration, regressions and non-AWS provision

- Existing Cognito config was privately copied from `mathbank-web/.env` using
  [the tested setup tool](../../mathbank-rest/scripts/setup_socratic_auth.py).
  Only the selected Cognito fields were copied; a new dedicated random CSRF
  secret was generated, valid existing secrets preserved, and settings were
  atomically saved with permissions `0600`. No values were printed.
  REST is currently in **Cognito mode**, trusted browser origin
  `http://127.0.0.1:5186`, local-only non-secure cookies and the explicitly
  scoped workstation AWS profile. No persistent local password was invented
  or saved; interactive local setup prompts the operator privately.
- Read-only AWS observation, **2026-10-25 UTC**, account `848941468793`,
  region `us-east-2`: existing pool/client metadata confirms
  `ALLOW_ADMIN_USER_PASSWORD_AUTH`, token revocation enabled and matching
  configured client secret; pool MFA observed `OFF`, not modified.
  Official AWS MCP timed out; authorized CLI/SDK fallback was used.
  The existing `login_session` profile needed the missing CRT dependency;
  runtime manifest now declares `boto3[crt]` and the required extra was restored
  using the existing `uv` package manager. No policy/account/client changes.
- Local mode is **explicit**, not a provider-error fallback:
  [local session store](../../mathbank-rest/src/mathbank_rest/socratic_local_auth.py)
  uses random opaque tokens with hashes in a bounded locked in-memory store,
  bcrypt credentials, expiry and current-session revocation. It requires
  loopback origin, hostname and peer; known Lambda/ECS runtimes are rejected.
  Credentials/CSRF/capability changes and restart invalidate local sessions.
  Namespaced `local:` principals and a visible UI warning prevent conflating
  test identity with Cognito approval. Default capability is author only.
- [Standalone local auth server](../../mathbank-rest/scripts/run_socratic_local.py)
  imports only the actual staff boundary, not full-app data/model integrations.
  `make setup-socratic-local` prompts for a password; `make run-socratic-local`
  serves one loopback process. It intentionally leaves unfinished catalog
  routes as visible 404s. No fabricated workflow/model/evaluation success.
- Regression root causes and fixes:
  - Learning-context agent wrapper intentionally sends `enrich=false`;
    assertion now checks both encoded path and explicit read-only query.
  - Tool-registration AST contains filtered collections and factory calls;
    inspect direct/starred names without assuming every element is a Name.
    Keep required-tool assertions and updated guided-mode answer-withholding
    instructions. No tutor runtime/instruction was changed.
  - Coaching/solution-guidance tests unintentionally queried the configured
    database's published routes before reaching mocked model/reference paths.
    Fixture those fast paths explicitly, with dedicated tests retaining
    published-route precedence. Do not remove published-first behavior.
- Follow-up verification:
  - Full `cd mathbank-rest && .venv/bin/python -m pytest -q --disable-warnings`:
    **804 passed, 134 skipped** after the AWS-runtime guard test was added.
    Skipped integration tests are not live schema/deployment acceptance.
  - `make test-socratic-offline`: **56 passed** in its standalone run; the
    subsequently added AWS-runtime rejection test also passed in the full
    suite, giving **57 covered cases** in this target. Synthetic Cognito,
    actual local sessions, setup and legacy learner security; no AWS/model
    or database operations in this selected target. A final redundant
    subset/build rerun was denied by the tool approval layer; it was not
    bypassed. The completed full-suite, TypeScript and prior build results
    above remain the verification evidence.
  - Focused Ruff passes; mypy passes for auth service/local store/router and
    both setup/run scripts (**5 source files**).
  - Frontend `npm test`: **24 passed**; TypeScript/production build pass
    (existing ~544 KB bundle warning remains).
  - `npm run test:e2e:local-auth`: **2 passed**, desktop/mobile actual
    browser → Vite → REST local login/cookies/CSRF/restore/logout/replay;
    no API interception. Synthetic test-only credentials, no saved traces,
    loopback-only test backend network. Both temporary servers stop.
  - `npm run test:e2e`: **8 passed**, separate synthetic prototype regression
    suite. It is not proof of workflow persistence.
- **Remaining gates:** an existing staff member must complete real Cognito
  login → GetUser/current-group check → logout → rejected replay. Do not ask
  for their password in chat or manufacture a user. Successful read-only
  metadata/config checks are not authentication or IAM authorization proof.
  No running full service was restarted or cloud stack redeployed.
  Hosted CDK/SSM mapping and pool-scoped REST IAM are still step 05; do not
  deploy local credentials, workstation profiles or insecure loopback settings.
  MFA/new-password challenge completion and refresh remain unsupported.
- Operator commands and mode switching are documented in the
  [REST README](../../mathbank-rest/README.md#interactive-non-aws-testing)
  and [frontend README](../../mathbank-socratic-admin/README.md#local-staff-login-without-aws).
  Step 02 remains the next implementation step, not silently started here.

## Step 02 execution record

- Date: **2026-10-25 UTC**; source revision
  `a0041e2bc53818b9d06e67d836a5b6d701872fb0` plus relevant uncommitted worktree.
  The user explicitly selected **additive Neon schema + isolated Socratic API
  stack**, not a shared REST deployment.
- Delivered [migration 053](../../mathbank-db/sql/053_socratic_drafts.sql):
  four isolated `orchestration.socratic_*` tables, 20 DRAFT candidate strategies
  across eight domains, immutable revision/command/strategy protections,
  deferred current-revision FK, strict schema-version check and restrictive
  source FKs. Applied only to the authorized REST-configured Neon target;
  repeated successfully. Scoped live metadata confirms all four column sets,
  61 constraints including NOT NULL metadata, and three application triggers.
  [Complete incremental schema/access catalog](reference/postgres/orchestration.md).
- Implemented [strict prototype IR](../../mathbank-rest/src/mathbank_rest/socratic_contracts.py),
  [transactional service](../../mathbank-rest/src/mathbank_rest/socratic_service.py),
  [staff API](../../mathbank-rest/src/mathbank_rest/routers/socratic.py),
  server-side workflow pagination, explicit source revision selection, compatible
  route filtering and safe retry receipts in the UI. No required prototype
  feature was removed to fit this schema.
- Create/update require verified `author`, exact Origin/CSRF and
  `Idempotency-Key`; updates additionally require expected hash. Sources bind
  explicit solution revision and matching published route. Same key/input
  replays the exact immutable response; changed input/stale expected hash is
  409. Workflow locking precedes a fresh revision read, avoiding a stale
  joined snapshot after waiting for another writer.
  Published routes also must match the existing compiler's exact **current
  source hash**, not merely the same solution UUID and PUBLISHED label;
  obsolete releases fail explicitly with `SOCRATIC_ROUTE_STALE`. Both stale
  and current source-hash branches are covered by regression tests.
- Workflow/revision/receipt plus existing audit/outbox commit atomically.
  Injected outbox failure rolled back all effects. Ordinary selected-target
  tests, including real local cookie/CSRF API → Neon persistence, rolled back.
  **One explicitly opted-in concurrency fixture remains:** a labeled
  `synthetic:socratic-test:*` owner with one workflow, two revisions, two command
  receipts and matching audit/outbox rows. Two simultaneous duplicate creates
  returned one identity; two saves from the same hash yielded one winner and
  one 409 loser. No canonical/real-learner rows were written. Immutable evidence
  was not deleted or bypassed for test cleanup.
- [Local launcher](../../mathbank-rest/scripts/run_socratic_local.py)
  preserves auth-only offline default; optional `--with-drafts` uses real
  REST-configured Postgres, bound to loopback with proxy headers disabled.
  This is not an offline database fixture or a deployed local-auth mode.
- Isolated [CDK entrypoint](../../mathbank-infra-aws/socratic_app.py) and
  [stack](../../mathbank-infra-aws/stacks/socratic_service_stack.py) deployed
  **`MathBankSocraticStack`** / function **`mathbank-socratic-api`** in
  account `848941468793`, `us-east-2`. No shared `MathBankRestStack` update.
  Same-origin SPA + isolated API:
  **<https://tzgysffipx6fiomvaqpcxzlxqu0gozfp.lambda-url.us-east-2.on.aws/>**.
  Three selected SSM SecureStrings, exact SSM/pool-scoped IAM, secure Cognito
  cookies, no workstation profile/local credentials, 512 MB/30-second requests,
  one-week logs, no AgentCore/Bedrock/Step Functions permissions.
- First deployment rolled back because reserved concurrency 2 would violate
  AWS's required minimum 10 unreserved executions; actual account limit is 10.
  **User explicitly chose `account-limit`: deploy without a function reservation.**
  The successful deployment shares existing account concurrency, not a hard
  function cap. No quota increase or change to other functions was made.
- Official AWS MCP identity check timed out; scoped CLI/SDK fallback was used.
  Infra's declared `python-dotenv` dependency was restored after the import
  failed. Container builds copy selected manifests/source/UI only, with
  named external contexts included in asset fingerprinting; template/staged-asset
  checks reject secret leakage.
- Hosted browser verification caught an embedded-font CSP violation. Added
  `data:` to font sources (not scripts), redeployed and verified local/bundled
  fonts load. The final hosted login screen passed at **exactly 1440 and
  390 pixels**, one h1, no horizontal overflow, no runtime/CSP errors.
  Integrated-browser auto-resize made one immediate resize measurement
  inconclusive; isolated headless contexts established the actual viewport
  assertions. Swagger CDN pages are disabled on the isolated app;
  `/openapi.json` remains available.

### Step 02 reproducible verification

| Command / check | Result |
|---|---|
| `cd mathbank-rest && .venv/bin/python scripts/migrate_socratic_drafts.py --apply --direct` | Applied and repeated; four tables present, no canonical/learner writes |
| `SOCRATIC_DB_TESTS=1 .venv/bin/python -m pytest -q --disable-warnings` | **824 passed, 135 skipped**, five existing warnings; other suites' opted-in integrations remain skipped |
| `SOCRATIC_DB_TESTS=1 SOCRATIC_CONCURRENCY_TESTS=1 ... pytest -q tests/test_socratic_postgres.py` (earlier six-case version) | **6 passed**, including genuine two-connection duplicate-create/CAS acceptance |
| `SOCRATIC_DB_TESTS=1 ... pytest -q tests/test_socratic_postgres.py` (expanded HTTP/failure version) | **7 passed, 1 skipped**; concurrency opt-in intentionally off to avoid accumulating fixtures |
| Focused Ruff and mypy | Passed; mypy covers four API modules plus migration, local launcher and deployment checker |
| `cd mathbank-socratic-admin && npm test && npm run build` | **25 passed**, TypeScript/build pass; existing ~545 KB bundle warning remains |
| `npm run test:e2e` | **8 passed**, full prototype fixtures at desktop/mobile; not live grading |
| `npm run test:e2e:local-auth` | **2 passed**, real loopback auth with outbound nonloopback sockets blocked |
| `make synth-socratic`; `python -m unittest discover -s tests -v` | Selected stack synthesized; **3 passed** for scoped IAM, configuration/bounds and secret exclusion |
| `make deploy-socratic` | Selected stack deployed successfully after approved concurrency change; subsequent UI/CSP fixes deployed |
| `python scripts/verify_socratic_deployment.py --url <Studio URL>` | **PASS**: real database readiness, exact hosted/source isolated OpenAPI and built SPA, no-store 401s, foreign-origin 403 before provider access, safe 422 and legacy-route absence |

The screened **main REST source** snapshot is now **333 paths / 359 operations /
202 schemas**. Hosted isolated OpenAPI is a separate, strictly smaller surface;
it matched `socratic_app.app.openapi()` exactly. This is not proof the shared
deployed REST API has been updated.

Broader database-package suite remains separately blocked in the existing
REST interpreter by missing `tiktoken` during `mathbank-db/etl/embed_corpus.py`
collection; no unrelated embedding dependency was installed. Do not claim all
repository/paid integration suites green.

### Step 02 remaining acceptance / next handoff

- **Successful Cognito staff login, fresh groups, protected hosted draft write/
  read and logout/revoked-token replay remain unverified.** Use an existing
  authorized staff user in the hosted browser, entering credentials privately;
  do not request passwords through chat or fabricate a cloud identity.
  Readiness and denial tests are not IAM/login proof.
- Real local auth → real Neon persistence is verified, but local identities are
  not Cognito attestations. Hosted local auth is forbidden.
- Step 03 is next: current-node safe activity DTO, existing scorer adapters,
  five AR cases, preview hash/version CAS, hints/reveal and disclosure tests.
  Evaluation/simulation/proposals currently fail visibly; no fallback grades,
  fake AWS success or production publication exists.
- Steps 04/05 still own DeepSeek V3.2 AgentCore packages, bounded proposal jobs
  and Step Functions/Lambda orchestration. The draft hosting stack does not
  mark those steps delivered. Full inspector/review/visual work remains gated
  exactly as in the ledger.
- No paid inference occurred. Lambda/ECR/log/SSM request/storage charges may
  accrue; no billed-cost total has been verified. The **$20** authorization is
  not an automatic AWS billing cutoff. No new NAT/ALB/VPC/provisioned concurrency.
- Temporary test servers/browsers terminate at test completion. Colima is the
  existing shared local build runtime; it was left available, not billed AWS
  compute. No commits made; preserve the dirty worktree.

## Resumption checklist

1. Read this ledger, requirement 65, affected project README/skill and source.
2. Inspect `git status`; do not assume the last agent committed its changes.
3. Reproduce the smallest relevant baseline; distinguish unrelated failures.
4. Mark the selected step `IN PROGRESS` and record concrete scope/files.
5. Implement through the owning service and test exact contracts/failure cases.
6. Record commands/results and deployment evidence, then mark the appropriate
   offline/live status. If blocked, name the blocker and next safe action.
7. Refresh source OpenAPI/reference when API changes; schema reference when DDL
   changes. Never substitute a documentation claim for actual runtime evidence.
