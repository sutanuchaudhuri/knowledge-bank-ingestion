# 22 — Agent Session Transcripts (student ↔ session link and conversation rebuild)

Status: **implemented** (migration `016`, REST `agent-sessions` router, web conversations pages).
Related: [18 tracker](./18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md) ·
[19 gotchas](./19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md) ·
[reference/POSTGRES_SCHEMA](./reference/POSTGRES_SCHEMA.md) ·
[reference/REST_API](./reference/REST_API.md).

## 1. Requirement

| ID | Requirement |
|---|---|
| TRN-1 | Every agent conversation started by a signed-in student MUST be durably linked `student_id → agent session id` in a project-owned table. |
| TRN-2 | A student MUST be able to list their own conversations and re-read any of them in full (their messages + tutor replies), newest first. |
| TRN-3 | An admin MUST be able to list conversations across students (filter by e-mail substring or student UUID) and read the full transcript, including model thinking, tool calls and (truncated) tool results. |
| TRN-4 | The rebuild MUST be derived from the persisted agent session store (`agent_sessions.sessions/events`) — never from browser state. |
| TRN-5 | Identity MUST be server-derived: the ADK `user_id` is the student UUID from the httpOnly JWT cookie, else `anonymous`. Client-supplied user ids are ignored. |
| TRN-6 | A student can never claim a session created under another identity; a session id already linked to a different student returns **409**. Foreign/unlinked transcripts return **404** to students. |
| TRN-7 | Anonymous (signed-out) conversations are stored by ADK but remain **unlinked**; the admin list reports only their count. |
| TRN-8 | Deleting a learner cascades to their links (the ADK rows themselves are framework-owned and not deleted by the project). |
| TRN-9 | All timestamps returned are ISO-8601 **with UTC offset** (ADK stores naive UTC). |

## 2. Data model

`learner.agent_session_link` (migration [`016_agent_session_link.sql`](../mathbank-db/sql/016_agent_session_link.sql)):

| Column | Notes |
|---|---|
| `agent_session_link_id` uuid PK | `gen_random_uuid()` |
| `agent_app_name`, `agent_user_id`, `agent_session_id` | logical reference to `agent_sessions.sessions(app_name, user_id, id)` — **no FK** (framework-owned schema) |
| `student_id` uuid | FK → `learner.student_profile` `ON DELETE CASCADE` |
| `surface` | `HOME_CHAT` \| `SOLVE_WORKSPACE` \| `OTHER` |
| `context` jsonb | e.g. `problem_code`, `solve_attempt_id`; merged (`||`) on re-link |
| `created_at`, `last_seen_at` | timestamptz |

Unique `(agent_app_name, agent_session_id)`; index `(student_id, created_at DESC)`.

## 3. Flow

1. Browser → `POST /api/agent/session` (Next.js). The server resolves identity from the cookie,
   creates the ADK session at `mathbank-agent` (`409` from ADK = already exists, treated as idempotent).
2. If signed in, the web server calls `POST /v1/learner/agent-sessions` with the student JWT.
   REST verifies the ADK row exists with `user_id = student_id`, then upserts the link
   (`ON CONFLICT … DO UPDATE … WHERE student_id = EXCLUDED.student_id`; no row returned → 409).
3. Rebuild: `agent_transcripts.build_transcript()` reads non-partial events in timestamp order and emits
   `user` / `assistant` messages; with `include_tools` it adds `thinking`, `tool_call`, `tool_result`
   (payloads truncated to 2,000 chars).

## 4. Interfaces

| Surface | Path | Auth |
|---|---|---|
| REST | `POST /v1/learner/agent-sessions` | student JWT |
| REST | `GET /v1/learner/agent-sessions?limit=` | student JWT |
| REST | `GET /v1/learner/agent-sessions/{id}/transcript` | student JWT (own only) |
| REST | `GET /v1/admin/agent-sessions?student=&limit=` → `{linked[], unlinked_count}` | `X-Admin-Api-Key` |
| REST | `GET /v1/admin/agent-sessions/{id}/transcript` | `X-Admin-Api-Key` |
| Web proxy | `/api/rest/learner/conversations[/…]`, `/api/rest/admin/conversations` | cookie |
| Web pages | `/learn/conversations` (student), `/admin/conversations` (admin) | cookie |

## 5. Verification

- Unit: `mathbank-rest/tests/test_agent_transcripts.py` (shape, truncation, naive-UTC timestamps).
- E2E: `mathbank-web/e2e/student.spec.mjs` (ownership 403/404, conversations page),
  `admin.spec.mjs` (`{linked, unlinked_count}`), `tutor-llm.spec.mjs` (new chat appears in the list).
- Manual walkthrough 2026-05 (Pia, Power of a Point): both chats listed and rebuilt; admin view shows tool calls.

## 6. Not yet implemented

- Solve-workspace chat surface (`SOLVE_WORKSPACE`) is reserved; the solve page does not yet open an agent chat.
- No transcript export (PDF/Markdown) or retention policy; no redaction pass beyond tool-payload truncation.
- Anonymous sessions cannot be claimed after sign-in (by design, TRN-6).
