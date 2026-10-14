# 64. AWS Bedrock mock-exam agent — natural-language paper generation, timed exam sessions, and post-exam diagnosis

## 0. Status and scope

| | |
|---|---|
| Status | **EXM-1 through EXM-18 are deployed/live-verified as recorded below. EXM-19 is implemented in the current worktree only**: migration 051 has not been applied, running services have not been refreshed, and cross-device resume has not been live-verified. Existing deployed flow: signup/login via real AWS Cognito → natural-language request → intake parsing → generator↔critic loop (real critic-caught math errors, real bounded revision) → persisted paper → one-question-at-a-time timed exam with interaction timeline → explicit submit → auto-grading → per-option explanations → diagnosis → print/export. **Deviations from the original design, confirmed live and necessary**: (1) Bedrock model invocation is blocked account-wide on this AWS account (`ValidationException: Error 002: Access to Bedrock models is not allowed for this account`, reproduced with two different models) — the Strands Agents SDK itself is unchanged, only the model provider is OpenAI for now (`llm_models.py`, a one-line swap back once access is resolved); (2) local dev needs an AWS SSO session for real Cognito admin calls; (3) the frontend deploys to S3+CloudFront, not Amplify Hosting. |
| Trigger | User request: a new, independent agent that creates a mock-exam question paper from a natural-language request ("how many questions, what kind of paper"), built on an **AWS-native agentic framework with an AWS-provisioned model** (explicitly **not** Google ADK), reusing the **existing MCP server** as a tool source and the **existing quiz generation/grading service** as a data layer, but as a **separate project with its own independent UI** — not a feature bolted onto `mathbank-agent`/`mathbank-web`. Exam answers stay hidden until after submission; a **critic agent** reviews/revises generated questions; a post-exam **diagnosis** step reports time spent, reasoning guidance, and ranked improvement areas; the paper must be **exportable**; deployment is Lambda, "pay-as-you-go least cost," reusing this repo's own proven AWS deployment patterns (requirements/62, requirements/63). |
| Grounding | Every architectural claim below is checked against this repo's actual code, not assumed: `quiz.*` schema (migration 042) and `quiz_runtime.py`'s real function signatures (§2), the real MCP tool list already exposed by `mathbank-mcp-competitions/server.py` (§3), `mastery.py`'s real difficulty/mastery functions (§5), and the AWS Strands Agents SDK's real, current Bedrock + MCP integration shape (§1, confirmed via web research this session **and then by direct, live code inspection** — `strands.models.openai.OpenAIModel`/`strands.models.bedrock.BedrockModel`, `strands.tools.mcp.mcp_client.MCPClient(url=...)`, and `agent(prompt, structured_output_model=YourPydanticModel)` as the current, non-deprecated structured-output API — deployable directly on Lambda with no additional managed runtime required). `AWS_BEARER_TOKEN_BEDROCK` already exists in the repo-root `.env` (confirmed via `grep`) but Bedrock invocation itself is blocked account-wide (see Status row above). |
| Scope boundary | This is an **additive, parallel** project — it does not modify `mathbank-agent` (Google ADK), `mathbank-web`'s existing student quiz UI (requirements/53's `QZ-9`), or any currently-deployed Lambda stack. It reuses the `quiz.*` Postgres schema and grading/mastery-absorption code as a **shared data layer**, and the already-deployed `mathbank-mcp-competitions` Function URL as a **shared tool source** — both by calling them, never by copying or forking their logic. `mathbank-exam-agent` never connects to Postgres/Neo4j directly, confirmed in the real code (`rest_client.py` is its one database boundary). |

### Progress tracker

