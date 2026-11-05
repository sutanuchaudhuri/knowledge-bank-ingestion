# Exam / quiz layer on DynamoDB — API-test findings

Source of the findings: the `exam_*` journeys in `apitest/journeys/` run with
`.venv/bin/python -m apitest --mode test-writable --suite journeys --only exam_identity exam_paper_20q exam_paper_small exam_fail_paths exam_quiz_learner exam_question_pool exam_race_respond exam_race_finalize exam_race_progress exam_race_submit exam_isolation exam_edge_cases`
(real uvicorn, real DynamoDB `-test` tables, content/vectors read from `dev`, 12 journeys). Last full run: 831 checks, 8 failed; the 8
failures are the 8 entries marked **FAIL** below (F1–F7; F3 accounts for two). Nothing under `src/` was edited.

Clean areas (no finding): learner isolation (every `/v1/quiz/*` route and every service route with a foreign `student_id` answers 404 and
changes nothing), credentials on all 24 exam-integration operations and 7 quiz routes (none / wrong key / learner bearer / garbage and
tampered bearer / service key as bearer → 401 or 403, nothing created or mutated), answer-key non-disclosure in `get_quiz`, finalize,
progress, in-exam respond, events and the EXAM_IN_PROGRESS refusal (marker-string and key-name scan), duplicate respond (8 parallel → exactly
one 200, 7 × `ALREADY_ANSWERED`, no phantom counter increments), parallel finalize (2 and 4 writers → one winner, no interleaved questions),
parallel progress (no lost drafts, no answered question keeps a draft), duplicate / parallel generation-event ordinals, parallel submit and
diagnosis writes, respond-vs-submit, unicode / LaTeX round trips, 10 000-char drafts, 26-option MCQ, 450 KB solution (accepted), minimal
questions, versioned diagnosis, `since_ordinal` paging across the 9→10 boundary.

---

## F1 — FAIL — Medium — `correct_count` in the "my papers" lists discloses correctness while the exam is open

* Endpoints: `GET /v1/quiz/mine` (learner bearer) and `GET /v1/quiz-integration/papers/mine?student_id=` (service key).
* Request: start + finalize a 20-question exam (`exam_mode=true`), answer question 1 correctly (`POST …/respond {"selected_key":"B"}`), then
  `GET /v1/quiz/mine`.
* Observed: `{"quiz_id": "...", "status": "IN_PROGRESS", "question_count": 20, "correct_count": 1, ...}`. The in-exam respond body is correctly
  `{"saved":true,"question_id":…,"answered_count":1}`, but the list reveals whether each answer was right, one answer at a time, before submit.
* Expected: during an exam (`answer_disclosure=AFTER_SUBMIT`, status READY/IN_PROGRESS) `correct_count` must be 0/absent until the paper is
  submitted (the review gate is `quiz_logic.review_open`).
* Source: `stores/exam/papers.py:317-333` (`list_my_quizzes` projects `correct_count` from GSI1; the counter is incremented at `:706`); the
  PostgreSQL original has the same projection (`quiz_runtime.py:557-568`), so this is inherited, not a migration regression — but it defeats the
  non-disclosure the exam path is built around. Journey check: `exam_paper_20q / LEAK: /v1/quiz/mine hides correct_count …`.

## F2 — FAIL — Medium — `POST /papers` (import) with an invalid question leaves a stray GENERATING shell per refused call

* Request: `POST /v1/quiz-integration/papers` with a valid paper header and one question whose `question_type` is `ESSAY` (→ 422
  `INVALID_QUESTION_TYPE`), and another with `difficulty_band:"legendary"` (→ 422 `INVALID_DIFFICULTY_BAND`).
* Observed: both are refused with 422, but `GET /papers/mine` afterwards shows 2 new papers `GENERATING` titled like the request. They never
  leave GENERATING (no TTL, no fail), and they are listed in the learner's own `/v1/quiz/mine`.
* Expected: `import_paper` docstring: "everything is validated before the first write (no stray GENERATING shell)".
* Source: `stores/exam/papers.py:368-383` — only `validate_paper_request` (paper-level) runs before `start_paper` (`:378`); question-level
  validation lives in `finalize_paper` (`:516-523`, `_pp_question_items`/`normalize_band`) and runs after the shell exists. An agent that
  retries a bad payload creates one orphan shell per attempt. Journey: `exam_paper_small / refused import leaves no GENERATING shell behind`.

