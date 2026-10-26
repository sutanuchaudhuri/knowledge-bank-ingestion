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
| 03 Synthetic response/evaluation/help | **COMPLETE (implementation, Neon migration 054, local live acceptance, hosted deploy 2026-10-26)** | **Local browser → local API → Neon verified; hosted `MathBankSocraticStack` redeployed and `make socratic-verify` PASS (2026-10-26); Cognito staff sign-in and AR golden-case approval still pending** | Shared `activity_scoring` (micro-course refactored onto it), AR1–AR5, pinned private activity snapshots, CAS/idempotent preview events, hints/reveal as assisted. 872 REST passed/135 skipped; 10 preview DB + 12 offline + 23 scorer tests; 25 UI unit; live desktop/mobile browser run. |
| 04 AgentCore proposal package | PENDING; depends on 02 | Pending | Bounded DeepSeek typed proposals, minimal context, exact eligibility, prompt/model provenance, explicit staff acceptance, stale-result rejection. |
| 05 Step Functions/Lambda/CDK | PENDING; depends on 04 | Pending | Isolated optional stack in existing CDK app, scoped IAM, durable intent/reconciliation, token/time/job limits and pause switch; selected-stack synth/test/deploy. |
| 06 Live Neon/AWS vertical acceptance | PENDING; depends on 03 and 05 | Pending | Real authenticated browser → REST → Neon → Step Functions/AgentCore → persisted proposal → explicit accept; receipts, bounded spend, failed-job/replay tests. |
| 07 Complete node inspector/graph editing | PENDING; depends on 02 and 03 | Pending | Full typed configs, source claims/activity/rubric refs, H1-H5 policies, lineage-aware split/merge/reorder/branch/return validation, accessibility and original UI detail. |
| 08 Mathematical/pedagogical review cockpit | PENDING; depends on 06 and 07 | Pending | Separate verified capabilities, exact-hash attestations, no stale/self-authorized publish, immutable release/retirement and operational activation. |
| 09 Visual/attachment integration | PENDING; depends on 03 and 07 | Pending | Reuse widgets/scene/artifact services, immutable reviewed refs, before/after disclosure, source rights/accessibility, safe video adapter; same student/preview resolver. |
| 10 Remaining framework and pilot | PENDING; depends on 08 and 09 | Pending | All node/assessment kinds, published structural graph, operations/projection/reindex controls, eight domains/20 strategies, S01-S22 and independent SME acceptance. |

Unified-portal steps 11–20 plus 12b (quizzes, videos, exams, student feature access, the reuse-first
vector **Finder**, assistant, micro chat) are proposed in [68](68_UNIFIED_STUDIO_PORTAL_PLAN.md) and are
**not started** until its open decisions (D-1, D-2, D-4–D-13, D-15–D-17) are reviewed.

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

## Step 03 execution record

- Date **2026-10-25**. Scope: synthetic preview evaluation/help only; no learner,
  mastery, course-progress or activity-response writes; no model or AWS calls.
- **Local password provisioning (user request):** `make socratic-password` runs
  [setup_socratic_auth.py](../../mathbank-rest/scripts/setup_socratic_auth.py)
  `--generate-password --credentials-only`: a random `secrets.token_urlsafe(18)` password is
  saved as `SOCRATIC_LOCAL_PASSWORD` plus its bcrypt hash in the gitignored, mode-600
  `mathbank-rest/.env`, without changing `SOCRATIC_AUTH_MODE` (REST stays Cognito; the local
  launcher forces local mode for its own process). Re-running rotates it. `.env` is
  excluded from Docker assets and never seeded to SSM. `sync-env.sh` rewrites
  `mathbank-rest/.env` (with backup) — rerun `make socratic-password` afterwards.
- **Scorer (SOC-ASMT-01/02/03):** [activity_scoring.py](../../mathbank-rest/src/mathbank_rest/activity_scoring.py)
  is now the single deterministic evaluator; `micro_course_service.submit_activity_response`
  calls it with unchanged semantics (MCQ `correct_index`, NUMERIC exact within 1e-9).
  Added MULTISELECT (`correct_indices`) and Assertion–Reason as a five-option MCQ whose key
  is derived from `assertion_reason.{assertion_true,reason_true,reason_explains}`; truth and
  entailment judgments are retained separately as private evidence. Inconsistent policies are
  unscoreable. SHORT_RESPONSE abstains (`UNCERTAIN`); rubric assistance is step 04.
  `live_runtime` poll scoring (`correct_option`) was not changed.
- **Migration [054](../../mathbank-db/sql/054_socratic_previews.sql)** applied (and 053
  re-applied idempotently) on the authorized Neon target: `orchestration.socratic_preview`
  (owner, pinned workflow revision/hash FK, private `activity_snapshot`, CAS `state_version`,
  position, budget, hint/reveal state) and immutable `socratic_preview_event` (idempotency
  key + request hash, decision, private response/evidence, exact returned DTO for replay).
