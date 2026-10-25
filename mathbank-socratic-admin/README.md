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

`make build` runs TypeScript checking and produces `dist/`. The hosting/infra
owner must route `/v1/admin/socratic/*` to REST on the **same origin**, enforce
HTTPS, private application authorization, CSP and security headers, disable
caching of authenticated API responses, and serve static assets. Root-level
hosting assumes this SPA is mounted at `/`; the three views use hash navigation.

### Local staff login without AWS

From `mathbank-rest`, run `make setup-socratic-local` and enter your own password
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

## Unified authoring workflow

1. Sign in using the REST administrator session.
2. Create/open a server draft in **Designer + Simulator**.
3. In **Resource Library**, select a canonical problem, explicitly choose a
   reference solution revision and optionally a published route reference.
4. Attach these references to the draft, then select a strategy overlay and edit
   node prompts and typed transition rules. **Rules by topic** filters by the
   actual source-node topic and keeps editable instructor annotations beside
   typed rules, fallback and transition budget; the strategy registry is retained.
5. Save and structurally validate; inspect a model-proposed edge comparison and
   edit source/outcome/destination/priority, then explicitly accept or reject.
   Acceptance changes a draft only.
6. Save/start a synthetic preview. Answer the current public activity (five-choice
   Assertion–Reason, single/multiple choice, numeric or written response), request
   an authorized hint, or explicitly confirm assisted reveal. REST evaluates and
   returns the current safe screen and journey/decision trace. Separate collapsed
   staff controls **simulate** outcomes without pretending they are grades.
   Inspector selection and preview position are independent; graph nodes support
   Arrow Up/Down, Home/End and Tab/Enter. Previous/Next inspect content only.
7. Resource cards retain quizzes, lessons, topics and transfer prompts. **View in
   simulator** requests a new server preview from that resource; it does not move
   an existing session or bypass prerequisites locally.

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
strategies, resources, draft create/read/update/history and structural
validation are implemented in REST. Evaluation/simulation/help/proposals
and job endpoints remain missing and must not be mistaken for delivered
behavior because their controls exist. See the
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

| Reference surface | Retained/enhanced surface |
| --- | --- |
| Dark sidebar, three views, soft cards/pills | Token-based dark shell, breadcrumbs/avatar, responsive navigation |
| Dotted map with selected/current/route states | Two-column map + simulator; independent inspector; text and green selected-edge cue |
| Selected-node outgoing rules | Shared rule editor in inspector and topic view; full source/outcome/destination/priority and editable annotation |
| Natural-language rule + Example | Coauthor on Designer and Rules; example instruction, before/after drawer, editable candidate, Accept/Reject |
| Answer choices / Your thinking / Submit | Safe current-activity renderer and REST response request, not browser answer keys |
| Hint toggle and restart | Server hint request, Hide/Show, assisted reveal confirmation, new hash-pinned preview |
| Journey and latest decision debug | Visible safe trace plus decision panel; no private reasoning/provider dump |
| Quizzes, lessons, topics and View in simulator | Filtered activity cards plus canonical source/solution/route picker |
| Reset example | Explicit discard of unsaved draft edits; no automatic replacement of a durable server draft with demonstration data |
| “Log in as student · Demo” | Explicit synthetic preview identity; never real-student impersonation |

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
login/revocation and deployed IAM remain pending. Server-side reference validation, authoritative draft
and preview persistence, model jobs, exact patch acceptance semantics, optimistic
locking/idempotency, safe current-node serialization and all AWS/Neon integration
must be supplied and verified by their owning packages. Browser layout/interaction
acceptance with test fixtures is not live integration, real-device certification,
source content rights verification or a production review/release lifecycle. Full course
runtime, arbitrary graph transformations, immutable publishing, learner analytics,
reviewer attestations, all assessment/visual kinds, complete inspector H1–H5
authoring, split/merge/reorder and route-step authoring remain **required,
unfinished scope**. They are not waived or removed by this frontend increment.