## F3 — FAIL (2 checks) — Medium — a router-valid but malformed question makes finalize return 502 and permanently FAILs the paper

* Request: `POST /papers/{id}/finalize` with one MCQ whose `options` is `[{"key":"A"},{"key":"B"}]` (items without `text`; the router types
  `ImportQuestion.options` as `list[dict]`, `routers/exam_integration.py:77`).
* Observed: `502 {"detail":{"code":"GENERATION_FAILED","message":"paper finalization failed"}}`; the paper is now `FAILED`, so the agent can
  neither fix and re-finalize (404 "no GENERATING quiz") nor continue. Other client errors (bad type/band) correctly stay 422 and leave the
  shell GENERATING and reusable.
* Server log:

  ```
  paper finalization failed for quiz 9f99f39d-…
  File ".../stores/exam/papers.py", line 535, in finalize_paper
    self._pp_question_items(uow, quiz_id, ordinal, q, refs=refs, problem_ids=problem_ids, ...
  File ".../stores/exam/papers.py", line 469, in _pp_question_items
    uow.put_new(ep.ExamQuestionItem(
  pydantic_core._pydantic_core.ValidationError: 2 validation errors for ExamQuestionItem
  options.0.text  Field required [type=missing, input_value={'key': 'A'}, input_type=dict]
  ```
