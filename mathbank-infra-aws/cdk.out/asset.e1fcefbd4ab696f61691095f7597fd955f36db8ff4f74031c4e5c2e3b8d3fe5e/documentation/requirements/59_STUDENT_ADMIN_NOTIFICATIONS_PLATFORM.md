# 59. Student and admin notifications platform (non-ML)

> **Status: scaffolded, not implemented, not tested.** This document is **deliberately not
> part of the `intellitutor-ml-rl` design pack** — it covers telling a student their
> submission/quiz/exam was graded, their mastery moved, or an admin needs to look at
> something, which is an event-driven side effect of existing write paths, not a model.
> See [54](54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md) §2 for why this lives inside
> `mathbank-rest` rather than as a `mathbank-ml-*` project.

## 1. Why this exists

Every grading/mastery-update path in the app today (`quiz_runtime.submit_response`,
`micro_course_service.submit_learning_item_response`/`submit_activity_response`, and the
plain problem-attempt grading path) computes a result and returns it **synchronously to the
caller that asked**, but nothing tells the student *later* (if they've navigated away) or
tells an admin that a pattern worth reviewing just happened. This document adds that layer
without touching how grading itself works.

## 2. Scope boundaries

- **In scope**: recording a notification record when a gradable event happens; delivering it
  to (a) an in-app notification list, (b) optionally an existing real-time channel
  (`mathbank-live`'s Socket.IO server, §5), (c) email, as a later, explicitly optional
  channel.
- **Out of scope**: changing any grading logic, any ML prediction, any model. Every trigger
  in §4 is wired to an *existing* function's return value, not a new computation.

## 3. Schema (`mathbank-db/sql/043_notifications.sql`, scaffolded, not applied)

```sql
-- requirements/59. New schema, additive, no changes to existing tables.
CREATE SCHEMA IF NOT EXISTS notification;

CREATE TABLE notification.event (
    notification_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_type        text NOT NULL,         -- STUDENT | ADMIN
    recipient_id          text NOT NULL,         -- student_id or admin identifier
    notification_type     text NOT NULL,         -- see §4 enum
    severity              text NOT NULL DEFAULT 'INFO',  -- INFO | SUCCESS | WARNING | ACTION_NEEDED
    title                 text NOT NULL,
    body                  text,
    -- TODO: decide whether `payload` should reference the source row (quiz response id,
    -- activity response id, data-readiness issue id) by a typed FK per notification_type,
    -- or stay a loosely-typed jsonb pointer like this. Loosely typed for now so this
    -- migration does not need to know about every possible source table up front.
    payload_json          jsonb NOT NULL DEFAULT '{}'::jsonb,
    read_at               timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_notification_event_recipient
    ON notification.event (recipient_type, recipient_id, created_at DESC);

CREATE INDEX idx_notification_event_unread
    ON notification.event (recipient_type, recipient_id)
    WHERE read_at IS NULL;

-- TODO: a `notification.preference` table (per-student channel opt-in/opt-out) is deferred
-- until at least one real delivery channel beyond in-app exists (§5) — do not build
-- preference management for a channel that doesn't exist yet.
```

## 4. Trigger catalog (each one maps to an existing, already-implemented function)

| Trigger | Existing source function | `notification_type` | Status |
|---|---|---|---|
| Quiz response graded | `quiz_runtime.submit_response` | `QUIZ_GRADED` | 🟡 call site identified, no call added yet (`# TODO` left at the exact return statement) |
| Micro-course learning-item graded | `micro_course_service.submit_learning_item_response` | `MICRO_COURSE_ITEM_GRADED` | 🟡 same |
| Micro-course activity graded | `micro_course_service.submit_activity_response` | `MICRO_COURSE_ACTIVITY_GRADED` | 🟡 same |
| Mastery crossed a threshold (e.g. concept moved WEAK→DEVELOPING per doc 03 §2's bands) | Depends on doc 58's cohort/mastery service existing first | `MASTERY_MILESTONE` | ⬜ blocked on doc 58, not this pass |
| Data-readiness flagged something admin-actionable | `services.data_readiness` (doc 58) | `ADMIN_DATA_GAP` | ⬜ blocked on doc 58 |
| New course release ready for admin review | Existing `review_release`/`publish_release` in `micro_course_service.py` | `ADMIN_REVIEW_NEEDED` | 🟡 call site identified |

**No trigger is wired in this pass.** `notifications.py::record_quiz_graded()` (and
siblings, one per row above) are fully-typed, fully-documented function stubs that the
*existing* grading functions would call — none of those existing functions have actually
been edited to call them yet, to keep this pass additive/non-invasive per the "scaffolded,
not implemented" instruction. Each stub's docstring names the exact line in the existing
file where the call would go.

## 5. Delivery channels

1. **In-app list** (always on): `GET /v1/notifications/me`, `POST
   /v1/notifications/{id}/read` — scaffolded REST router, backed by `notification.event`.
2. **Real-time push** (optional, reuses existing infra): `mathbank-live`'s Socket.IO server
   already exposes `emitTo(rooms, event, data)` (confirmed by reading
   `mathbank-live/server.mjs`) — `notifications.py::_publish_realtime()` is stubbed to HTTP-
   POST to a small new `mathbank-live` endpoint that calls `emitTo([f"student:{id}"],
   "notification", payload)`, reusing the existing room-based routing rather than inventing
   a second real-time server. **Not implemented** — the new `mathbank-live` endpoint itself
   is also just a `# TODO` stub, not built in this pass.
3. **Email** (explicitly deferred): `# TODO: do not build until an email-sending
   dependency/provider decision is made; do not default to a specific provider without
   asking`.

## 6. Pydantic entities (`mathbank_rest/notifications.py`, scaffolded)

`NotificationEvent`, `NotificationCreate`, `NotificationListResponse` — field-for-field
match to §3's schema. `NotificationType` is a `Literal` enum over exactly the
`notification_type` values in §4's table (not free text — matching this session's own
doc 45 finding about enumerating free-text fields).

## 7. Requirement inventory (NOTIF-*)

| ID | Requirement | Acceptance evidence | Status |
|---|---|---|---|
| NOTIF-1 | Schema is additive, no existing table touched | `043_notifications.sql` only adds a new schema | ✅ |
| NOTIF-2 | `notification_type` is enumerated | `contracts`/pydantic `Literal` | ✅ |
| NOTIF-3 | Every trigger maps to an already-implemented existing function, not a new computation | §4 table | ✅ |
| NOTIF-4 | Real-time delivery reuses `mathbank-live`'s existing Socket.IO server, not a new one | `notifications.py::_publish_realtime()` docstring | ✅ (plan only, not wired) |
| NOTIF-5 | No existing grading function has actually been edited to call a notification trigger yet | `git diff` on `quiz_runtime.py`/`micro_course_service.py` shows no changes | ✅ (intentional, this pass is additive-only) |
| NOTIF-6 | Migration is new-file-only, not applied to any live database | No `migrate_notifications.py --apply` was run | ✅ |

## Cross-document relationship

Independent of the `mathbank-ml-*` projects (doc 54 §2 explains why). Reuses
`mathbank-live`'s existing Socket.IO server (unmodified in this pass). Depends on doc 58's
services existing before the `MASTERY_MILESTONE`/`ADMIN_DATA_GAP` triggers can be wired.
