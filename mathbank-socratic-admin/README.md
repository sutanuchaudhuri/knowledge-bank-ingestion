# MathBank Socratic Studio — synthetic draft prototype

Independent React + Vite + TypeScript admin frontend. **This is a synthetic-only
draft UI with a real isolated draft-persistence API, not a student runtime,
grading system, mathematical reviewer or publishing service.** Deployment is
owned by the existing infra project, not this package. See the
[deployment/acceptance ledger](../documentation/requirements/67_SOCRATIC_IMPLEMENTATION_HANDOFF.md)
for the verified hosted scope. Production publishing is deliberately unavailable.

The supplied [UI prototype](../documentation/copilot-instructions/mathbank-adaptive-socratic-framework/UI/README.md)
is the **minimum feature and visual-detail baseline**, not a disposable sketch.
The other twelve framework documents remain required scope. Features not
delivered yet are backlog/release gates, not removed requirements. See
[requirement 65](../documentation/requirements/65_ADAPTIVE_SOCRATIC_ADMIN_AND_AGENTCORE.md)
and the source/atomic-route integration in
[requirement 36](../documentation/requirements/36_STEP_GENERATOR_AND_AUTHORING.md).

## Run and verify

Requires Node 22.12+ (or Node 24) and the repository checkout, including the shared
MathBank UI source files.

```sh
cd mathbank-socratic-admin
make install
make test
make build
make dev
# Reproducible desktop/mobile interaction checks, with test-only intercepted APIs:
npx playwright install chromium
npm run test:e2e
# Real loopback staff authentication without AWS/database/model integrations:
npm run test:e2e:local-auth
```

Development uses `http://127.0.0.1:5186`; Vite proxies same-origin `/v1` to
`http://127.0.0.1:8000`. Set `SOCRATIC_REST_TARGET=http://127.0.0.1:8019`
when REST runs elsewhere. This is a dev-server-only, non-secret proxy target,
not a browser credential. The REST owner must permit this development origin and configure its
session cookie appropriately; HTTPS and secure cookie policy remain mandatory
for hosted environments. Do not put credentials in Vite environment variables.
`make dev` is operator-invoked; no server is left running by implementation tests.
`make start`/`stop`/`status` run the same Vite server in the background (`.server.log`);
from the repository root `make socratic-start` pairs it with the local staff API on
`:8019`, and `make socratic-ui-start` uses the full REST on `:8000`.

`make build` runs TypeScript checking and produces `dist/`. The hosting/infra
owner must route `/v1/admin/socratic/*` to REST on the **same origin**, enforce
HTTPS, private application authorization, CSP and security headers, disable
caching of authenticated API responses, and serve static assets. Root-level
hosting assumes this SPA is mounted at `/`; the three views use hash navigation.

### Local staff login without AWS

Quickest path, from the repository root: `make socratic-password` generates a random
password and saves it as `SOCRATIC_LOCAL_PASSWORD` (plus its bcrypt hash) in the gitignored
`mathbank-rest/.env`, leaving REST's Cognito mode unchanged; read it there, then
`make socratic-start DRAFTS=1` and sign in as `local-author`. Re-running rotates it.