- **API** ([service](../../mathbank-rest/src/mathbank_rest/socratic_preview.py), router):
  `POST /workflows/{id}/simulate`, `GET /previews/{id}`, `POST /previews/{id}/respond|assist|
  reveal|transition`. Pre-answer DTO allowlists node, activity prompt, safe option keys
  (`AR1`–`AR5` or positional), kind and pinned snapshot revision — never keys, policies,
  hints not yet disclosed or future nodes. Routing: exact outcome, else ALWAYS; lowest
  priority number wins; RETRY without a rule stays; otherwise fallback; budget exhaustion ends
  at fallback. CORRECT→SUCCESS, INCORRECT→RETRY, abstain→UNCERTAIN; after an explicit reveal a
  correct answer is capped at UNCERTAIN (assisted, not independent). Hints come from the
  activity's `hints` (≤5) and mark later decisions `assisted`. Same key+payload replays the
  stored result; changed payload, stale version, saved-draft change, stale screen or ended
  preview → 409. Structural validation now reports unbindable `activity_ref`s.
  `/health` now reports `evaluation_available: true` with scope `SYNTHETIC_PREVIEW_DETERMINISTIC`.
- **UI:** renders the activity prompt, numeric input hint, transition budget and assisted
  history pills; contract allows server `null`s.

### Step 03 verification

| Command / check | Result |
|---|---|
| `make socratic-migrate` | 053+054 applied; six `orchestration.socratic_*` tables EXIST |
| `pytest tests/test_activity_scoring.py` | **23 passed** incl. five AR golden cases (AR1–AR5) |
| `pytest tests/test_socratic_preview.py` | **12 passed** offline (routing, DTO allowlist, client-grade rejection, OpenAPI/CSRF) |
| `SOCRATIC_DB_TESTS=1 pytest tests/test_socratic_preview_postgres.py` | **10 passed**, all rolled back: full journey, no learner writes, replay/conflict/stale/owner, snapshot pinning, reveal cap, budget, unsupported bindings, start rules, immutable events |
| `SOCRATIC_DB_TESTS=1 pytest -q` (full REST) | **872 passed, 135 skipped** |
| micro-course regression | 15 passed, 17 skipped (unchanged behavior) |
| `npm test`; `npm run typecheck` | **25 passed**; clean |
| Live: `make socratic-start DRAFTS=1`, API via Vite proxy | login → create/save draft bound to an existing MCQ (read-only) → simulate → respond (STAY_ON_NODE) → no-hint 409 → reveal → capped UNCERTAIN → fallback; no key leakage |
| Live Playwright browser, 1440/390 | question + 4 options + server feedback; no overflow or page errors |

Persistent synthetic evidence from the live run: one draft "Live step 03 acceptance
(synthetic)" owned by the `local:` principal with its preview rows (immutable by design).

### Step 03 remaining gates

- The five AR golden cases are self-checking test fixtures; **staff mathematical approval is
  still required** (SOC-ASMT-02) and is not claimed.
- No AR/MULTISELECT `activity.definition` rows exist yet; authoring them writes the shared
  activity table and needs explicit approval (the admin activity API accepts the policy).
- ~~Hosted stack not redeployed~~ — **done 2026-10-26** (see the hosted deploy record below).
- A real Cognito staff sign-in on the hosted URL (and a hosted preview run) is still unverified.

### Step 03 hosted deploy record (2026-10-26)

| Command | Result |
|---|---|
| `make socratic-test` | 108 passed, 18 skipped (UI vitest + typecheck + REST Socratic) |
| `aws login --profile aws-sutanu-admin` | session renewed (it had expired) |
| `make socratic-diff` | only change: `SocraticFunction` container `ImageUri` (no IAM/URL/other resource changes) |
| `make socratic-deploy` | ✅ `MathBankSocraticStack` updated in 53 s; StudioUrl unchanged `https://tzgysffipx6fiomvaqpcxzlxqu0gozfp.lambda-url.us-east-2.on.aws/` |
| `make socratic-verify` | **PASS**: hosted readiness, exact isolated source OpenAPI/SPA, no-store 401, foreign-origin 403, safe 422, legacy-route absence. **NOT VERIFIED**: Cognito staff sign-in/groups, protected cloud persistence, logout/revocation, model/orchestration jobs |
| `GET /health` | `evaluation_available: true`, `evaluation_scope: SYNTHETIC_PREVIEW_DETERMINISTIC`, `model_jobs_available: false` |
| Unauthenticated `POST /v1/admin/socratic/previews/{id}/respond` | 403 (denied) |
| Playwright 1440/390 on the hosted URL | rebuilt sign-in page renders, one `h1`, no overflow, no page errors |