* Expected: 422 (e.g. `INVALID_OPTIONS`) with the paper left GENERATING, like the other validation errors.
* Source: `papers.py:548-551` (`except Exception` → `_pp_fail` + 502) wraps typed-model construction at `:469`; validate the question shape
  (type the router's `options` as `{key,text}`) or map `pydantic.ValidationError` to a 422 before the `_pp_fail`.

## F4 — FAIL — Low/Medium — parallel answers to different questions of one paper are refused with 409 CONFLICT beyond ~3 writers

* Request: 8 simultaneous correct answers to 8 different questions of one exam (service and learner routes mixed).
* Observed (two runs): 5/8 and 6/8 saved, the rest `409 CONFLICT "the paper changed while answering; try again"`. 3 simultaneous answers: all
  saved. Every saved answer was counted exactly once (`answered_count` values unique and consecutive; stored `correct_count` equal to the number
  of 200s) — there is no lost update, only refused legitimate answers.
* Expected: a valid, first answer to an unanswered question should not be rejected because another question was answered at the same moment.
* Source: every respond is version-guarded on the single PAPER item (`papers.py:706` `expected={"version": cur.version}`) with
  `RACE_ATTEMPTS = 3` (`:54`, retry at `:712`) and a 30–120 ms backoff (`stores/learner/uow.py:181-190`). The paper item is a hot partition key
  per exam. Realistic double-click/autosave concurrency (2–3) is fine; consider an atomic `ADD` counter without the version guard, or more
  attempts. Journey: `exam_race_respond`.

## F5 — FAIL — Low — respond accepts an answer that is not one of the options

* Request: `POST /papers/{id}/questions/{q}/respond {"student_id":…, "selected_key":"ZZ"}` on a 3-option MCQ.
* Observed: 200 `{"saved":true,…}`; the answer is stored and graded wrong and the question is now `ALREADY_ANSWERED` (a typo cannot be corrected).
  `PUT …/progress` with the same value is refused with `INVALID_DRAFT`.
* Expected: same validation as the draft (`quiz_logic.validate_exam_draft`, `:97-111`) before grading.
* Source: `papers.py:654-675` goes straight to `ql.grade_answer` (`quiz_logic.py:354-362`). Journey: `exam_paper_small`.

## F6 — FAIL — Medium — `GET /difficulty-distribution` is slow and returns corpus-native labels, not the quiz band vocabulary

* Request: `GET /v1/quiz-integration/difficulty-distribution?concept_slug=<any real concept from /v1/concepts>`.
* Observed: **14–15 s** (the unknown-slug and technique calls take 0.2–0.5 s) and a body such as
  `{"distribution":{"AIME D3 / Entry (Q1-5)":234,"AIME D4 / Core (Q6-9)":197,"MPG Main / empirical":40,"CMM Team / proof-style":7,…}}`.
* Expected: the generator's vocabulary is `easy|medium|hard|very_hard` (`quiz_logic.BANDS`, `normalize_band` rejects everything else), so a
  distribution the agent cannot map to the bands it must send back is of little use; and a request path should not take 15 s.
* Source: `papers.py:935-956` (one GSI1 query over the concept's PTAG partition, then a `batch_get` of every problem item). The labels are the
  stored `core.problem.difficulty_band` (the original docstring says the same), so this is a product question (normalise in the read model?),
  plus a latency problem for popular concepts (precompute/cache). Journey: `exam_identity / distribution (concept_slug) is band -> count`.

## F7 — FAIL — Low (product) + harness limitation — `POST /v1/quiz/generate` is 502 in `test-writable` mode; a best-effort cache write is fatal

* Request: `POST /v1/quiz/generate {"style":"AIME","question_count":2,"question_types":["MCQ"]}` with a learner bearer.
* Observed (harness server): `502 GENERATION_FAILED`. Log: `embeddings.embed_text → _to_shared_cache → typed.put(ContentQemb) → ddb._guard →
  ReadOnlyViolation: AWS write guard blocked dynamodb.PutItem` (`hybrid_search.search_problems` → `embeddings.py:81`).
* Cause: the harness maps `content` to `dev`, and the query-embedding cache is a *content-table write on a request path*, which the guard
  correctly refuses. With the content context pointed at `test` (a one-off server started with `MB_DDB_ENV_OVERRIDES=vectors=dev`, same
  guard) generate returns 200 in ~10 s and every learner check (generate → mine → get → progress → respond → review → GRADED → diagnosis, 61
  checks) passes — so the DynamoDB generate path itself works.
* Product-side robustness: `embeddings._to_shared_cache` swallows only `StoreError` (`embeddings.py:100-106`); any other exception from the
  cache write (here `ReadOnlyViolation`, a `RuntimeError`) aborts the whole embedding and with it the request (generate 502; the pool topic
  branch is silently disabled — `question-pool topic branch unavailable` in the log). A best-effort cache should swallow `Exception`.
* Journey: `exam_quiz_learner / generate a practice quiz (LLM)` (kept failing on purpose; everything after it runs only when generate works).

---

## Observations (no defect, recorded for the product questions)

* Question pool (`exam_question_pool`, 44 checks pass): write-back + exact duplicate (content-hash sentinel → no new entry) + near-duplicate
  inside one finalize (two prompts differing by a final `.` link to one entry → 2 entries for 3 questions) + `pool_question_id` serving
  (served entry no longer offered to that learner; an unknown id is ignored) + the writer never gets its own entries all behave as designed.
  Entries stay `vector_state=PENDING` because `s3vectors.PutVectors` to the `dev` bucket is guard-blocked
  (`question-pool vectors not written … left PENDING`), and the dev `QUIZ_QUESTION` index is empty, so the vector branch returned no rows: every
  returned match has `topic_similarity == 0.0`. Near-duplicate-by-index and topic matching are therefore not exercised end to end.
* The match route returns 200 `[]` for an unknown style, band outside the vocabulary and an unknown student (never 5xx).
* A 450 KB `solution_text` is accepted (offloaded), a draft of exactly 10 000 characters round-trips, 10 001 → 422.
* Mid-exam `diagnosis-input` returns solution text to the service key (expected: service-only route).
* `PUT progress` while a paper is GENERATING / FAILED / submitted → 409 `EXAM_NOT_EDITABLE`; `fail` on an open/READY/GRADED paper is a no-op
  returning the unchanged view; generation events are still accepted after FAILED and refused after submit.

## Harness defects (apitest/*.py outside journeys/, not edited)

1. `Ctx.unique_email()` builds `…@example.test`; `POST /v1/learner/register` (EmailStr) rejects that special-use domain with 422, so any
   journey registering a learner with it fails. The exam journeys use their own `@example.com` helper (`exam_common.email`).
2. `test-writable` maps `content=dev`, which makes every content-table write on a request path (the shared query-embedding cache) a blocked
   write: `POST /v1/quiz/generate` cannot pass and every embedding call raises after the provider call (cost incurred, result discarded);
   the pool topic branch is disabled. A separate `content=test` data plane (or a QEMB cache in a `-test` table) is needed for those paths.
3. `apitest/reports/server-test-writable.log` is overwritten by each run, so tracebacks of earlier runs are lost; the report counts only the
   last run's tracebacks.
