# 44. Micro-course mobile platform, AI integration, analytics, and data lifecycle (design plan — backend foundation slice implemented, see §0)

## Comprehensive web/mobile/AI/analytics integration contract

> **Normative correction.** Learner-specific misconception/mastery evidence is private
> PostgreSQL state and must never be projected into the shared Neo4j instructional graph.
> Structural graph projections represent what content teaches/requires/can diagnose, not
> what a particular learner currently knows or misunderstands.

### 44.A End-to-end dataflow

```text
Web / Mobile
   |
   +--> Course runtime
   +--> Interaction runtime
   +--> Tutoring-route runtime
   +--> Scoped AI / video Q&A
   |
   v
PostgreSQL authoritative transaction
   |
   +--> learner/domain event
   +--> immediate deterministic evidence update where required
   +--> audit.action_log
   +--> ai_usage_event when AI is invoked
   +--> pipeline.outbox_event
             |
             +--> analytics rollups
             +--> reconciliation
             +--> notifications
             +--> retention jobs
             X--> NO learner-specific Neo4j writes

Published authoring changes
   |
   +--> micro_course structural projection
   +--> tutoring_routes structural projection
   +--> interaction_template structural projection
   +--> search/embedding pipeline
```

### 44.B Shared packages

```text
@mathbank/course-contract
@mathbank/api-client
@mathbank/interaction-core
@mathbank/scene-spec
@mathbank/semantic-vocabulary
```

Web and mobile share types/vocabulary/geometry/evaluator-safe logic; rendering remains
framework-specific.

### 44.C Mobile primary navigation wireframe

Phone:

```text
┌───────────────────────────────┐
│ MathBank                      │
├───────────────────────────────┤
│ My courses                    │
│                               │
│ Markov Chains        4 / 9    │
│ ███████░░░           Continue │
│ Last: Transition Matrix       │
│                               │
│ Vieta                Complete │
│ ████████████          Review  │
│                               │
│ Recommended                   │
│ Jensen — because: ...         │
├───────────────────────────────┤
│ Home   Courses   Progress  Me │
└───────────────────────────────┘
```

### 44.D Mobile course state wireframe

```text
┌───────────────────────────────┐
│ ‹ My Courses       4 / 9      │
│ Markov Chains                 │
├───────────────────────────────┤
│ ✓ ✓ ✓ ● ○ 🔒 🔒             │
│ Transition Matrices           │
├───────────────────────────────┤
│ [approved video]              │
│ [Ask at 02:23]                │
│                               │
│ [interactive matrix editor]   │
│                               │
│ Feedback                      │
│ Row A totals 1.2              │
│ [Try again] [Why?]            │
│                               │
│ [Start practice problem]      │
├───────────────────────────────┤
│ [Back]             [Continue] │
└───────────────────────────────┘
```