The hosted Studio now serves the step 03 API and the rebuilt UI (rail, searchable sidebar, drawer,
Flow / Natural language / JSON).
- Free-form rubric assistance, AI decisions and proposal jobs remain steps 04–05.

## Roles, role switching and user management record (2026-10-26)

**Request:** create an admin and a student group in Cognito, add `sutanu.chaudhuri@gmail.com` to
both, let the user see and switch role (switching changes access), and add a user-management screen
for access patterns and admin password/security actions.

**Cognito (pool `us-east-2_wQePckX1G`, "mathbank-exam-students")**
- Reused the existing **`Admins`** group (already the Studio/mathbank-web/live admin group — a second
  admin group would split access). Created **`Students`** (precedence 10).
- `sutanu.chaudhuri@gmail.com` (CONFIRMED) added to **Admins** and **Students**. Note: Admins also
  grants mathbank-web/live admin UI access.

**Design (server-enforced)**
- Studio sign-in still requires `Admins`. Roles: `admin` (author + `manage_users` + `preview`, plus
  reviewer/publisher capabilities from their groups) and `student` (`preview` only: list/open
  workflows and run the simulator — no authoring, strategies, sources, AI or users). `student` is
  offered only to Admins who are also in `Students`; Students-only users cannot enter the Studio.
- Active role lives in an HttpOnly `mathbank_socratic_role` cookie; it can only **narrow** what
  current group membership grants (forged values fall back to the first granted role).
- `PUT /session/role` (CSRF), `POST /session/password` (Cognito `ChangePassword`, current password
  required), `/users*` routes (capability `manage_users`): search, detail, group add/remove,
  password reset (Cognito emails a code), global sign-out, disable/enable. Self-lockout guarded
  (cannot remove own Admins, disable, reset or sign out yourself).
- Access patterns: Cognito sign-in history needs the Plus tier (pool is Essentials), so the Studio
  appends sign-in success/failure, sign-out, role switch, password change and every admin action to
  the existing **`audit.action_log`** (entity `STAFF_USER`, `after_state` has role/group, a /24 or /48
  IP prefix and a truncated user agent; never passwords). Enabled by `SOCRATIC_ACCESS_AUDIT=true`
  (hosted stack, local `DRAFTS=1`); off for offline tests. No migration needed.
- UI: rail shows only views the role allows (Users & access for `manage_users`); top-bar role pill and
  avatar open the **Your account** drawer (role segmented switch, change password); Users view with
  search, group chips, status pills, role matrix and a user drawer (groups, 30-day access stats,
  recent activity, confirm-gated security actions).
- IAM (Socratic stack only, scoped to the one pool): `ListUsers`, `ListUsersInGroup`, `AdminGetUser`,
  `AdminAdd/RemoveUserToGroup`, `AdminResetUserPassword`, `AdminUserGlobalSignOut`,
  `AdminDisable/EnableUser` (plus existing `AdminInitiateAuth`, `AdminListGroupsForUser`).

**Files:** `mathbank-rest/src/mathbank_rest/{config.py,socratic_auth.py,socratic_users.py (new),routers/socratic.py}`,
`scripts/run_socratic_local.py`, `tests/test_socratic_users.py` (new) + updated auth tests, Makefile
targets; `mathbank-socratic-admin/src/{contracts.ts,App.tsx,Sidebar.tsx,Users.tsx (new),styles.css}`,
`tests/Users.test.tsx` (new), `e2e/local-auth.spec.ts`, `e2e/local_auth_server.py`;
`mathbank-infra-aws/stacks/socratic_service_stack.py`.

| Verification | Result |
|---|---|
| `make socratic-test` | UI 38 passed (+4) + typecheck; REST **121 passed**, 18 skipped (+13 role/user tests) |
| `make socratic-e2e` | prototype 8 passed (one mobile case flaked once, passed 3/3 on rerun); local-auth 2 passed incl. real role switch surviving reload |
| `make socratic-diff` | IAM statement + image only |
| `make socratic-deploy` | ✅ 73 s, same StudioUrl |
| `make socratic-verify` | PASS (same scope as before) |
| Hosted unauthenticated `GET /users` / `PUT /session/role` without CSRF / foreign-origin reset | 401 `STAFF_SESSION_REQUIRED` / 403 / 403 |