| ID | Item | Status |
|---|---|---|
| EXM-1 | New project `mathbank-exam-agent` — Strands Agents SDK, three agent roles (generator, critic, diagnoser) | ✅ IMPLEMENTED and live-verified — model backend is OpenAI for now, not Bedrock (see Status row) |
| EXM-2 | Migration `047_mock_exam_extensions.sql` — additive columns on `quiz.paper`/`quiz.question`, new `quiz.exam_diagnosis` table | ✅ IMPLEMENTED — applied live to Neon |
| EXM-3 | Natural-language intake → generation parameters (style, count, question types, topic/skill targets, difficulty, time limit) | ✅ IMPLEMENTED and live-verified (`intake.py`) |
| EXM-4 | Generator agent: drafts questions via MCP tools (corpus grounding) + direct REST calls (mastery/theorem/difficulty data) | ✅ IMPLEMENTED and live-verified (`generator_agent.py`, `exam_service.py`'s topic/difficulty resolution) |
| EXM-5 | Critic agent: reviews each drafted question (correctness, difficulty match, clarity, solvability and math-format validity); bounded revise-and-recheck loop | ✅ Existing critic live-verified; current worktree adds `math_format_ok` checks for delimiters/braces/KaTeX compatibility and rejects APPROVE when false. This addition has not been deployed/live-verified. |
| EXM-6 | Exam session lifecycle: timed session, per-question time tracking, no mid-exam feedback, answers revealed only after submission, resumable signed-in progress | ✅ Existing answer gate/event timeline/options explanations are live-verified. Migration 051 and owner-scoped draft/current-position persistence are source/worktree changes only; not applied/live-verified. |
| EXM-7 | Diagnosis agent: post-exam holistic report — time management, reasoning-strategy guidance, ranked improvement areas (tied to real mastery deltas) | ✅ IMPLEMENTED and live-verified (`diagnosis_agent.py`) |
| EXM-8 | Export: browser-native print/PDF view of the generated paper (and, separately, the post-exam report) | ✅ IMPLEMENTED — `mathbank-exam-web`'s `Review.jsx` page (`window.print()` + `@media print` CSS in `theme.css`), covering every question's full solution, every MCQ option's explanation, and the diagnosis report in one printable view |
| EXM-9 | Independent UI — `mathbank-exam-web`, a separate deployable frontend, not inside `mathbank-web` | ✅ Existing UI deployed/live-verified; current worktree uses a one-question navigator, KaTeX display panels and return-to-exam login routing. Durable drafts/resume are not active until migration 051 and service rollout. |
| EXM-10 | Lambda deployment — new `mathbank-infra-aws` stack(s), reusing the proven cold-start-SSM-secret pattern, Bedrock IAM/bearer-token wiring | ✅ IMPLEMENTED and live-verified — see §10's full rewrite for what was actually built (OpenAI, not Bedrock, so no bearer-token wiring; a Cognito IAM policy instead); backend at `https://rp4tfkonnswyn72i7dvvijao3i0amwxw.lambda-url.us-east-2.on.aws/`, frontend (S3+CloudFront, not Amplify — a plain static SPA, no Next.js) at `https://d1zj6erbhmlgyk.cloudfront.net`; `mathbank-rest` itself was also redeployed (it predated this feature's schema/routes entirely) |
| EXM-11 | Tests: NL-intake parsing, generator→critic loop, exam session gating, diagnosis synthesis, grading/mastery-absorption reuse | ✅ PARTIAL — 8 fast unit tests (schemas, deterministic topic-resolution logic) + 12 passing `mathbank-rest` tests (5 new, live against Neon, covering import/exam-mode-gate/submit/diagnosis); the full agent↔critic↔diagnosis live flow and the full browser UI flow were both run manually/live, not yet automated pytest/Playwright cases (each run costs real OpenAI tokens and 60-120+ seconds) |
| EXM-12 | AWS Cognito-backed onboarding (signup, login, forgot-password) — real User Pool, admin-API-only flows, anonymous-or-StudentId identity | ✅ IMPLEMENTED and live-verified — real Cognito User Pool `us-east-2_wQePckX1G`; `cognito_auth.py`/`jwt_verify.py`/`auth_dependency.py`; migration `049_cognito_student_identity.sql`; a real signup → generated-username flow → logout → login-with-generated-username round trip was verified in a live browser |
| EXM-13 | Parallel per-question generation (ThreadPoolExecutor), each question grounded in its own deterministic graph+RAG retrieval (`search_problems`), with a rotating candidate-pool window so different questions see different real sources | ✅ IMPLEMENTED and live-verified — a real 3-question run showed genuinely interleaved thread execution in the generation-event log (all 3 `DRAFT_QUESTION STARTED` before any `DONE`); confirmed via live Neo4j/Postgres hybrid search, not a mock |
| EXM-14 | Multiple, explicitly-noted inspiration sources per question ("inspired by, never copied" made concrete) — new `quiz.question_source` junction table, server-side validated against the real retrieved candidate pool (never trusting the model's own citation) | ✅ IMPLEMENTED and live-verified — real competition/year/source_url resolved and surfaced in the review page's "Inspired by" citation |
| EXM-15 | Whole-paper aggregate diversity/dedup critic pass (cross-question near-duplication, repeated MCQ option text), bounded fix-up regeneration loop | ✅ IMPLEMENTED and live-verified — a real run exercised 2 full aggregate passes with targeted question regeneration |
| EXM-16 | Computed complexity/difficulty signals (structured `solution_steps`, real step/concept/technique counts fed to the critic as evidence, not just re-read prose) — mirrors the real-corpus precedent (`pedagogy.problem_enrichment.solution_step_count`) | ✅ IMPLEMENTED and live-verified — `quiz.question.complexity_signals`/`quiz.solution.solution_steps`/`step_count`, shown as a pill in the review page |
| EXM-17 | Live, step-by-step generation-progress UI (durable `quiz.generation_event` log, polled by the frontend) instead of one static spinner message | ✅ IMPLEMENTED and live-verified — split `start`/`run`/`generation-progress` endpoints; a real run produced 90 ordered, correctly-interleaved events, rendered live on a new `GeneratingPaper.jsx` page |
| EXM-18 | Exam-taking UI redesign: one question at a time (not a stacked accordion), with a clickable status-dot navigator (attempted/skipped/seen-unattempted/not-seen, each with an icon + color + tooltip) | ✅ IMPLEMENTED — `TakeExam.jsx` rewritten; build passes and lint exits successfully with three warnings; logic manually traced and answer/skip/submit/review data contract live-verified via direct API calls; pixel-level visual confirmation pending |
| EXM-19 | Math-format critic review and clear LaTeX rendering; persist signed-in exam position and unsubmitted answers so a learner can resume after returning, including on another device | 🟡 IMPLEMENTED IN WORKTREE — critic verdict and KaTeX surface changed; migration `051_exam_resume_state.sql`, REST/agent proxy and exam UI persistence/restore added. Focused REST/agent tests and UI build passed. Migration and services have not been activated; no live or cross-device resume verification yet. |
| EXM-20 | asyncio generation pipeline and a growing, cached question pool (`quiz.question_pool`) consulted before any drafting | 🟡 IMPLEMENTED AND LOCAL-LIVE-VERIFIED — see §16. Migration `052_quiz_question_pool.sql` is applied to Neon; focused agent/REST tests and the web build pass. Local browser runs verified pool lookup, ordered async progress, TeX rendering and fail-closed quality rejection. AWS services are not redeployed. |

## 1. Why a new, separate AWS-native agent project (not Google ADK, not `mathbank-agent`)

`mathbank-agent` is built on Google's Agent Development Kit (ADK) and Google/LiteLLM model
routing (requirements/9, requirements/53 QZ-8's `quiz_generator_agent` lives there). The
user explicitly wants this new capability on an **AWS agentic framework with an
AWS-provisioned model** — a genuinely different stack, not a Google ADK sub-agent wearing
different clothes. Confirmed live (web research, this session) that the right AWS-native
choice is the **Strands Agents SDK** (`strands-agents`, open source, AWS-maintained):

- **Model-first, protocol-driven**: an `Agent(tools=[...], model=BedrockModel(...))` is
  the whole orchestration loop — no bespoke tool-calling plumbing to write, matching the
  existing project's bias toward reusing proven libraries over hand-rolled agent loops.
- **Native Bedrock support**: `strands.models.bedrock.BedrockModel(model_id=..., boto3_client=...)`
  — the `boto3_client` can be constructed from `AWS_BEARER_TOKEN_BEDROCK` (the Bedrock API
  key already present in this repo's root `.env`), so no new IAM role/credential class is
  needed, only env-var distribution (§9).
- **Native MCP tool support**: `strands.tools.mcp.mcp_client.MCPClient(url).list_tools_sync()`
  turns *any* MCP server's tools into Strands tools with zero custom adapter code — this is
  exactly the "must use the existing MCP" requirement, pointed at
  `mathbank-mcp-competitions`'s already-deployed Function URL
  (`https://xkvec5covshtvkf35ryg2haree0dijjm.lambda-url.us-east-2.on.aws/`, requirements/63
  §1), not a new or forked MCP server.
- **Deployable as a plain Lambda function, no extra managed runtime required**: confirmed
  live that Bedrock AgentCore (AWS's optional managed agent-runtime service) is **not**
  required — a Strands `Agent` can run inside an ordinary Lambda handler exactly like every
  other service this repo has already deployed (requirements/63), which is the cheapest
  option and keeps this project's deployment story consistent with every other service.

**Model choice (cost-driven, per the "least cost" instruction):** originally planned as
**Anthropic Claude 3.5 Haiku via Bedrock** for the generator and critic roles, with a
slightly stronger model for the one-call-per-exam diagnosis agent. **Confirmed live this
session that Bedrock invocation is blocked account-wide** (`ValidationException: Error
002: Access to Bedrock models is not allowed for this account`, reproduced with both
`anthropic.claude-haiku-4-5-20251001-v1:0` and `amazon.nova-2-lite-v1:0` — not a model-ID
or region issue, a genuine account-level restriction; `aws bedrock list-foundation-models`
succeeds, only actual invocation is rejected). Per the user's explicit instruction,
implementation proceeded with **`strands.models.openai.OpenAIModel`** (`gpt-4o-mini`) for
all three roles instead — confirmed live to work identically through the same `Agent`/
`structured_output_model=` interface. `llm_models.py` isolates this choice to three small
factory functions; swapping back to `BedrockModel` once account access is resolved touches
no other file.

## 2. Reuse boundary — what comes from requirements/53, what's new

Requirements/53 already built a real, tested, live-verified quiz subsystem. This project
reuses it as a **shared data layer and shared grading/mastery engine**, and adds a new
**generation/critique/diagnosis agent layer** on top — it does **not** fork or duplicate
the schema, and does **not** re-implement grading or mastery absorption.

| Reused as-is | New in this project |
|---|---|
| `quiz.paper`/`quiz.question`/`quiz.solution`/`quiz.response` schema (migration 042) | Additive columns only (§4) — no breaking change to requirements/53's existing rows or code |
| `quiz_runtime.submit_response()` (grading: exact-match for MCQ, LLM-graded for free-text/proof) | Unchanged — reused by REST call, not reimplemented. (The LLM-graded path still calls OpenAI internally today; swapping its model provider is explicitly **out of scope** here — see §13 open question 3.) |
| `quiz_runtime._absorb_mastery_feedback()` → `mastery.py`'s `recompute_concept_mastery`/`recompute_technique_mastery` | Unchanged — the diagnosis agent (§7) *reads* the resulting mastery deltas, it doesn't recompute them differently |
| `mastery.py`'s `normalized_difficulty`/`difficulty_weight`/`mastery_tier`/`build_improvement_plan` | Reused for difficulty calibration (§5) and as an input to the diagnosis agent's "areas to improve" ranking |
| `mathbank-mcp-competitions`'s existing MCP tools (`search_problems`, `get_problem`, `list_concepts`, `list_techniques`, `list_competitions`) | Reused via Strands' `MCPClient`, pointed at the already-deployed Function URL — **not** a new/forked MCP server |
| `object_store` (S3/filesystem abstraction) | Reused for the generated-paper JSON and per-response snapshots, exactly as requirements/53 already does it |
| **New**: question generation itself | A new Strands/Bedrock generator agent (§4) — `quiz_runtime.generate_quiz()` is OpenAI-hardcoded (`_client()`) and is **not** called by this project; generation is new code, writing into the same `quiz.*` tables so every downstream reuse above keeps working unchanged |
| **New**: critic/revision loop | Not present anywhere in requirements/53 |
| **New**: exam-mode session semantics (timed, ephemeral, zero mid-exam feedback) | requirements/53's existing flow allows per-question review as soon as a response is submitted (`QZ-5`/`QZ-9`) — exam mode deliberately withholds this (§6) |
| **New**: post-exam diagnosis (time management, reasoning guidance, ranked improvement areas) | Not present anywhere in requirements/53 — its "review" (`get_review`) returns grading + solutions, not a holistic qualitative report |
| **New**: export/print view, independent UI, Lambda deployment for this project | All new (§8, §9, §10) |

## 3. Tool surface

| Tool | Source | Used by |
|---|---|---|
| `search_problems`, `get_problem`, `list_competitions` | MCP (`mathbank-mcp-competitions`, existing, already deployed) | Generator agent — "inspired by" grounding, exactly like requirements/53's `hybrid_search.search_problems()` call, but as an agent-visible tool rather than an inline Python call |
| `list_concepts`, `list_techniques` | MCP (same server) | Generator agent — topic/skill resolution from a natural-language request |
| A new, small **direct REST tool set** (plain HTTP calls the Strands agent treats as tools, not MCP) — mastery lookup, theorem lookup, problem `difficulty_band` distribution | `mathbank-rest` (existing endpoints: requirements/61's theorem endpoints, student mastery endpoints) | Generator agent — difficulty calibration (§5); honestly scoped as **not yet MCP tools** (requirements/61's theorem catalog was never added to `mathbank-mcp-competitions`'s tool list) rather than pretending otherwise |
| `generate_quiz`-shaped question persistence (a new, thin write path into `quiz.question`/`quiz.solution`, **not** a call to `quiz_runtime.generate_quiz()` itself — see §2) | New code in `mathbank-exam-agent`, calling `mathbank-rest` over REST (never a direct DB connection — keeps the one-database-boundary rule this repo already follows) | Generator agent's final "commit the paper" step, after the critic loop (§4, §5) approves it |

## 4. Agent architecture — generator, critic, diagnoser

```mermaid
flowchart TD
    NL[Natural-language request: 10-question AIME-style paper on combinatorics, hard, 90 minutes] --> Intake[Intake: parse into style/count/types/targets/difficulty/time_limit]
    Intake --> Gen[Generator agent, Strands + Bedrock Claude Haiku]
    Gen -->|MCP tools: search_problems, list_concepts, list_techniques| MCP[(mathbank-mcp-competitions, deployed)]
    Gen -->|REST tools: mastery, theorems, difficulty_band distribution| REST[(mathbank-rest, deployed)]
    Gen --> Draft[Draft question N]
    Draft --> Critic[Critic agent, Strands + Bedrock]
    Critic -->|APPROVE| Final[Finalize question N into quiz.question/quiz.solution]
    Critic -->|REVISE, up to 2 rounds| Gen
    Final --> Paper[quiz.paper status READY]
    Paper --> Exam[Exam session: timed, ephemeral, no mid-exam feedback]
    Exam -->|submit per question, reusing quiz_runtime.submit_response| Grading[Grading + mastery absorption, unchanged from requirements 53]
    Grading --> Diagnose[Diagnosis agent, Strands + Bedrock]
    Diagnose --> Report[quiz.exam_diagnosis: time management, reasoning guidance, ranked improvement areas]
```

- **Generator agent**: given the parsed intake, drafts one question at a time (matching
  requirements/53's own per-question loop shape), grounding each draft with 2-3 MCP
  `search_problems` results for the resolved topic (never copying them — same "inspired
  by, not copied" rule as requirements/53 §4) plus a difficulty-calibration pass (§5).
- **Critic agent**: reviews each draft against a fixed rubric — mathematical
  correctness, difficulty-band match (not accidentally easier/harder than requested),
  clarity/unambiguous phrasing, and (for MCQ) distractor quality (no two options
  equivalent, no "all of the above" unless deliberately requested). Returns either
  `APPROVE` or `REVISE` with specific, structured feedback; the generator incorporates
  feedback and resubmits, capped at **2 revision rounds** per question (then the best
  version so far is kept with a `NEEDS_HUMAN_REVIEW` flag rather than looping forever —
  a bounded, observable failure mode, not a silent infinite retry).
- Every round (generator draft → critic verdict → revision, if any) is appended to
  `quiz.question.revision_log` (§4 schema) — not just the final approved version — so an
  admin can audit *why* a question looks the way it does, mirroring this repo's existing
  "audit, don't just store the final state" bias (`record_audit_event`, used throughout
  `micro_course_service.py`/`quiz_service.py`).

## 5. Difficulty determination — reusing real signals, not inventing a new model

"Use graph data and Postgres data to identify difficulty" is implemented as a **composite
signal the generator consults before drafting and the critic checks after**, built
entirely from data already computed by this repo, not a new ML model:

1. **Postgres**: `core.problem`/`pedagogy` rows' existing `difficulty_band` distribution
   for the resolved topic (same column `mastery.py`'s `normalized_difficulty`/
   `difficulty_weight` already consume) — gives a real, corpus-grounded prior for what
   "hard" means for this specific topic, not a guessed absolute scale.
2. **Postgres (student-specific, when a student_id is supplied)**: the student's current
   `concept_mastery`/`technique_mastery` scores (via `mastery.py`'s `mastery_tier`) —
   lets the generator aim slightly above the student's current tier (desirable
   difficulty) rather than a context-free "hard," when the request implies
   personalization rather than a fixed, student-agnostic mock exam.
3. **Neo4j graph**: prerequisite depth of the resolved concept/technique (how many
   `REQUIRES`/`PREREQUISITE_OF`-type edges deep it sits from foundational concepts,
   using the existing graph projection — requirements/7's own schema, no new Neo4j
   writes) — a concept requiring a longer prerequisite chain is treated as a structural
   difficulty signal independent of any one student's mastery, useful for the
   student-agnostic "generate a standard AIME-style paper" case.
4. The critic agent is given all three signals explicitly in its review prompt (not left
   to infer difficulty from the question text alone) and is instructed to flag a
   mismatch (e.g., "this reads as `easy` despite being requested as `hard`") as a
   `REVISE` verdict, not merely a note.

## 6. Exam-mode session lifecycle — ephemeral, timed, zero mid-exam feedback

Requirements/53's existing `quiz.response` flow permits viewing `get_review` (grading +
solutions) as soon as a response is submitted — appropriate for self-paced practice, but
**wrong for a mock exam**, where revealing one question's correct answer mid-exam lets a
student infer grading patterns or simply stop practicing retrieval under pressure. Exam
mode therefore adds a **session gate**, not a schema fork:

- `quiz.paper.exam_mode = true` papers reject `GET /{quiz_id}/review` with `409
  EXAM_IN_PROGRESS` until `status = 'SUBMITTED'` or later — a small, additive guard in
  the existing REST router, not new grading logic.
- The client-side "ephemeral" requirement is satisfied by **never fetching
  `quiz.solution` rows for an in-progress exam at all** (not merely hiding them in the
  UI) — the same server-side withholding principle requirements/53 §5 already uses for
  practice quizzes, just with the trigger moved from "this question has a response" to
  "this whole paper has been submitted."
- **Per-question timing**: `quiz.response.time_spent_seconds` (already exists, migration
  042) is populated client-side exactly as requirements/53 already does — this project
  adds nothing new to *capture* per-question time, only to *report on* it afterward
  (§7). A visible, client-side countdown against `quiz.paper.time_limit_seconds` (new
  column, §4) auto-submits the paper (not merely warns) when the limit is reached —
  matching real exam conditions.
- Nothing about "ephemeral" implies the data itself is deleted — `quiz.paper`'s existing
  1-day-adjacent TTL conventions elsewhere in this repo (e.g. `mathbank-manim-studio`'s
  `studio.*` tables) are **not** applied here by default, since a student's exam history
  and diagnosis report are exactly the kind of record worth keeping; "ephemeral" is
  scoped specifically to *mid-exam answer visibility*, not data retention.

## 7. Diagnosis agent — the post-exam report

A new `quiz.exam_diagnosis` row (§4 schema) is generated **once**, after `submit_response`
has been called for every question and each has been graded (reusing requirements/53's
existing grading path unchanged). The diagnosis agent is given, as structured input (not
asked to re-derive from scratch):

- Per-question: `is_correct`, `time_spent_seconds`, `difficulty_band`, the question's
  tagged concepts/techniques, and (for incorrect responses) the student's actual
  `raw_response` alongside the correct answer/solution.
- Paper-level: total time spent vs. `time_limit_seconds`, per-question time distribution
  (flagging questions that took disproportionately long relative to their difficulty
  band — a real pacing signal, not a guess).
- The student's **pre-exam** `concept_mastery`/`technique_mastery` scores for every
  tagged concept/technique (so the report can say "this confirms a known gap" vs. "this
  is a new, previously-unflagged gap," not just restate what was already known).

It produces a structured report (persisted, not just streamed):

| Field | Content |
|---|---|
| `time_management_verdict` | e.g. "well-paced," "rushed the last third," "spent 40% of total time on 2 of 10 questions" — grounded in the actual per-question time distribution, not generic advice |
| `reasoning_guidance` | For each **missed** question: a short note on the *kind* of thinking that would have reached the correct approach (e.g. "look for an invariant before attempting direct casework"), not a restated solution — the solution itself is already shown via the reused `quiz.solution` reveal |
| `improvement_areas` | A ranked list (jsonb), each entry `{concept_or_technique, current_mastery_tier, evidence: "missed 2 of 3 questions tagged here"}` — built from `mastery.py`'s real `mastery_tier()`/`build_improvement_plan()`, not an LLM free-associating topics |

## 7a. Implementation notes (this session) — real deviations from the design above

The service layer (EXM-1 through EXM-7) was fully built and live-verified this session.
Two things turned out differently from §1-§7's original design, both confirmed live,
not assumed:

- **Model backend is OpenAI, not Bedrock** — see §1's updated model-choice paragraph.
  No other architectural change follows from this; `Agent`/`MCPClient`/
  `structured_output_model=` usage is identical regardless of which `Model` backs it.
- **The corpus difficulty signal (§5 point 1) needed one new, small `mathbank-rest`
  endpoint**, not a reuse of `mastery.py` or the existing `search_problems` MCP tool as
  originally assumed. Confirmed live: neither `hybrid_search.search_problems()` (used
  internally by `quiz_runtime.generate_quiz`) nor the `mathbank-mcp-competitions`
  `search_problems` MCP tool projects `core.problem.difficulty_band` at all — it exists
  as a real column (confirmed via `information_schema.columns`) but neither retrieval
  path surfaces it. Added `GET /v1/quiz-integration/difficulty-distribution`
  (admin-gated, additive-only) instead of modifying either already-audited retrieval
  path. Also surfaced a second, real finding: the real `difficulty_band` vocabulary in
  this corpus is competition-tier labels (e.g. `"AIME D3 / Entry (Q1-5)"`,
  `"HMMT Guts / elite"`), not the simple `easy/medium/hard/very_hard` enum §5/§11
  assumed — the critic agent is given these real labels directly, not a translated or
  invented simplification.
- **A second small new endpoint**, `GET /v1/quiz-integration/students/{student_id}/
  mastery-summary`, was needed for the same reason as the difficulty-distribution one:
  the existing `/v1/learner/mastery` endpoint derives `student_id` from the caller's
  *own* bearer token (`get_current_student_id`), which doesn't fit a backend service
  acting on behalf of a specific, different student — admin-key-gated, mirroring the
  same pattern as every other `/v1/quiz-integration/*` endpoint.
- **A real, live-caught critic finding, not a hypothetical**: in one live run, the
  critic agent correctly flagged two consecutive mathematical errors in generator
  drafts (a miscounted committee-selection combinatorics problem) across 2 revision
  rounds before the bounded loop exhausted — confirmed the question was then correctly
  flagged `needs_human_review` in its `revision_log` rather than silently persisted,
  exactly matching §4's design intent (a fix made live, mid-session, after the first
  end-to-end run surfaced the gap: the original loop accepted the last draft
  unconditionally at the round cap with no flag at all).
- **Real files**: `mathbank-exam-agent/src/mathbank_exam_agent/{config,llm_models,
  rest_client,mcp_tools,schemas,intake,generator_agent,critic_agent,diagnosis_agent,
  exam_service,main}.py`; `mathbank-rest/src/mathbank_rest/routers/exam_integration.py`
  and four new functions in `quiz_runtime.py` (`import_paper`, `submit_exam`,
  `write_diagnosis`, `get_diagnosis`, `get_paper_for_diagnosis`); migration
  `mathbank-db/sql/047_mock_exam_extensions.sql` (applied live to Neon).

## 8. Export

**V1, zero new server-side dependency** (deliberately avoiding this repo's own
hard-won lesson from requirements/63 about native-dependency Lambda image bloat —
Cairo/Pango/LaTeX for `mathbank-manim-studio` was a multi-hour undertaking (GOTCHAS.md
§46) for a genuinely different, video-rendering need; a question paper is plain
text/LaTeX/diagrams, which a browser already renders perfectly well):

- A dedicated `/exam/{quiz_id}/print` route in `mathbank-exam-web` renders the full
  paper (questions only, no answers, matching the exam-mode gate in §6) with a
  `@media print` stylesheet; `window.print()` → "Save as PDF" is the export mechanism.
  Same approach for the post-exam diagnosis report at `/exam/{quiz_id}/report/print`.
- **V2 (explicitly deferred, not this implementation)**: a real server-generated PDF
  (e.g. via `weasyprint` or `reportlab`) if a "download PDF without the browser's print
  dialog" requirement emerges later — flagged here so it isn't silently forgotten, not
  built speculatively now.

## 9. Independent UI — `mathbank-exam-web`

✅ **IMPLEMENTED and live-verified** — a separate deployable frontend, not a new route
inside `mathbank-web`, per the user's explicit "independent UI" instruction. What was
actually built, differing from the plan below in two ways (static hosting target; actual
page count):

- A plain Vite + React SPA (not Next.js) — six screens in the end (`Landing`, `Signup`,
  `Login`, `ForgotPassword`, `RequestPaper`, `TakeExam`, `Review`), still noticeably
  lighter than `mathbank-web`'s full app-shell since there is no sidebar/breadcrumbs/
  admin surface. Follows the **modern-ui-design** skill's token/component contract (own
  `theme.css` with the same `--mb-*` token values, `PageHeader`/`Pill`/`Callout`/`Button`/
  `Field`, no hard-coded colors) as an independent copy, not an import, of
  `mathbank-web`'s tokens — this project has no dependency on `mathbank-web` at all.
- Calls `mathbank-exam-agent`'s own REST surface exclusively (`src/api.js`), never
  `mathbank-rest` directly — the same "one service owns its own write path" boundary
  already established across this repo.
- Live-verified in a real browser (Playwright): real Cognito signup → generated-username
  flow → logout → login; anonymous session → natural-language paper request → real
  LLM-generated MCQ paper → accordion exam-taking with event-timeline logging and
  per-question answer-locking → submit-warning modal → full review with per-option
  explanations (including specifically *why* each wrong answer is wrong) → diagnosis
  report → print/export view. Verified at both 1280px and 390px viewports, zero console
  errors. Two real bugs were caught and fixed by this testing, not left as known issues:
  a missing `started_at`/`status` guard that let a finished exam's page be revisited as
  if still in progress, and a response-submission race between confirming a question and
  immediately submitting the whole exam that could trip `quiz.response`'s
  `UNIQUE(question_id)` constraint as a raw 500 (fixed on both the frontend, with an
  in-flight-request-aware submit sweep, and the backend, converting the resulting
  `IntegrityError` into the same clean `409 ALREADY_ANSWERED` the non-racing path already
  returns).
- Deployed to **S3 + CloudFront**, not Amplify Hosting — doc 62/63's Amplify
  recommendation is specifically for this repo's *Next.js* apps (SSR); this is a plain
  static SPA with no server component at all, for which a private S3 bucket (Origin
  Access Control, no public bucket website hosting) behind CloudFront is both cheaper and
  the more idiomatic fit, with a 403/404 → `/index.html` (HTTP 200) error-response
  rewrite for client-side routing. See §10 for the full stack/URL.

## 10. Lambda deployment

✅ **IMPLEMENTED and live-verified this session** — both `mathbank-exam-agent` (backend)
and `mathbank-exam-web` (frontend) are deployed and were exercised end-to-end (real
Cognito signup, real OpenAI generation, real event-timeline logging, real diagnosis)
against their live URLs, not just localhost. Deviates from the plan originally sketched
below in two ways: this service never touches Postgres directly (all `quiz.*` data goes
through `mathbank-rest`'s REST surface, confirmed in `rest_client.py` — there is no
`PLAIN_ENV_KEYS` Postgres entry), and the model provider is OpenAI, not Bedrock (§0's
Status row), so there is no `AWS_BEARER_TOKEN_BEDROCK` secret either.

- **Backend** — `mathbank-exam-agent/Dockerfile.lambda` (own-directory build context,
  pip-installs the package + its `lambda` extra, mirroring `mathbank-rest`'s
  pip-install-then-`rm -rf` pattern rather than `mathbank-agent`'s whole-directory copy,
  since this is a proper src-layout package) + `lambda_handler.py` (Mangum-wrapped
  FastAPI app, identical cold-start-SSM-secret pattern to every other service,
  GOTCHAS.md §42). Function URL:
  `https://rp4tfkonnswyn72i7dvvijao3i0amwxw.lambda-url.us-east-2.on.aws/`.
- `mathbank-infra-aws/stacks/exam_agent_service_stack.py` — `PLAIN_ENV_KEYS` (model IDs,
  `COGNITO_USER_POOL_ID`/`COGNITO_CLIENT_ID`), `SECRET_KEY_TARGETS`
  (`OPENAI_API_KEY`, `ADMIN_API_KEY`, `COGNITO_CLIENT_SECRET`) fetched from SSM at cold
  start, plus an explicit IAM policy granting exactly
  `cognito-idp:AdminCreateUser`/`AdminSetUserPassword`/`AdminInitiateAuth`/`AdminGetUser`
  on this one User Pool's ARN (`ForgotPassword`/`ConfirmForgotPassword` need no IAM grant
  at all — they're Cognito's "public" API actions, gated by the App Client, not IAM).
  Live-verified: a real signup via the deployed Lambda succeeded using only its
  execution-role credentials, no `AWS_PROFILE` needed (unlike local dev, where the
  `aws-sutanu-admin` SSO profile must be active — README.md's own caveat).
- **Frontend** — `mathbank-exam-web` is a plain Vite/React SPA, not a Next.js app, so it
  does **not** use doc 62/63's Amplify Hosting recommendation (that's for this repo's
  Next.js apps, which need SSR). Instead: `mathbank-infra-aws/stacks/
  exam_web_static_stack.py` — a private S3 bucket (`BLOCK_ALL` public access, no
  website-hosting config) behind a CloudFront distribution using Origin Access Control,
  with 403/404 rewritten to `/index.html` (HTTP 200) for client-side routing, deployed
  via `BucketDeployment` straight from the built `dist/`. URL:
  `https://d1zj6erbhmlgyk.cloudfront.net`. `VITE_EXAM_AGENT_BASE_URL` is baked in at
  build time via `.env.production`, pointed at the backend's Function URL above.
- Two real bugs surfaced only once both services were actually deployed and called each
  other for the first time (both documented in full as GOTCHAS.md §49/§50, not repeated
  here): (1) this service's `.env` uses lowercase keys, unlike every other service's —
  the CDK stack's own case-sensitive lookup silently wired zero secrets until fixed, with
  no synth/deploy error at all, just a clean-looking-but-wrong `401` at request time; (2)
  the first request after deploying both Lambdas paid for two simultaneous cold starts,
  tripping a 15s httpx client timeout tuned for warm steady-state — raised to 30s.
- `mathbank-rest` itself was also redeployed this session (`make deploy
  STACKS="MathBankRestStack"`) — it had been deployed once, earlier in this overall AWS
  work, **before** any of requirements/64's `quiz.*` schema/router additions existed, so
  the live Lambda was stale and missing every `/v1/quiz-integration/*` route entirely
  until redeployed.

## 11. Schema (migration `047_mock_exam_extensions.sql`, additive only)

```sql
ALTER TABLE quiz.paper
    ADD COLUMN IF NOT EXISTS exam_mode boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS time_limit_seconds integer,
    ADD COLUMN IF NOT EXISTS agent_framework text NOT NULL DEFAULT 'OPENAI_DIRECT'
        CHECK (agent_framework IN ('OPENAI_DIRECT', 'STRANDS_BEDROCK'));

ALTER TABLE quiz.question
    ADD COLUMN IF NOT EXISTS revision_log jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS quiz.exam_diagnosis (
    quiz_id uuid PRIMARY KEY REFERENCES quiz.paper(quiz_id) ON DELETE CASCADE,
    time_management_verdict text NOT NULL,
    pacing_notes jsonb NOT NULL DEFAULT '[]'::jsonb,
    reasoning_guidance jsonb NOT NULL DEFAULT '[]'::jsonb,
    improvement_areas jsonb NOT NULL DEFAULT '[]'::jsonb,
    generated_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
```

No existing row, column, or constraint from migration 042 is altered or dropped —
every requirements/53 code path continues to work unchanged against
`agent_framework = 'OPENAI_DIRECT'`, `exam_mode = false` rows exactly as before.

## 12. Secrets/env wiring

- Add a `sync-bedrock-key.mjs` (mirrors `sync-openai-key.mjs` exactly): copies
  `AWS_BEARER_TOKEN_BEDROCK` from the root `.env` only into `mathbank-exam-agent/.env`,
  never echoing the value, wired into `sync-env.sh`/`make sync-keys` alongside the
  existing OpenAI/ElevenLabs/Neon syncs.
- `seed_ssm.sh mathbank-exam-agent` (existing script, no changes needed — already
  generic over `SECRET_KEYS`, just needs `AWS_BEARER_TOKEN_BEDROCK` added to that list
  in `mathbank-infra-aws/seed_ssm.sh`, the one small, explicit edit required there).

## 13. Testing plan

- NL-intake parsing: a table of real example requests ("a 10-question AIME-style paper
  on combinatorics, hard, 90 minutes" → `{style: AIME, question_count: 10,
  target_concept_slugs: [combinatorics], difficulty_band: hard, time_limit_seconds:
  5400}`) — asserted directly, not just "the agent seemed to understand."
- Generator→critic loop: a deliberately-flawed draft (wrong difficulty, ambiguous MCQ
  distractors) fed through a test double of the critic step, asserting a `REVISE`
  verdict and a bounded (≤2) revision count, never an infinite loop.
- Exam-session gating: `GET /{quiz_id}/review` on an `exam_mode=true`, still-`IN_PROGRESS`
  paper returns `409`; the same call after `SUBMITTED` succeeds — a direct port of
  requirements/53's own existing REST test style (`test_quiz_runtime.py`).
- Diagnosis synthesis: a fixture with known `is_correct`/`time_spent_seconds`/mastery
  values, asserting the report's `improvement_areas` matches what `mastery.py`'s own
  `build_improvement_plan()` would independently compute for the same input — the
  diagnosis agent's ranking must agree with the existing, trusted mastery engine, not
  contradict it.
- A real end-to-end live run (mirroring this session's own "never just unit tests"
  discipline): one real natural-language request → a real Bedrock-generated,
  critic-reviewed paper → a real timed exam session → a real diagnosis report, run
  against the live Neon Postgres instance exactly like every other project in this repo.

## 14. Parallel generation, multi-source citation, aggregate diversity, complexity signals, live progress (continued, EXM-13..18)

Four real gaps in the original design, closed in one pass: (1) `generate_exam_paper`
drafted questions one at a time, sequentially — slow for a 10+ question paper and no
cross-question check existed at all; (2) a question's real corpus inspiration was never
actually recorded (`inspired_by_problem_id` existed as a DB column and API field, but
`exam_service.py` never populated it — confirmed by reading the code, not assumed); (3)
`difficulty_band` was pure LLM self-report with no computed evidence behind it; (4) the
frontend showed one static "this can take a minute or two" message for the whole
generation call, with zero visibility into what was actually happening.

### 14.1 Architecture — "planning" layer is deterministic, not a second LLM agent

Per-question flow: **retrieve → draft → critique**, where retrieval is the corpus's
existing hybrid (semantic + lexical + graph) `search_problems` call, done
**deterministically by the orchestrator**, not left to the generator agent's own
tool-calling judgment (confirmed Strands' `Agent.__call__` cannot be shared/re-entrant
across threads — `ConcurrencyException` — so every generator/critic call already
constructs a fresh `Agent` per invocation, which is exactly what parallel execution
needs). A single, wider-than-needed candidate pool is retrieved once per paper
(`_retrieve_candidate_pool`), then **rotated into a different window per question slot**
(`_candidate_window`) so different questions in the same paper cite different real
sources instead of all converging on the same top-1 match.

```
parse_intake -> start_paper (mints quiz_id immediately, status GENERATING)
  -> resolve topic/concept slug, corpus difficulty signal, candidate pool  (once per paper)
  -> ThreadPoolExecutor: for each question slot IN PARALLEL:
       candidate_window = rotate(candidate_pool, question_index)
       loop (bounded): draft_question(candidates) -> critic review_question -> APPROVE/REVISE
  -> aggregate_critic_agent.review_paper(all drafts) -> flagged ordinals?
       -> bounded fix-up: regenerate only the flagged question(s), re-check
  -> finalize_paper (persists questions + quiz.question_source + complexity_signals, status READY)
```

Confirmed thread-safe via the actual library source, not assumed: `MCPClient.
call_tool_sync` dispatches onto its own background event loop
(`_invoke_on_background_thread`), safe for concurrent calls from multiple threads on one
shared client; `rest_client._request` opens a fresh short-lived `httpx.Client` per call.

### 14.2 Multiple inspiration sources, server-side validated

`GeneratedQuestionDraft.inspiration_sources: list[InspirationSource]` (1-3 typical,
`canonical_code` + a specific `note` on what was borrowed/changed) — the generator
prompt requires citing *only* from the candidate pool it was given; `generator_agent.
draft_question` then drops any `canonical_code` not actually in that pool before
accepting the draft (never trusts the model's own citation at face value). Persisted via
a new `quiz.question_source` junction table (migration `050`, additive — the original
singular `inspired_by_problem_id` column still gets the rank-1 source for any existing
reader), resolved back to real `canonical_code`/`competition`/`year`/`source_url` in
`quiz_runtime.get_review()` and shown as an "Inspired by" citation in the review page.

### 14.3 Aggregate diversity/dedup — a second critic pass, over the whole paper

`aggregate_critic_agent.review_paper()` runs once, after every individual question has
already passed its own per-question critic — checks only what a single-question critic
structurally cannot: cross-question near-duplication (same core setup reused) and MCQ
option text repeated verbatim across *different* questions. Flagged questions are
regenerated with specific feedback, bounded to `_MAX_AGGREGATE_FIX_ROUNDS` (2) full
passes; anything still flagged after that is kept with `needs_human_review` recorded in
`revision_log` — the same bounded, observable-failure philosophy the per-question critic
loop already used, applied one level up.

### 14.4 Computed complexity/difficulty signals, not just LLM self-report

Mirrors the real-corpus precedent (`pedagogy.problem_enrichment.solution_step_count`/
`technique_ids`, migration 010) rather than inventing a new metric: the generator now
produces `solution_steps: list[str]` (discrete, ordered reasoning steps) instead of one
prose blob — `step_count` is literally `len(solution_steps)`, not an estimate.
`concept_count`/`technique_count` come from the already-drafted `concept_slugs`/
`technique_slugs`. These are passed to the critic as explicit evidence for its
`difficulty_match_ok` check, and persisted as `quiz.question.complexity_signals` (jsonb
snapshot) + `quiz.solution.solution_steps`/`step_count` (migration `050`), surfaced as a
"6 steps · Hard" pill in the review page. `solution_text` (the human-readable, numbered
rendering) is now *derived* from `solution_steps`, never the other way around, so it can
never drift out of sync with the real step count.

### 14.5 Live generation progress — a durable, pollable event log

A new, append-only `quiz.generation_event` table (migration `050`) — one row per
meaningful step (`INTAKE`/`TOPIC_RESOLVE`/`DIFFICULTY_SIGNAL`/`DRAFT_QUESTION`/
`CRITIC_REVIEW`/`AGGREGATE_DIVERSITY_CHECK`/`AGGREGATE_FIX`/`PERSIST`/`DONE`, each
`STARTED`/`DONE`, optionally tagged with a `question_ordinal`), posted by a thread-safe
`_ProgressLog` every question-generation thread shares. This required splitting the
previously-synchronous `generate_exam_paper()` into two phases, since the frontend needs
the `quiz_id` *before* generation finishes to start polling:

- `POST /v1/exam-papers` (now `start_generation`) — parses intake, mints the quiz_id,
  status GENERATING, returns immediately (one cheap LLM call, not the N-question work).
- `POST /v1/exam-papers/{quiz_id}/run` (now `run_generation`) — the actual parallel
  generate+critique+aggregate work; re-parses the same `nl_request` (stateless across
  the two calls; the intake parse is cheap compared to what this call actually does) to
  recover fields `start_paper`'s own persisted columns don't carry (like `topic_hint`).
- `GET /v1/exam-papers/{quiz_id}/generation-progress` — polled by the frontend every
  ~1.2s while status is GENERATING.

A real 3-question live run produced 90 ordered events with genuinely interleaved thread
execution (all 3 questions' `DRAFT_QUESTION STARTED` fired before any `DONE`), confirming
real, not simulated, parallelism. `mathbank-exam-web`'s new `GeneratingPaper.jsx` page
fires `run` fire-and-forget (a real, complete HTTP request either way — not abandoned
mid-flight, just not awaited for navigation) and renders the polled event stream live.

### 14.6 Exam-taking UI — one question at a time, status-dot navigator

`TakeExam.jsx`'s accordion (every question's header stacked vertically, only one body
expanded) is replaced with a single current-question card plus a row of clickable status
dots — one per question, color + icon + tooltip coded into four states: **attempted**
(confirmed with a real answer), **skipped** (confirmed with none), **unattempted** (seen,
not yet confirmed), **not seen** (never opened). Clicking any dot jumps directly to that
question; Previous/Next buttons also work (a confirmed question, revisited, renders
read-only — options still shown with the locked-in selection highlighted, but clicks
no-op, matching the existing "once you move on, your answer is locked in" design intent,
unchanged). The underlying confirm/submit/event-logging state machine is untouched —
this was a presentation-layer change over already-correct logic.

### 14.7 What was and wasn't live-verified this pass

Live-verified, not assumed: the full parallel-generation pipeline (real OpenAI + real
deployed MCP + real Neon) including genuine concurrency, candidate-pool rotation giving
different questions different real sources, the aggregate fix-up loop actually
regenerating a flagged question, computed complexity signals, the 90-event progress log,
and the answer/skip/submit/review data contract via direct API calls against a real
generated paper. **Not yet pixel-confirmed**: the dot navigator's rendered colors/layout.
For the current resume/formatting worktree addition, focused REST and exam-agent tests
pass and the web build passes; lint exits successfully with three warnings. No live
database migration, service rollout, resume session or browser rendering was exercised.

## 15. Math-format review and durable exam resume (EXM-19; worktree only)

The critic's structured verdict now includes `math_format_ok`. Its review prompt checks
math delimiters, brace balance and compatibility with the KaTeX renderer. A question
cannot be accepted as `APPROVE` when this flag is false; the normal bounded revision
loop is used instead. This is an agent-level notation review, not a formal proof of
mathematical correctness or a guarantee that every browser font/layout renders without
overflow.

The exam UI renders math through KaTeX and places display equations in a distinct,
contrasting, horizontally scrollable surface. Invalid TeX is configured not to throw
through the page. A browser-level visual pass of this exact change remains outstanding.

For a signed-in learner, exam progress is keyed to the resolved `student_id`, not a
browser-local device identifier. The UI restores the paper's current question, each
confirmed answer, unsubmitted drafts and skip/visit state. Navigation and MCQ drafts
are saved promptly; written drafts are debounced, then flushed before navigation,
confirmation or submission. The first progress save starts the timed paper once;
subsequent saves preserve its server timestamp and do not create a graded response.
A stale or expired login returns to the login page with the exam URL preserved, so a
successful login resumes the same owned paper. A
Cognito-backed login on another device resolves to the same learner identity, so the
same owned paper can be resumed there after authentication.

The browser calls `PUT /v1/exam-papers/{quiz_id}/progress` on
`mathbank-exam-agent`; the authenticated agent proxies to the admin-key-protected
`PUT /v1/quiz-integration/papers/{quiz_id}/progress` REST route, supplying its resolved
student identity. REST checks ownership and that the paper is editable, validates the
current question and draft shape, then transactionally saves
`quiz.paper.resume_question_ordinal` and the optional
`quiz.response_draft` row. The first progress save also initializes `started_at` and
transitions a `READY` paper to `IN_PROGRESS`, without resetting that timestamp later.
Confirming an answer removes that question's draft;
skipping removes its draft; final submission removes all paper drafts. Only the
existing `quiz.response` row is graded.

Migration `051_exam_resume_state.sql` is additive and idempotent. It and the REST
migration runner exist in the worktree, but no database target has been migrated or
inspected for this feature. Running services have not been refreshed, so this behavior
is not available from the currently running application versions until rollout.
See the source-derived [quiz schema](reference/postgres/quiz.md), [REST API
inventory](reference/REST_ENDPOINTS.md) and
[implementation reference](reference/README.md). No cross-device resume or live
LaTeX-rendering result is claimed.

## 16. asyncio pipeline and the question pool (EXM-20; worktree only)

**asyncio.** `exam_service.run_generation_async` replaces the ThreadPoolExecutor:
generator/critic/aggregate/intake calls use `Agent.invoke_async` (`*_async` variants,
fresh `Agent` per call), blocking MCP/REST calls run in `asyncio.to_thread`. Intake
re-parsing overlaps MCP start-up and `list_tools`; one `search_problems` call (limit 12)
now serves both topic-slug resolution and the candidate pool; the difficulty signal and
the pool lookup run concurrently; all un-pooled slots draft concurrently (semaphore of
8), and **aggregate fix-ups for flagged slots are also regenerated concurrently** (they
were sequential). Progress events are enqueued and delivered by one background task in
ordinal order, so posting never blocks generation and `since_ordinal` polling never
skips an event. `POST /v1/exam-papers/{quiz_id}/run` is now an `async def` endpoint.
The aggregate critic now sees 1-based ordinals, matching how its flags are mapped back.

**Question pool** (`quiz.question_pool`, migration `052`): critic-approved generated
questions with full solutions (the complete finalize payload as jsonb), keyed by the
*request* inputs — paper style, requested difficulty band, normalized topic text and the
resolved concept slug — deduplicated by a sha256 `content_hash` of the normalized prompt.

```
TOPIC_RESOLVE -> POOL_LOOKUP (POST /v1/quiz-integration/question-pool/match)
  match = same style AND question_type in requested types AND same difficulty band
          AND (pg_trgm similarity(topic) >= 0.5 OR concept_slugs overlap)
          AND never already served to this student
          ORDER BY similarity DESC, times_served ASC, random()
  -> fill slots by question type from the pool; draft only the remaining slots
  -> aggregate diversity pass over pooled + fresh questions (a flagged pooled question
     is replaced by a fresh generation)
  -> finalize_paper: pooled questions link quiz.question.pool_question_id and bump
     times_served; fresh questions that reached a clean critic APPROVE carry
     add_to_pool=true and are written into the pool (needs_human_review ones are not)
```

A near-identical request is therefore served largely or entirely from the pool, while
repeat requests by the same student keep drafting new questions, so the pool keeps
growing. Pool lookup failures (for example before migration 052 is applied) are logged
and generation falls back to drafting every question.

**Quality gate.** Hard/very-hard is defined by non-trivial interaction of multiple
concepts, constraints or techniques, never by solution-step count or by extracting one
easy named operation from a difficult source problem. When multiple corpus candidates
exist, a hard draft must combine distinct contributions from at least two and state a
`synthesis_rationale` that the critic independently verifies. Generator and critic
default to `gpt-4o`, malformed JSON/TeX escape artifacts are normalized before review,
and deterministic delimiter plus MCQ-structure checks supplement the LLM critic. A
critic-rejected draft is regenerated up to four times (later attempts must abandon the
old setup); if no draft passes, `POST /v1/quiz-integration/papers/{quiz_id}/fail` marks
the paper `FAILED`. Rejected questions are never persisted, served, or added to the
pool.

## Open questions to resolve before implementation starts

1. **Phasing**: this is a genuinely large build (new agent service + new independent UI
   + new Lambda stack), comparable in scope to the entire requirements/63 deployment
   arc. Recommended phasing: (a) service layer + generator/critic agents + REST API,
   live-tested without a UI first (matching this session's own established "service
   layer first" pattern), (b) exam-session + diagnosis logic, (c) `mathbank-exam-web`,
   (d) Lambda deployment. Confirm this order, or a different priority, before starting.
2. **Student identity**: should `mathbank-exam-agent` require an authenticated
   `student_id` (full personalization, per §5 point 2) or support an anonymous/guest
   mock-exam mode (student-agnostic, corpus-difficulty-only calibration, per §5 point
   3)? Both are designed for above, but v1 scope should pick one as the default.
3. **`submit_response`'s free-text/proof grading still calls OpenAI internally**
   (requirements/53, unchanged by this project per §2) — confirm this is acceptable for
   v1 (grading quality is already proven and live-verified) rather than a hard
   requirement to also move grading to Bedrock, which would be a separate, larger change
   to requirements/53's own code, not this project's.

## Cross-document relationship

Builds on [requirements/53](53_AI_GENERATED_QUIZ_SUBAGENT.md) (schema, grading, mastery
absorption — reused, not forked), [requirements/61](61_THEOREM_AXIOM_LEMMA_CATALOG.md)
(theorem data, consulted as a difficulty/grounding signal via direct REST, not yet an
MCP tool), and [requirements/62](62_AWS_SERVERLESS_DEV_HOSTING_COST_RESEARCH.md)/
[requirements/63](63_AWS_SERVERLESS_DEPLOYMENT_IMPLEMENTATION.md) (the Lambda deployment
pattern this project's §10 reuses directly, including every GOTCHAS.md lesson learned
there). The [modern-ui-design](/Volumes/External/Developer/knowledge-bank-ingestion/.github/skills/modern-ui-design/SKILL.md)
skill governs `mathbank-exam-web`'s visual contract even though it is a separate app from
`mathbank-web`.