Alternatively, from `mathbank-rest`, run `make setup-socratic-local` and enter your own password
at the terminal prompt, then `make run-socratic-local`. In this frontend run
`npm run dev`; open `http://127.0.0.1:5186` and sign in as `local-author`.
The explicit **Local testing** notice marks the session. See
[REST local-auth instructions and constraints](../mathbank-rest/README.md#interactive-non-aws-testing)
for ports, switching back to Cognito, private settings and single-process expiry.

The standalone local server exposes the **real session endpoints only**.
Add `--with-drafts` to the REST local launcher for real draft persistence
against its configured Postgres. Without that flag, catalog failures are
expected; no fake catalog, grading, model or AWS success is substituted.
`npm run test:e2e:local-auth` starts its own isolated real local API on `8018`
and Vite on `5188`, runs desktop/mobile login → cookies/CSRF → restore → logout
→ rejected replay, and stops both processes. Its synthetic credentials are
test-only, and its backend blocks non-loopback socket connections. Traces are
disabled for that suite so session tokens are not saved in trace artifacts.
The separate prototype suite still intercepts synthetic workflow APIs for
full UI regression checks; neither suite claims live Cognito/Neon/AgentCore.

## Layout and authoring workflow

The Studio follows the clean prototype
[`UI/index (1).html`](../documentation/copilot-instructions/mathbank-adaptive-socratic-framework/UI/index%20(1).html):
an **icon rail** (Designer, Rules by topic, Templates & sources, Student simulator, sign-out),
a **searchable sidebar**, one calm **canvas** and a right **detail drawer** where all editing
happens. Colours and type come from the shared MathBank tokens, not the prototype's palette.
Escape closes the open sidebar (narrow screens) or drawer; edits stay in the unsaved draft.

- **Sidebar search** ([search.ts](src/search.ts), a separate pure module): one box matches all
  words, accent- and case-insensitively, across draft titles/domains (grouped by domain),
  the open workflow's step titles/prompts/topics/rule descriptions and strategy templates.
  Quick actions: *New workflow* and *Export draft JSON*.
- **Designer canvas** has three read representations of the same typed program:
  **Flow** (step cards with their plain-language rules), **Natural language**
  ([narrative.ts](src/narrative.ts): a generated summary plus each step and rule as sentences,
  instructor annotations in parentheses) and **JSON** (read-only typed program with copy).
  Switching never changes the draft; edits go through the drawer.
- **Detail drawer:** *Edit step* (title, student-facing content with rendered math, type,
  connections, add branching rule; topic/objective/activity reference/source claim/accessible
  alternative/remove under *More settings*), *Edit rule* (plain-language description first,
  then from/when/go-to/priority), *Add step*, *Add branching rule*, *New workflow*,
  *Workflow settings* (strategy, entry, fallback, move budget, source, save & validate,
  discard edits, draft identity) and *Ask AI*.

1. Sign in with the REST staff session.
2. Pick or search a workflow in the sidebar, or *New workflow* (title, domain, optional strategy).
3. *Templates & sources → Sources*: choose a canonical problem, explicitly a reference solution
   revision, and optionally a published route, then *Use in current draft*.
4. Click a step or rule card to edit it in the drawer; save from the drawer or the top bar.
5. *Ask AI*: describe a rule, review the proposed sentence, optionally *Compare and adjust*
   source/outcome/destination/priority, then explicitly *Accept into draft* or *Dismiss*.
6. *Student view*: *Save & start preview*, answer the current activity (five-choice
   Assertion–Reason, single/multiple choice, numeric or written), ask for a *Hint*, or confirm
   *Reveal explanation* (assisted). REST scores and routes; *Test routing* and *Student journey*
   are collapsed staff tools. *Preview as student* in a step drawer, or *Steps* in the library,
   starts a new server preview from that step.

The intended chain is **source problem → existing reference-solution / reviewed
route authoring → strategy/workflow overlay** (requirements 36, 39 and 65).
This Studio references existing route releases; it does not implement a second
atomic-step editor, generate canonical steps, edit reference mathematics,
merge/split atomic steps, or replace existing route review/publish
screens. The API supplied here exposes reference IDs/revisions, not reference
solution bodies or route-editing endpoints. Use the existing MathBank route
authoring workspace for those capabilities; no cross-origin admin token or
unverified link is synthesized.

Source verification, structural validity and mathematical/pedagogical human
approval are different things. Catalog reference compatibility and release
eligibility must be checked by REST; selecting a source is not certification.

## API contract

All requests target `/v1/admin/socratic`, use `credentials: include` and
`cache: no-store`. Authentication uses an HTTP-only cookie. The CSRF token is
held only in module memory and sent as `X-CSRF-Token` on every authenticated
mutation, including sign-out. Session creation is the bootstrap exception.
There is **no browser admin API key, localStorage persistence, mock fallback,
embedded answer key, scoring or frontend routing authority**.

| Endpoint | UI use |
| --- | --- |
| `POST /session {username,password}` | Sign in → `{actor,csrf_token,auth_mode}` |
| `GET /session` | Restore server cookie session → `{actor,csrf_token,auth_mode}` |
| `DELETE /session` | Sign out (CSRF protected) |
| `GET /strategies` | `{strategies:[{code,domain,label,status,phases}]}` |
| `GET /resources?q=&limit=25&offset=0` | Source problem / solution revision / route references and `has_more` |
| `GET /workflows?limit=25&offset=0` | Server-paginated owned summaries and `has_more`; at most 25 visible rows |
| `POST /workflows {title,domain}` | Create server-owned initial program |
| `GET /workflows/{id}` | Load draft detail |
| `PUT /workflows/{id} {expected_hash,program}` | Optimistic draft save |
| `POST /workflows/{id}/validate {expected_hash}` | Structural report `{valid,findings}` |
| `POST /workflows/{id}/proposals {expected_hash,instruction}` | Start proposal job |
| `GET /jobs/{id}` | Bounded polling only for queued/running jobs |
| `POST /workflows/{id}/proposals/{job_id}/accept {expected_hash,candidate?}` | Explicit acceptance, optionally of staff-edited edge; REST revalidates |
| `POST /workflows/{id}/simulate {expected_hash,start_node_key?}` | New server-owned preview, optionally from an explicitly requested eligible resource |
| `GET /previews/{id}` | Explicit refresh |
| `POST /previews/{id}/transition {expected_version,idempotency_key,outcome}` | Simulate `ALWAYS`, `SUCCESS`, `RETRY`, `UNCERTAIN` |
| `POST /previews/{id}/respond {expected_version,idempotency_key,current_node_key,activity_id,activity_revision,response}` | Current activity submission, never a client grade |
| `POST /previews/{id}/assist {expected_version,idempotency_key}` | Request next approved current hint |
| `POST /previews/{id}/reveal {expected_version,idempotency_key}` | Confirm explicit assisted current explanation |

The exact TypeScript contract is in `src/contracts.ts`. Programs use
`socratic.prototype.v1`, source references, typed nodes/edges, entry/fallback and
bounded transitions. Detail must declare `prototype_only:true`; previews must
declare `synthetic:true`. Production/non-synthetic responses fail closed. Synthetic
responses contain `{selected_keys}` or `{text}`, never a grade, score, mastery,
arbitrary ASL or hidden assessment definition.

This table describes the **frontend's required contracts**. Sessions,
strategies, resources, draft create/read/update/history, structural
validation and **synthetic preview simulate/respond/assist/reveal/transition**
(ledger step 03, deterministic shared scorer, migration 054) are implemented
in REST. A node binds an activity by setting `activity_ref` to an
`activity.definition` UUID; the preview pins a private snapshot of it and the
current activity DTO adds its `prompt`. Proposal and job endpoints remain
missing and must not be mistaken for delivered behavior because their
controls exist. See the
[screened source OpenAPI](../documentation/requirements/reference/openapi.json).
An unavailable route must fail visibly; there is no runtime test-data fallback.

Draft create/update send an `Idempotency-Key`. Unknown network/5xx outcomes
retain the same receipt for an unchanged retry in the current session;
successful responses and identity changes clear it. Receipts are memory-only,
not durable across reloads: after reloading following an uncertain create,
inspect/refresh server drafts before creating again. Backend receipts remain
immutable. Neither localStorage nor browser-held AWS credentials are used.

### Additive schema contract required by prototype parity

- Nodes retain key/label/type/prompt and add optional topic, objective,
  `source_claim_ref`, `activity_ref` and `accessible_alternative`. The full
  framework node vocabulary is selectable; LESSON/TOPIC retain the original
  resource vocabulary. Exposing an editor option does not implement its runtime.
- Edges add `annotation`, kept alongside typed fields and included in draft
  hashing/audit. The generated typed summary always shows actual current fields;
  annotations explicitly require rechecking after condition changes.
- Only the **current** preview may include `activity` with immutable ID/revision,
  supported response kind and safe option keys/text. No correct key, predicate,
  future activity, rubric answer, source solution or hidden hint is needed.
- `feedback` and `help:{level,text,assisted:true}` come from REST after disclosure
  checks. The UI cannot choose a hint level, infer correctness or claim mastery.
- History extends the existing safe node/reason/source fields with optional
  `from_key`, `to_key`, `outcome`, `rule_id`. Branch highlighting uses only these
  server-returned fields; inspection never creates routing evidence.
- Preview is pinned to its saved hash. Editing **and then saving** the draft
  still requires a preview restart, not just a dirty-state check.

REST must reject unsupported node configurations, cross-source activity refs,
stale versions/hashes and disallowed start nodes. It owns FK relationships,
immutable dependencies, roles, idempotency, atomic commits and scoring. These
TypeScript additions are not a database migration or permission to accept
unvalidated JSON in PostgreSQL.

### Prototype feature traceability

| Reference surface (`UI/index (1).html`) | Studio surface |
| --- | --- |
| Icon rail + searchable topic sidebar | Rail views + domain-grouped draft search that also finds steps and strategies |
| Designer step cards, arrows and branch sentences | Flow view; selected step and last server-selected branch highlighted |
| Edit step drawer with connections | Step drawer with typed fields, rendered math and connection list |
| Plain-language rule editor | Rule drawer: editable description beside the authoritative typed rule |
| “Describe a rule” / Ask AI | Ask AI drawer with server proposal, adjust, explicit accept/dismiss |
| Rules by topic | Topic chips and readable rule rows opening the rule drawer |
| Templates | Strategies (by domain), Sources (problem/solution/route) and Steps tabs |
| Student simulation | Student canvas with server-scored answers, hints, assisted reveal |
| Export draft JSON | Sidebar quick action plus the read-only JSON representation |
| Reset demo | Explicit *Discard unsaved edits* in workflow settings; no demo data |

The offline phrase parser and browser answer keys are replaced by their required
server contracts, **not by removal of the corresponding UI**. Real AgentCore
jobs, evaluation, review and publication remain integration work.

Draft saves occur **before** proposal, validation and simulation. A proposal is
pinned to the saved hash; a dirty or changed draft cannot accept it. The comparison
shows all existing source/outcome edges against the proposed candidate including
destination/priority; the server owns add/replace semantics and exact validation.
Polling stops on success/failure, after at most 60 requests spaced two seconds
apart or a 150-second wall-clock deadline, on dismissal/workflow change/sign-out,
or on unmount. Each API request also has a 30-second timeout. Operators can
explicitly resume status checks after timeout. Requests are aborted on unmount.
HTTP 409 never automatically retries a mutation: explicit server reload discards
the stale draft or refreshes preview state.

Transition calls generate a fresh idempotency key per click and do not
automatically retry network failures. If the response is uncertain, refresh the
preview before another outcome; the server must enforce CAS/idempotency and
reject stale/duplicate state changes.

## Shared design and test coverage

Imports canonical `--mb-*` theme tokens/component surfaces from
`mathbank-web/app/globals.css` and the existing
`mathbank-exam-web/src/components/MathText.jsx` renderer plus its normalizer.
There is no forked normalizer. Inter and Bootstrap Icons are self-hosted. A small
SPA-specific shell uses the same sidebar/breadcrumb/avatar/page-header contract;
the Next.js `AppShell` itself cannot run in Vite.

Vitest + Testing Library tests cover cookie/CSRF requests, conflicts, bounded and
aborted polling, explicit proposal acceptance, save-before-proposal/simulation,
source revision selection, annotations, editable proposals, five-option AR,
response failures, hint/reveal controls, selected branches, resource preview,
hash-pinned restart, 25-row pagination, shared math rendering and keyboard
inspection independent of synthetic position.

Playwright checks all three views at 1440×1000 and 390×844, including two-column
desktop layout, single-column mobile, no horizontal page overflow, math, keyboard
focus, annotated rules, editable proposals, answer/hint flow and library
resources. Every API response in that suite is intercepted test data; it
does not authenticate real staff, grade mathematics, call AWS or write Neon.
The original eight resources and seven routing branches are preserved in the
public-prompt reference test fixture, with explicit START/COMPLETE wrappers.
Fixtures never substitute for unavailable REST responses in the application.

The separate local-auth suite does not intercept session APIs: it verifies actual
local staff cookies, CSRF, restoration, logout/replay and the local-mode notice
at both viewport sizes. Latest verification: **24 unit tests, 8 prototype
browser cases, 2 real local-auth browser cases**, TypeScript and build pass.

### Backend/production-required gaps

REST staff sessions and explicit capabilities are implemented and tested offline
and through the real local-auth browser suite; successful Cognito staff
login/revocation and deployed IAM remain pending. Draft persistence, synthetic preview
persistence, optimistic locking/idempotency and safe current-node serialization are
implemented in REST (steps 02–03). Model jobs, exact patch acceptance semantics,
free-form rubric assistance and the remaining AWS integration
must be supplied and verified by their owning packages. Browser layout/interaction
acceptance with test fixtures is not live integration, real-device certification,
source content rights verification or a production review/release lifecycle. Full course
runtime, arbitrary graph transformations, immutable publishing, learner analytics,
reviewer attestations, all assessment/visual kinds, complete inspector H1–H5
authoring, split/merge/reorder and route-step authoring remain **required,
unfinished scope**. They are not waived or removed by this frontend increment.