**Not verified by the agent:** a real Cognito sign-in (needs the user's password), role switch and
user actions on the hosted URL. Admin password reset makes Cognito email a code; the user completes it
through a "forgot password" flow (mathbank-web has one; the Studio sign-in does not yet).

## UI re-baseline record (2026-10-25)

User direction: make the Studio clean and simplified like
[`UI/index (1).html`](../copilot-instructions/mathbank-adaptive-socratic-framework/UI/index%20(1).html),
with a searchable left navigation backed by a separate search module, a detail view where the
admin works, and the flow viewable as JSON or natural language.

- Rebuilt [mathbank-socratic-admin](../../mathbank-socratic-admin/README.md#layout-and-authoring-workflow)
  as icon rail · searchable sidebar · canvas · detail drawer. New modules:
  [search.ts](../../mathbank-socratic-admin/src/search.ts) (pure multi-term search across
  drafts, open-workflow steps/rules and strategies), [narrative.ts](../../mathbank-socratic-admin/src/narrative.ts)
  (plain-language flow), `Sidebar`, `Panels` (step/rule/new-rule/new-step/new-workflow/settings
  drawers), `RulesView`, `Library` (strategies/sources/steps). Removed the cluttered
  `RuleEditor`, `Rules` and `Resources` screens. **No capability was removed**: every
  previous action (draft paging, create/open/save/discard/validate, strategy/entry/fallback/budget,
  source linking with explicit revision, node/edge CRUD and annotations, AI proposal adjust/accept,
  preview start/respond/hint/reveal/simulate/refresh/history, conflict reload, sign-out) is
  reachable from the drawer, settings or a collapsed section. API calls are unchanged; no backend
  change. Added Escape to close the sidebar/drawer; fixed an off-canvas sidebar that stayed
  focusable on phones.
- Verification: `npm test` **34 passed** (incl. 5 new search/narrative tests and rewritten App
  tests); typecheck and production build pass; `npm run test:e2e` **8 passed** and
  `npm run test:e2e:local-auth` **2 passed** at 1440/390; live browser run against local
  API + Neon at 1440/390: one h1 per view, no horizontal overflow, no console errors. Hosted
  stack not redeployed.

## Operator tooling and documentation record (2026-10-25)

Status: **COMPLETE (tooling/docs; no deployment, migration or AWS mutation performed).**
Step 03 remains the next implementation step and was not started.

- Root [Makefile](../../Makefile) `socratic-*` targets delegate to
  [Studio](../../mathbank-socratic-admin/Makefile), [REST](../../mathbank-rest/Makefile) and
  [infra](../../mathbank-infra-aws/Makefile): install/test/e2e/build; local
  `socratic-setup-local`, `socratic-start|stop|restart|status|access` (staff API `:8019`
  pidfile `.socratic.pid`, UI `:5186`, `DRAFTS=1` for real Postgres drafts);
  `socratic-migrate`; AWS `socratic-seed|synth|diff|deploy|verify|outputs|destroy`.
  New infra targets `diff-socratic`, `outputs-socratic`, `destroy-socratic` exist because the
  shared `destroy`/`outputs` use `app.py` and never covered this stack.
- New [mathbank-socratic skill](../../.github/skills/mathbank-socratic/SKILL.md); Socratic
  sections added to the `mathbank-local-services` and `mathbank-infra-aws` skills. Root
  [README](../../README.md) now includes the Studio in the repository map, flowchart, C1/C2,
  admin authoring flow 7, student/synthetic-preview flow 8, the `orchestration` schema row
  and ER diagram, and a Socratic quick start. All changed Mermaid blocks render (mmdc).
- Verification: `make socratic-test` → UI **25 passed** + typecheck, REST **70 passed /
  8 skipped** (DB opt-in); `make socratic-e2e` → **8 + 2 passed**; `make socratic-ui-start`
  → HTTP 200, then `socratic-ui-stop` released `:5186`; `make socratic-access` resolved the
  deployed StudioUrl read-only. `make socratic-start` correctly failed with
  `LOCAL_STAFF_NOT_CONFIGURED` because local staff credentials are operator-set
  (`make socratic-setup-local`); no password was created. Deploy/destroy targets were
  dry-run (`make -n`) only.

Current done/partial/pending architecture and deployment diagrams:
[STUDIO_PLATFORM_ARCHITECTURE.md](../architecture/STUDIO_PLATFORM_ARCHITECTURE.md) — update its status
classes and matrix whenever a step changes state.

## Resumption checklist

1. Read this ledger, requirement 65, the `mathbank-socratic` skill, affected project README and source.
2. Inspect `git status`; do not assume the last agent committed its changes.
3. Reproduce the smallest relevant baseline; distinguish unrelated failures.
4. Mark the selected step `IN PROGRESS` and record concrete scope/files.
5. Implement through the owning service and test exact contracts/failure cases.
6. Record commands/results and deployment evidence, then mark the appropriate
   offline/live status. If blocked, name the blocker and next safe action.
7. Refresh source OpenAPI/reference when API changes; schema reference when DDL
   changes. Never substitute a documentation claim for actual runtime evidence.