### 44.E Tablet landscape wireframe

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Markov Chains                                               4 / 9   │
├───────────────┬──────────────────────────────────────────────────────┤
│ STEPS         │ Transition Matrices                                 │
│ ✓ Prereq      │ ┌─────────────────┐ ┌─────────────────────────────┐ │
│ ✓ State       │ │ video / scene   │ │ interaction                 │ │
│ ✓ Video       │ └─────────────────┘ └─────────────────────────────┘ │
│ ● Matrix      │ Tutor / feedback                                    │
│ ○ Practice    │ [Ask] [Hint] [Practice problem]                     │
│ ○ Transfer    │                                                      │
├───────────────┴──────────────────────────────────────────────────────┤
│ [Back]                                                 [Continue]   │
└──────────────────────────────────────────────────────────────────────┘
```

### 44.F Offline rules

Offline may:
- render cached published state content;
- preserve local interaction state;
- queue responses/events with `client_event_id`;
- show `Saved offline`.

Offline may not:
- claim authoritative correctness for hidden/server-only scoring;
- confirm misconception evidence;
- advance server-pinned required progress;
- obtain new route hints;
- invoke AI.

Reconnect:
- replay idempotently;
- server evaluates;
- refresh current enrollment/runtime;
- surface conflicts explicitly.

### 44.G Immediate evidence vs batch analytics

Immediate learner feedback:

```text
semantic interaction event
→ server deterministic evaluator
→ interaction_event
→ evidence update
→ feedback
```

Batch:

```text
outbox
→ evidence reconciliation
→ analytics rollups
→ activity timeline
→ notifications
```

Batch never changes canonical graph.

### 44.H AI grounding hierarchy

For in-course AI:

```text
1 approved current transcript segment
2 approved current CourseState Q&A/content
3 approved active InteractionInstance context
4 approved current RouteStep content/hint level
5 published search representations
6 explicitly bound canonical node descriptions
```

No learner-time open-web search.

### 44.I AI policy/usage

Before provider call:

```text
feature enabled?
actor authorized?
explicit consent required/present?
budget/quota available?
approved provider/model?
data scope allowed?
```

Write one `ai_usage_event` for measurable usage with request ID, provider/model,
prompt/completion/total tokens and estimated cost where available.

### 44.J Analytics read model

Recommended rollups:

```text
analytics.course_release_daily
analytics.course_state_daily
analytics.activity_daily
analytics.interaction_signature_daily
analytics.route_usage_daily
analytics.ai_usage_daily
analytics.feedback_daily
```

Cohort misconception analytics:
- aggregate canonical misconception IDs;
- enforce minimum cohort size/privacy threshold;
- never imply a student diagnosis from a single wrong answer.

### 44.K Corrected Neo4j boundary

Allowed structural edge:

```text
InteractionInstance -[:CAN_REVEAL]-> Misconception
RouteStep -[:CAN_TRIGGER]-> Misconception
CourseState -[:WATCHES_FOR]-> Misconception
```

Forbidden learner edge:

```text
Student -[:HAS_MISCONCEPTION]-> Misconception
Enrollment -[:FAILED]-> Skill
```

If a future aggregate learner graph is ever desired, it requires a new privacy-reviewed
projection kind, no student identity, and explicit cohort thresholds.

### 44.L Retention classes

**Retain canonical/versioned**
- published course releases;
- published route releases;
- template/SceneSpec versions;
- review/audit decisions required by policy.

**Retain latest operational state**
- active enrollment/runtime;
- latest derived evidence summary.

**Roll up then purge**
- raw interaction events;
- raw course events;
- old outbox rows after all consumers + safety window.

**AI**
- token/cost metadata may have a different retention period from prompts/responses.

All purge jobs are idempotent and audited.

### 44.M Correlation/observability

Trace with:

```text
request_id
client_event_id
actor
course_release_id
state_id
interaction_instance_id
route_attempt_id
ai_usage_event_id
outbox_event_id
audit_action_id
```

Dashboards distinguish:
- API health;
- publication;
- graph parity;
- search coverage;
- outbox lag;
- analytics lag;
- AI cost/failures;
- asset integrity.

### 44.N Cross-client golden flow

Run same test on Web and mobile:

```text
enroll
→ play approved video
→ timestamp Q&A
→ interaction
→ deterministic error/evidence
→ remediation
→ tutoring-route practice
→ approved hint
→ return to course
→ server-graded checkpoint
→ complete
→ export
```

Verify:
- same contract version;
- same semantic events;
- same server-authoritative evaluation;
- idempotent offline replay;
- same pinned releases;
- correlated audit/AI usage;
- analytics rollup;
- zero learner-specific Neo4j facts.


## 0. Status and scope

**Mostly planning; a scoped backend foundation slice is implemented.** This
document extends
[42_MICRO_COURSE_STUDENT_NAVIGATION.md](42_MICRO_COURSE_STUDENT_NAVIGATION.md)
(the stepper/enrollment JSON contract) and
[43_ADMIN_MICRO_COURSE_AUTHORING_UI.md](43_ADMIN_MICRO_COURSE_AUTHORING_UI.md)
(the admin authoring UI plan) with everything needed to take the student
experience to a native-mobile, AI-integrated, analytics-backed, auditable
product. Every capability below is mapped against **what already exists**
(reused as-is) versus **what is new** (Postgres table, Neo4j projection,
pgvector representation, or REST endpoint) — nothing is proposed in the
abstract. Where a capability has no existing precedent in this codebase,
that is stated explicitly rather than implied.

**Implemented this session** (the subset the admin Activity tab in doc 43
depends on, per explicit user prioritization — mobile app, notifications and
gamification were deferred):
- §5 Auditability — `audit.action_log` (migration 035) + `record_audit_event()`,
  wired into course create/review/publish/deactivate/reactivate.
- §4.1/§4.2 Silent feedback write + queue path — `learner.interaction_event`
  (previously-unwired, migration 033) is now written by
  `record_interaction_event()`, which also enqueues a `LEARNER_SIGNAL` event
  on the existing `pipeline.outbox_event` transactional outbox. The
  *consumer* that evaluates evidence and projects into Neo4j (§4.2's second
  half) is **not** built — this is write+enqueue only, matching this
  section's explicit scoping.
- §7.2 new-endpoint inventory — `/deactivate`, `/reactivate`, `/activity`,
  `/templates`, `/releases/{id}/diff/{other_id}`,
  `/enrollments/{id}/interaction-events`, and `/{code}/preview` (AMC-14) are
  live; see doc 43 §6 for full status per admin-facing requirement.

**Deferred in full** (not started): the React Native app (§2), push
notifications (§2.5), AI tutor-in-course connection (§10), AI token-usage
metering (§44.I), export/cheat-sheet generation (§9), data retention/purge
automation (§6), and the analytics rollup read model (§44.J/§4.3) — the
Activity tab today reads live, matching §4.3's explicit low-volume
allowance, not the rollup table this section also describes.

## 1. Responsive tiers: phone, tablet, desktop

Doc 42 §5 only specified a two-tier breakpoint (≥992px vertical rail /
<992px horizontal row). A tablet (iPad-class, ~768–1024px, both portrait and
landscape) needs its own tier — at 768–991px portrait, a horizontal top
stepper with full labels wastes space differently than a phone; at
1024px+ landscape, a narrower vertical rail (180px, not 240px) fits without
feeling like a phone-sized compromise.

| Tier | Width | Stepper | Content panel | Notes |
|---|---|---|---|---|
| Phone | <768px | Horizontal row, numbered dots, only current step labeled (today's <992px rule, refined) | Full width, single column | Touch targets ≥44px (platform HIG minimum, stricter than the web's 36px floor) |
| Tablet portrait | 768–991px | Horizontal row, current **and adjacent** steps labeled (room for 2–3 labels, not just one) | Full width, single column, max-width capped at ~70ch for reading comfort | New tier; today's CSS collapses straight from 992px to phone behavior, which is correct for landed width but imprecise for tablet step-label density |
| Tablet landscape / small desktop | 992–1279px | Vertical rail, narrower (180px) | `1fr`, same as desktop | Existing ≥992px rule, width-tuned |
| Desktop | ≥1280px | Vertical rail, 240px (today's rule) | `1fr`, capped content width for readability | Unchanged |

This is a CSS/breakpoint refinement to `app/learn/courses/[code]/page.jsx`
and `globals.css` — no new REST/data work.

## 2. React Native mobile app

### 2.1 Why this is additive, not a rewrite

The entire student experience is already contract-driven: doc 42 defines
exact JSON shapes the web reader consumes from
`mathbank-rest`/Next.js proxies. A React Native app consumes the **same**
`/v1/micro-courses/*` endpoints directly (mobile talks to `mathbank-rest`,
not through the Next.js proxy layer, since there is no browser-cookie
session to bridge — see §2.3) with **no new backend logic**, only new
backend *surface* where mobile-specific concerns exist (push tokens,
offline sync cursors — both net-new, see §2.4/§7).

### 2.2 Proposed repo/package

New top-level package `mathbank-mobile/` (peer to `mathbank-web`), **Expo +
React Native** (not bare RN) for OTA updates, managed native modules, and a
single codebase targeting iOS/Android — this matters for a small team
shipping a "one in a million" polish bar without maintaining two native
projects by hand.

| Web concept | Mobile equivalent | Why not shared code |
|---|---|---|
| `InteractionTemplateRenderer.jsx` (SVG via JSX) | Re-implemented using `react-native-svg` | React DOM SVG elements (`<svg>`, `<path>`) don't exist in RN; the *data model* (instance_config → geometry math) is identical and should be extracted into a shared, framework-free `@mathbank/interaction-geometry` package (pure JS: given `instance_config`, return point/path coordinates) consumed by both the web SVG renderer and the RN SVG renderer. |
| YouTube `<iframe>` embed | `react-native-youtube-iframe` (wraps the native YouTube player) or an in-app `WebView` pointing at the same `youtube-nocookie.com/embed/...` URL doc 42 §3.3 already constructs | URL construction logic (`youTubeEmbedUrl()`) is plain JS and *is* shared via the same package. |
| `MathText` (KaTeX via web CSS/JS) | `react-native-katex` (WebView-backed) or server-prerendered MathML/SVG fallback | KaTeX's DOM output doesn't render natively; a WebView wrapper is the pragmatic 1:1, with a fallback of asking the REST layer to return pre-rendered math SVG for offline/low-end-device cases (new, optional, §7). |
| Next.js httpOnly session cookie (`lib/session.js`) | Platform secure storage: `expo-secure-store` (iOS Keychain / Android Keystore) holding the same JWT `mathbank-rest` already issues via `/v1/learner/login` | No cookie jar on mobile; the JWT is sent as `Authorization: Bearer` directly from the device to `mathbank-rest`, meaning **mobile needs CORS/host allowance on `mathbank-rest` for the app's origin/scheme**, a small, explicit backend config change (not a new endpoint). |
| Next.js API proxy routes (`/api/rest/...`) | None — the app calls `mathbank-rest` directly | Fewer moving parts; the proxy layer exists on web only to keep the admin key and session cookie server-side, neither of which applies to a mobile JWT-bearing client. |

### 2.3 Auth and session

- Reuse `/v1/learner/login` / `/v1/learner/register` as-is (same JWT).
- Token stored in `expo-secure-store`; refresh strategy: today's JWT has no
  refresh-token endpoint (`security.create_access_token` is a single
  long-lived token) — mobile should not invent its own refresh flow ahead of
  the web app; if session longevity becomes a mobile-specific problem, it is
  a shared backend change (`/v1/learner/refresh`), tracked as new work (§7),
  not mobile-only.
- Biometric unlock (Face ID/Touch ID/Android biometric) gates *local* access
  to the already-stored token — convenience, not a new auth factor against
  the backend.

### 2.4 Offline support

Mobile is the first client where "offline" is a first-class expectation
(airport, classroom with poor wifi). Proposed tiers, explicitly scoped:

1. **Read-cache (low risk, do first):** the last-fetched published course
   JSON (doc 42 §3.1) and the last-fetched enrollment runtime (§3.2) are
   cached on-device (e.g. `react-query`'s persisted cache / MMKV). A student
   can reopen a course and keep reading without a network call. This is
   pure client-side caching — zero backend change.
2. **Offline quiz answering (medium risk):** a student answers an
   `activity.definition` question offline; the attempt is queued locally and
   replayed against `POST .../activity-responses` on reconnect. Since that
   endpoint is already idempotent-safe per-attempt (it only ever inserts a
   new event row; replays just add another recorded attempt, which is
   consistent with "every attempt recorded," not "exactly one attempt"), no
   backend change is strictly required, but a client-generated
   `client_event_id` (idempotency key) **should** be added to the request
   body and persisted in `learner.micro_course_state_event.payload` so a
   retried replay after a flaky-but-actually-successful request doesn't
   double-count in analytics (§9's rollup should dedupe on this key) — this
   is the one small, explicit backend/data change offline support needs.
3. **Offline `advance` (out of scope for v1):** advancing the server-pinned
   `current_state` requires the optimistic-concurrency `state_version`
   (doc 42 §4) and is **not** made offline-safe in this plan — a student
   without connectivity can keep reading/answering but cannot "move to the
   next step" until back online. Pretending otherwise risks silent,
   un-reconcilable conflicts with the server's authoritative stepper
   position.

### 2.5 Push notifications

New capability (§10 covers the product reason — incentivizing completion).
Expo's push service (`expo-notifications`) needs a device push token stored
server-side against the student, which does not exist today:

- **New table**: `learner.push_device` (`student_id`, `platform`
  (`IOS`/`ANDROID`/`WEB`), `push_token`, `last_seen_at`, `created_at`).
- **New endpoint**: `POST /v1/learner/push-devices` (register/update a
  token), `DELETE /v1/learner/push-devices/{token}` (on logout).
- A scheduled job (not a new always-on service — reuse the existing
  pipeline/outbox worker pattern) reads `learner.micro_course_enrollment`
  for stale `IN_PROGRESS` rows and enqueues reminder notifications (§10).

## 3. "One in a million app" — concrete UX/engineering bar

Avoiding vague superlatives, this is a checklist, each item testable:

| Dimension | Bar |
|---|---|
| Performance | Course JSON → first interactive step rendered in <1s on a mid-tier device on 4G (cache-first per §2.4 makes repeat opens near-instant). |
| Accessibility | Every interactive control (sliders, MCQ buttons, stepper) has a screen-reader label and meets WCAG AA contrast; verified per-template in doc 41's ITL-14-style accessibility_policy, not just "looks fine." |
| Motion | Respect `prefers-reduced-motion` (web) / OS reduce-motion setting (mobile) for any transition/animation — doc 41's `animation_template.reduced_motion_behavior` field already exists for this; it must actually be read client-side, which today's reader does not yet do (flagged gap, §7). |
| Resilience | Every mutating action (advance, activity-response, push-token registration) has a visible pending/error/retry state — never a silent failure (today's `recordActivity`/`advanceEnrollment` already surface `actionError`; mobile must match this bar, not regress to swallowed errors). |
| Personalization | The course catalog (§8's "My micro-courses") ranks/badges courses using *existing* mastery-gap data (`GET /v1/admin/knowledge-gaps`-style queries, scoped to the logged-in student via `/v1/learner/mastery`) — "recommended because you're weak on X," not generic. |
| Consistency | Every pill, icon, and status label matches the vocabulary tables already defined in doc 42 (`STATE_TYPE_LABELS`) and doc 30 (icon vocabulary) — mobile re-exports the same label maps from the shared package in §2.2, not a re-authored copy that can drift. |
| Trust | AI-assisted content (cheat sheets, tutor answers, drafted admin content) is always visibly labeled as AI-assisted with a source/citation, per doc 43's AI-is-a-suggestion principle — carried through to every surface in this document (§12, §13). |

## 4. Silent feedback collection → graph feed

### 4.1 Two tiers of signal (both already schema-modeled; only one is wired)

| Tier | Table | Status today | What it captures |
|---|---|---|---|
| Explicit | `learner.micro_course_state_event` (`event_type='ACTIVITY_RESPONSE'`) | **Wired** (this session) | "Student answered quiz Q with choice/value X, correct=Y." |
| Implicit/silent | `learner.interaction_event` (migration 033; `before_state`/`action_payload`/`after_state`/`evaluation_outcome`/`error_signature`) | **Schema exists, not yet written to** (doc 41's ITL-12 "persisted interaction-event runtime" is explicitly open) | Every manipulation inside a visual interaction — a slider drag, a matrix cell edit, a state-graph click, time spent before the first action, abandoning without completing — matched against `pedagogy.misconception_evidence_rule.error_signature` to accumulate evidence *without the student ever "submitting" anything*. |

**New work**: wire `InteractionTemplateRenderer.jsx` (and its future React
Native twin, §2.2) to emit `interaction_event` rows on meaningful
interaction milestones (not every pixel of a slider drag — debounced to
"settled" values), via a new endpoint `POST /v1/micro-courses/enrollments/{id}/interaction-events` (student-authenticated, mirroring the existing
`activity-responses` endpoint's shape).

### 4.2 Queue mechanism: reuse the existing transactional outbox

`pipeline.outbox_event`/`pipeline.outbox_consumption` (migration 012)
**already implements** exactly the durable, at-least-once, per-consumer
queue this requirement asks for — `publish_release` already writes a
`MICRO_COURSE_PUBLISHED` event through it. Proposed reuse, not a new
mechanism:

1. On every `ACTIVITY_RESPONSE`/`interaction_event` insert, also insert a
   `pipeline.outbox_event` row (`event_type='LEARNER_SIGNAL'`,
   `aggregate_type='ENROLLMENT'`, `aggregate_id=enrollment_id`, `payload`
   containing enough to re-derive the misconception/evidence update without
   re-querying — denormalized on write, standard outbox practice).
2. A new background consumer (same shape as any future outbox consumer —
   none exist yet as a running service today; `pipeline.outbox_consumption`
   is schema-only) reads unconsumed `LEARNER_SIGNAL` events, evaluates them
   against `pedagogy.misconception_evidence_rule` (the evaluators already
   exist in `interaction_runtime.py`, e.g.
   `evaluate_transition_matrix_row` — this consumer *calls* existing
   evaluation functions, it does not reimplement them), accumulates
   per-student misconception confidence, and marks the outbox row consumed.
3. The consumer updates learner-specific evidence/latest-state rows and analytics
   rollups in PostgreSQL. It **does not** project confirmed learner misconceptions or
   mastery into Neo4j. `interaction_template_projection.py` remains structural
   authoring metadata only (`InteractionInstance-[:CAN_REVEAL]->Misconception`,
   evidence-rule metadata, scenes/templates, etc.). Only published authoring changes
   may trigger that structural projector.

### 4.3 Real-time vs. batch — recommendation

Two options exist in this codebase already; neither needs to be invented:

- **Batch (recommended default):** a scheduled job (e.g. every 1–5 minutes)
  drains the outbox. Simple, matches the existing outbox's design intent,
  and misconception confidence does not need sub-second latency to be
  useful.
- **Real-time (optional, for live-classroom contexts only):** `mathbank-live`
  (doc 28, already implemented with reconnect/replay semantics) can relay a
  `LEARNER_SIGNAL` to an instructor's live dashboard the moment it's
  recorded, **in addition to** the batch path feeding Neo4j — real-time is
  for a human watching live, not for the graph update's own latency
  requirement, which batch satisfies fine.

## 5. Auditability and traceability

No general-purpose audit-log table exists today (`micro_course_review` is
the closest precedent — an append-only decision log for release reviews,
but scoped only to publication, not every admin/AI action). Proposed:

- **New table**: `audit.action_log` (`actor_type` `STUDENT`\|`ADMIN`\|`AI`\|
  `SYSTEM`, `actor_id`, `action` (e.g. `COURSE_METADATA_EDITED`,
  `AI_DRAFT_ACCEPTED`, `COURSE_DEACTIVATED`), `entity_type`, `entity_id`,
  `before_state jsonb`, `after_state jsonb`, `request_id` (correlation id,
  see below), `created_at`). Append-only (same immutability-trigger pattern
  as every other append-only ledger in this schema, e.g.
  `learner.micro_course_state_event`).
- **Correlation id**: every REST request already can carry (or gains) an
  `X-Request-Id` header, propagated into every audit row and every outbox
  event's payload, so a single student action (e.g. "answered quiz Q") can
  be traced end-to-end: REST request → `micro_course_state_event` row →
  `outbox_event` row → Neo4j projection write → (if AI was involved) the
  `ai_usage_event` row from §14. This is the traceability mechanism the
  requirement asks for — one id threading every table a single action
  touches, queryable without joining on timestamps/guesswork.
- Directly closes doc 43 AMC-10/AMC-12's open "authoring-provenance
  logging" gap — `audit.action_log` with `actor_type='AI'` *is* that log.

## 6. Data retention and purge ("keep only latest state")

The schema already distinguishes **latest-state** tables from
**append-only history** tables; the purge policy should respect that
distinction rather than purge indiscriminately:

| Kind | Example | Purge policy |
|---|---|---|
| Latest-state (overwritten in place) | `tutor.micro_course_runtime` (one row per enrollment, `current_state_id` updated in place) | Never purged while the enrollment is `IN_PROGRESS`; deleted only when the parent enrollment itself is deleted (cascade), which this plan does not propose doing to a student's own history. |
| Append-only raw event log | `learner.micro_course_state_event`, `learner.interaction_event`, `audit.action_log`, `pipeline.outbox_event` | Rolled up (§9) into summary tables, then **purged past a retention window** (e.g. 180 days of raw events once rolled up) — using the existing `allow_purge` session-setting escape hatch pattern (`SET LOCAL pedagogy.allow_purge = 'on'` already used by migrations 032-034's immutability guards) so a purge job can delete rows a normal transaction is blocked from touching, without weakening the guard for every other caller. |
| Outbox | `pipeline.outbox_event` + `pipeline.outbox_consumption` | Standard outbox hygiene: delete an event once every known consumer has a `pipeline.outbox_consumption` row for it **and** it is older than a short safety window (e.g. 7 days) — this is a well-understood, bounded-growth pattern, not new design risk. |
| Derived/rollup | New analytics rollup tables (§9) | Never purged (they are the retained "latest state" for analytics); only re-aggregated. |

This gives a concrete answer to "purge old data with only latest state
kept": the *raw* event tables are what get purged (after rollup), the
*state-pointer* and *rollup* tables are what's kept.

## 7. REST integration pattern (web + mobile) and the new-endpoint inventory

### 7.1 Client-side data-fetching pattern (formalizing what's informal today)

The current student reader uses ad hoc `useEffect`+`fetch`. For a "seamless"
integration bar across web and the new mobile client, standardize on:

- A typed API client generated/hand-written once from doc 42's JSON shapes
  (shared package, §2.2), used by both web and mobile — not two independent
  hand-rolled fetch call sites drifting apart.
- `react-query` (already a reasonable fit given the existing fetch/retry
  patterns) for caching, retry-with-backoff, and the offline cache in §2.4,
  replacing today's manual `useState`/`useEffect` fetch-and-store dance in
  `page.jsx` — a refactor of existing code, not new backend surface.
- Every mutating call (`advance`, `activity-responses`, `interaction-events`,
  feedback in §13) carries the `X-Request-Id` from §5 and, where relevant,
  the `client_event_id` idempotency key from §2.4.

### 7.2 Consolidated new-endpoint inventory

| Endpoint | Method | Purpose | New table(s) |
|---|---|---|---|
| `/v1/micro-courses/enrollments/{id}/interaction-events` | POST | Silent/implicit interaction telemetry (§4.1) | writes `learner.interaction_event` (existing schema) + `pipeline.outbox_event` |
| `/v1/learner/push-devices` | POST/DELETE | Register/remove a mobile push token (§2.5) | `learner.push_device` (new) |
| `/v1/learner/micro-courses/progress` | GET | "My micro-courses" dashboard across all enrollments (§8) | reads existing `learner.micro_course_enrollment` + `tutor.micro_course_runtime`; no new table |
| `/v1/micro-courses/{code}/export` | GET | Export a completed course's transcript/certificate (§9) | reads existing tables; renders PDF/JSON on the fly, no new table required unless certificates are persisted (optional, see §9) |
| `/v1/micro-courses/{code}/cheat-sheet` | POST (explicit consent) | Generate an AI cheat-sheet for a course (§12) | new `pedagogy.micro_course_cheat_sheet` (cached generated artifact + source hash, so it's regenerated only when content changes) |
| `/v1/micro-courses/enrollments/{id}/ask` | POST | Scoped AI tutor question inside a course step (§13) | logs to `ai_usage_event` (§14); answer not persisted beyond the chat transcript pattern already used elsewhere (`agent_transcripts.py`) |
| `/v1/micro-courses/enrollments/{id}/feedback` | POST | "Report an issue" / feedback widget (§15) | new `learner.micro_course_feedback` |
| `/v1/admin/micro-courses/{code}/activity` | GET | Backs doc 43's Activity tab | reads rollup tables (§9); admin-key gated |

## 8. Progress across all enrolled courses ("My micro-courses")

A new student-facing page (web: `/learn/courses/progress` or a tab on
`/profile`; mobile: a primary tab, not buried) listing every course the
student has ever enrolled in, each row showing: title, status pill
(`IN_PROGRESS`/`COMPLETED`), `step_number`/`step_count` (doc 42 §3.2's
existing fields), last-activity date, and a "Continue" deep link straight
into the live stepper step. Backed entirely by the new
`GET /v1/learner/micro-courses/progress` endpoint (§7.2) — a simple
aggregate query over existing `learner.micro_course_enrollment` rows for
the authenticated student; **no new table**.

## 9. Export and auto-generated cheat sheets

### 9.1 Export

- **Transcript/certificate (PDF)**: on `COMPLETED` status, a student can
  export a one-page PDF (course title, objectives, completion date,
  per-step summary) — rendered server-side (reuse whatever PDF pipeline
  already exists for other document generation in this codebase, or a
  lightweight library if none does) from data already in
  `learner.micro_course_enrollment`/`pedagogy.micro_course_release`; no new
  table needed unless the product wants certificates to be independently
  verifiable later (a `learner.micro_course_certificate` table with a
  signed/hashed id would be the addition if so — flagged as optional, not
  committed).
- **Raw data export (JSON)**: a student's own enrollment/event/feedback
  rows, for transparency/portability — a straightforward read-only query
  across existing tables, gated to the authenticated student's own
  `student_id` only.

### 9.2 Auto cheat sheet

An AI-assisted, one-page summary (key objectives, the formulas/relationships
shown in each state's interactions, the quiz takeaways) generated **from the
course's own content only** (objective/instruction/interaction
`learning_objective`/activity `explanation` fields already in doc 42's JSON
shapes) — explicitly *not* free-form AI knowledge, so it cannot hallucinate
content the course didn't actually teach. Cached in the new
`pedagogy.micro_course_cheat_sheet` table keyed by
`(release_id, content_hash)` so it is regenerated only when the release's
content actually changes (the release's own `content_hash`, already computed
by `_content_hash()` at publish time, is the natural cache key). Requires
the same explicit-consent-per-generation pattern as every other paid-AI
feature in this codebase (doc 35's CRA-6 pattern).

## 10. AI tutor connection inside a micro-course

A scoped "Ask about this step" affordance reusing the **existing** tutor/
agent infrastructure (`mathbank-rest/src/mathbank_rest/tutor.py`,
`pedagogy.py`, `step_tutor.py`), not a new chat system:

- The question is answered with retrieval **scoped to the current course
  state's content** (its objective, instruction, bound interaction
  `learning_objective`, bound concepts/techniques) — requiring a new
  pgvector representation kind in the existing `search.representation`
  table (`source_entity_type='MICRO_COURSE_STATE'`), embedded at publish
  time (alongside the existing `'PROBLEM'`/`'SOLUTION'` kinds, same table,
  same `search.embedding_model` infra — no new vector store).
- Answers must cite which step/state they're grounded in (consistent with
  this document's trust bar, §3, and the existing source-gated tutor
  behavior elsewhere in the codebase — e.g. the solution-guidance tests'
  "source and statement gated" pattern already enforced for problem
  tutoring).
- Logged via `ai_usage_event` (§14) for cost tracking and via
  `audit.action_log` (§5) with `actor_type='AI'` for traceability.

## 11. Error reporting / feedback

A lightweight, always-available "Report an issue" affordance on every step
(icon button, matching the existing `IconButton` convention) opening a small
form: category (`CONTENT_ERROR`/`VIDEO_BROKEN`/`QUIZ_WRONG`/`OTHER`),
free-text, optional screenshot — posts to
`POST /v1/micro-courses/enrollments/{id}/feedback` (§7.2), persisted in a new
`learner.micro_course_feedback` table (`enrollment_id`, `state_id`,
`category`, `message`, `status` `OPEN`\|`ACKNOWLEDGED`\|`RESOLVED`,
`created_at`). Surfaces in doc 43's admin Activity tab as a feed, closing
the loop between "student reports a problem" and "admin sees it without
hunting through support channels."

## 12. Measuring AI token usage per student

No AI cost/usage tracking exists anywhere in this codebase today (verified:
no `prompt_tokens`/`completion_tokens`/cost columns in any migration). New,
explicit instrumentation:

- **New table**: `ai_usage_event` (`event_id`, `student_id` (nullable — some
  AI calls are admin-initiated, e.g. doc 43's drafting assistant),
  `admin_actor` (nullable, mutually exclusive with `student_id`), `feature`
  (`MICRO_COURSE_TUTOR_QA`\|`CHEAT_SHEET_GENERATION`\|
  `ADMIN_CONTENT_DRAFTING`\|`VIDEO_TRANSCRIPTION`\|...), `provider`,
  `model_name`, `prompt_tokens`, `completion_tokens`, `total_tokens`,
  `estimated_cost_usd`, `request_id` (ties to §5's correlation id),
  `created_at`).
- Every LLM call site (`route_openai.py`, `route_ollama.py`, and any new
  call introduced by §10/§12's features) wraps its provider response and
  writes exactly one `ai_usage_event` row — centralizing this in one small
  helper function (e.g. `record_ai_usage(...)`) called from every site,
  rather than ad hoc logging per feature, is what makes "measure tokens
  per student" actually answerable with one `GROUP BY student_id` query
  instead of reconstructing it from scattered logs.
- A per-student (and per-course, via joining `ai_usage_event.request_id` →
  audit trail → `enrollment_id`) usage summary becomes a straightforward
  read, and a **budget/quota check** (e.g. "stop allowing AI tutor calls
  for this student today past N tokens") becomes a simple guard in front of
  the same call sites — explicitly flagged as a product decision to make
  later, not committed to a specific limit here.

## 13. Student activity logging (consolidated view)

Rather than one monolithic "activity log" table, this plan's position is
that activity is already naturally split by concern (§4's event tables,
§5's audit log, §12's AI usage) and a **consolidated view** is a read-side
concern, not a write-side one:

- A `student_activity_timeline` read model (a view or a small rollup table,
  decision deferred to implementation) that `UNION ALL`s: enrollment
  lifecycle events (`ENROLLED`/`STATE_CHANGED`/`COMPLETED`), quiz/
  interaction events, feedback submissions, and AI usage — ordered by time,
  filterable per student — is what both a future "my activity" student page
  and the admin Activity tab (doc 43 §3.2.7) read from, instead of each
  screen hand-rolling its own multi-table join.

## 14. Incentivizing course completion

No gamification/notification precedent exists today; proposed, explicitly
scoped to avoid manipulative dark-pattern territory:

- **Progress nudges, not guilt:** a push/email reminder (via §2.5's device
  registry, or email if no push token) sent once after N days of
  inactivity on an `IN_PROGRESS` enrollment, capped at a small number of
  reminders per course (not an unbounded drip) — framed as "pick up where
  you left off" with the exact next step's title (reusing
  `current_state.title` from doc 42 §3.2), not generic.
- **Completion acknowledgment:** the export/certificate in §9.1 itself is
  the primary incentive artifact — something tangible to show for
  finishing, not a points system layered on top for its own sake.
- **Streak/badge mechanics are explicitly deferred**, not recommended as a
  v1 requirement: they need their own product-design pass (what counts as
  a "streak" across multiple courses, anti-gaming considerations) that is
  out of scope for a data/platform design document.

## 15. Persistence map (recap, one table)

| Capability | Postgres | Neo4j | pgvector (`search.*`) | Queue |
|---|---|---|---|---|
| Stepper content/enrollment (doc 42) | `pedagogy.micro_course*`, `learner.micro_course_enrollment`, `tutor.micro_course_runtime` | `projection_kind='micro_course'` (doc 40) | — | — |
| Silent interaction telemetry | `learner.interaction_event` + learner evidence/latest-state + analytics rollups | **No learner-specific graph projection.** `projection_kind='interaction_template'` stays structural authoring metadata | — | `pipeline.outbox_event` (§4.2) |
| Audit/traceability | new `audit.action_log` | — | — | — |
| AI token usage | new `ai_usage_event` | — | — | — |
| Scoped course AI tutor | — (chat transcript reuses existing agent-transcript pattern) | — | new `search.representation` kind `'MICRO_COURSE_STATE'` | — |
| Cheat sheet | new `pedagogy.micro_course_cheat_sheet` | — | reuses the same course-state embeddings for grounding | — |
| Feedback | new `learner.micro_course_feedback` | — | — | — |
| Push devices | new `learner.push_device` | — | — | — |
| Export/certificate | existing tables (+ optional `learner.micro_course_certificate`) | — | — | — |

## 16. Requirement inventory (MCX-*)

| ID | Requirement | Acceptance |
|---|---|---|
| MCX-1 | Tablet-tier responsive layout | A dedicated 768–991px tier exists distinct from phone and desktop/landscape-tablet, per §1's table, verified at 820×1180 (iPad portrait) with no overflow. |
| MCX-2 | Shared, framework-free business-logic package | Interaction geometry math and label vocabularies are extracted into one package consumed by both `mathbank-web` and `mathbank-mobile`, so web and mobile cannot silently drift on what a template/state-type label means. |
| MCX-3 | Mobile auth reuses the existing JWT | No new auth mechanism is introduced for mobile; the same `/v1/learner/login` JWT is stored in platform secure storage and sent as `Authorization: Bearer`. |
| MCX-4 | Offline read-cache | A student can reopen a previously-viewed course/enrollment with no network and see the last-synced content. |
| MCX-5 | Offline-queued, idempotent quiz attempts | A quiz answer submitted offline is queued with a client-generated idempotency key and replayed on reconnect without double-counting in analytics rollups. |
| MCX-6 | Push registration | A logged-in student can register/remove a device push token; tokens are never shared across students. |
| MCX-7 | Silent interaction telemetry wired end-to-end | Meaningful (debounced) interaction manipulations are recorded in `learner.interaction_event`, evaluated into private learner evidence/latest-state, and queued via the existing outbox for reconciliation/analytics. They are **not** written as learner-specific Neo4j facts. |
| MCX-8 | Correlated audit trail | Every student/admin/AI action that changes persisted state writes one `audit.action_log` row, carrying a request id that also appears on any related outbox/AI-usage rows for that same action. |
| MCX-9 | Rollup-then-purge retention | Raw event tables are only purged after being rolled up into a retained summary, using the existing `allow_purge` escape-hatch pattern; latest-state pointer tables are never purged while their parent enrollment is active. |
| MCX-10 | Typed, shared API client with retry/offline cache | Web and mobile share one API client implementation (not independently hand-rolled fetch calls) built on top of doc 42's JSON contract. |
| MCX-11 | Cross-course progress view | A student can see every course they've ever enrolled in, with status and a one-tap resume, from one screen/endpoint. |
| MCX-12 | Export | A completed course can be exported as a PDF summary and as a raw JSON data export, scoped strictly to the requesting student's own data. |
| MCX-13 | Content-grounded cheat sheet | A generated cheat sheet is built only from the course's own authored content (never free-form AI knowledge), cached by release content-hash, and requires explicit per-generation consent. |
| MCX-14 | Scoped, cited AI tutor | An in-course AI question is answered using retrieval scoped to the current step's content, cites which step grounded the answer, and is never answered from unscoped general knowledge. |
| MCX-15 | Feedback loop closes to admin | A student-submitted feedback report is visible in the admin Activity tab (doc 43) without any manual log-digging. |
| MCX-16 | Per-student AI cost visibility | Every AI call, across every feature, writes exactly one usage-event row sufficient to answer "how many tokens/how much cost did this student generate," without reconstructing it from scattered per-feature logs. |
| MCX-17 | Non-manipulative completion nudges | Inactivity reminders are capped in frequency, reference the student's actual next step, and are not a points/streak system layered on without its own product-design pass. |

## 17. Explicit non-goals of this document

- No Neo4j schema changes are proposed — this plan only populates
  projections doc 40/41 already define.
- No new vector store/technology — this plan only adds a
  `search_entity_type` value to the existing pgvector table.
- No commitment to a specific push-notification/PDF-generation/analytics-
  rollup *library* — those are implementation choices made when this plan
  is picked up, not design constraints fixed here.
- No gamification mechanics beyond capped reminders (§14) are specified;
  streaks/badges are explicitly deferred to a future product-design pass.

## Cross-document implementation sequence

All six documents must be implemented as one dependency-ordered program:

```text
Phase 0  Inventory current DB migrations, services, projectors, routes, UI and tests.
Phase 1  Resolve canonical schema/contract gaps and secure student payload v2.
Phase 2  Complete interaction catalogs + deterministic runtime + evidence engine.
Phase 3  Complete SceneSpec Web/Manim/mobile renderers and accessibility behavior.
Phase 4  Complete micro-course media/transcript/Q&A/intervention authoring.
Phase 5  Add micro-course ↔ tutoring-route bindings and nested route runtime.
Phase 6  Complete student web/tablet/phone layouts and shared API client.
Phase 7  Complete admin catalog/workspace/media/widgets/routes/publish/graph screens.
Phase 8  Complete structural Neo4j projectors + verify/diff for all projection kinds.
Phase 9  Complete search/embedding publication for approved course/route content.
Phase 10 Wire audit, AI usage, outbox consumers, analytics rollups and retention.
Phase 11 Build mobile client/offline replay/push features.
Phase 12 Run comprehensive cross-system golden fixtures and security/privacy checks.
```

### Global hard prohibitions

Never:
- create a parallel Concept/Technique/Skill taxonomy;
- mutate published content in place;
- expose hidden answers/evaluation policy in learner JSON;
- treat one wrong answer as a confirmed misconception;
- project learner-specific misconception/mastery data into shared Neo4j;
- run destructive shared-graph rebuilds;
- let runtime LLMs invent course states/routes/interactions/remediations;
- duplicate service logic separately in UI/CLI/mobile;
- claim graph/search parity from a queued job;
- use a separate fake preview renderer;
- lose exact return state/time when launching a subflow.
