# 19 — Gotchas and Operational Pitfalls (exhaustive catalog)

Every entry below was hit for real while building this repository, or is a rule that exists because of something that was hit.
Each entry gives the **symptom**, the **cause**, and the **rule or fix**, plus **where it is enforced** when that is code.

- The narrative, machine-setup history lives in [GOTCHAS.md](../GOTCHAS.md); "root §N" below refers to it.
- This document is the requirements-level catalog: new work must not reintroduce any of these.
- When you hit a new pitfall, add it here (and to root GOTCHAS.md when it is a machine-setup issue), and add a row to the change log at the bottom.

IDs are stable (`GOT-<area>-<n>`). Areas:
`SRC` source data · `PG` PostgreSQL · `GR` graph · `RUN` pipeline runners · `ENR` enrichment · `ENV` credentials/tools · `WEB` UI/REST/agent · `TEST` tests/verification · `VEC` vectors · `DIAG` gap diagnosis · `REC` recovery · `WALK` walkthrough/transcripts · `ATB` admin textbook dashboard · `GEO` geometry runtime completion (doc 26).

---

## 1. Source data and import packages (`SRC`)

| ID | Symptom | Cause | Rule / fix (enforced in) |
|---|---|---|---|
| GOT-SRC-1 | The first CSV column name is `\ufeffproblem_id`, so key lookups fail. | Prasolov CSVs carry a UTF-8 BOM. | Always open package CSVs with `encoding="utf-8-sig"` ([import_textbook_package.py](../mathbank-db/etl/import_textbook_package.py)). |
| GOT-SRC-2 | Problem `13.39` appears twice in Ch01_20. | One copy is chapter-INTRO prose mis-tagged as a problem. | The real problem is kept and the INTRO copy rejected, with WARNING `DUPLICATE_PROBLEM_ID`. The taxonomy row is resolved by section. Never abort the package for this. |
| GOT-SRC-3 | Solutions `SOL-3.61` and `SOL-5.79` have no problem. | Orphans in the source. | Rejected with WARNING `ORPHAN_SOLUTION`; source 1,274 → DB 1,272 still reconciles because rejections are counted. |
| GOT-SRC-4 | The same part/step ID appears more than once (81 parts, 140 steps). | Source ID generator collisions. | Keep every row: the k-th repeat gets the suffix `#k` and the `occurrence` column. The step at occurrence k attaches to part occurrence k; dependencies on a repeated ID resolve to occurrence 1 (INFO conflict). |
| GOT-SRC-5 | 47 parts have `step_count` ≠ imported steps. | Source counting errors. | Store the actual count in `step_count` and the source value in `source_step_count`; record INFO `STEP_COUNT_MISMATCH`. Do not drop the steps. |
| GOT-SRC-6 | 7 duplicate transformation IDs (all on 13.39). | Same as GOT-SRC-2. | Imported as `#2` occurrences, with INFO. |
| GOT-SRC-7 | Anchor lookups fail for some learning items. | `solution_step_anchor_id` is pipe-delimited (`A|B`). | Split on `|` into `pedagogy.learning_item_step_anchor` with `anchor_ordinal`. |
| GOT-SRC-8 | The same taxonomy node has different names in the two Prasolov packages. | Packages were authored separately. | The first name is kept; INFO `NAME_CONFLICT`. 43 shared nodes are unchanged. |
| GOT-SRC-9 | Ch21_30 has extra columns; problems 23.8 and 23.19 are renumbered. | Later package revision. | The importer reads columns by name and keeps unknown columns in `source_metadata`. Renumbering is preserved in `source_printed_problem_id` and `source_numbering_note`. |
| GOT-SRC-10 | Dependency source rows (5,699) exceed stored edges (5,658). | Duplicate `(from, to, type)` rows. | Merge by primary key. Reconciliation counts unique edges plus merged duplicates. Do not "fix" this mismatch by inserting duplicates. |
| GOT-SRC-11 | A transformation has `no_proof=FALSE`. | Proof transformations are out of scope. | Rejected; `pedagogy.learning_item.no_proof` has `CHECK (no_proof)`. |
| GOT-SRC-12 | Solution diagrams leak the answer. | `SOLUTION` usage diagrams were initially candidates for problem images. | Only `STUDENT_PROBLEM` diagrams link to `core.problem_image`. `SOLUTION_HIDDEN` never do; the safety SQL in [doc 18](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md) must return 0. |
| GOT-SRC-13 | Some legitimate old PDFs were rejected as "not PDF". | `startswith(b"%PDF-")` fails on whitespace-prefixed headers. | Accept a header within the first 1024 bytes after whitespace; still reject HTML. Validate both official hosts (root, Purple Comet section). |
| GOT-SRC-14 | `/files/...pdf` returns the homepage with HTTP 200. | Dead archive links. | Check the PDF bytes and retain an explicit failed source; never classify the homepage. |
| GOT-SRC-15 | Purple Comet question counts differ by year. | Old HS contests do not all have 30 questions. | Take the count from the official answer table and enforce it exactly. |
| GOT-SRC-16 | Docling output collapses to a single whole-paper block. | Docling emits `## Problem 1` (and `## Problem1`), but the regex expected bare `Problem 1`. | Treat Markdown heading prefixes as question headings, use a forward consecutive sequence, then enforce exact counts. |
| GOT-SRC-17 | A diagram or continuation page is missing. | Proportional page assignment. | Follow the numbered page spans and keep full-page renders as well as embedded rasters. |
| GOT-SRC-18 | An answer key was being treated as a solution. | Answer-only PDFs. | Answers go to `core.problem.official_answer`. Never fabricate `core.solution` rows. |
| GOT-SRC-19 | MPG Problems 1–9 are corrupted. | A "Directions" cover page (root §8). | Skip the cover page before splitting. |
| GOT-SRC-20 | `\x00` in parsed text fails Postgres inserts. | OCR/PDF NUL bytes (root §7). | Strip NUL before insert. |
| GOT-SRC-21 | Prasolov problems disappear when filtering by year. | The textbook edition has `year` NULL. | Hybrid search year filters exclude textbooks by design. Filter on competition or level instead when textbooks should be included. |

## 2. PostgreSQL / Neon (`PG`)

| ID | Symptom | Cause | Rule / fix |
|---|---|---|---|
| GOT-PG-1 | `deadlock detected` between the textbook importer and the enrichment watcher (`knowledge.skill` vs `knowledge.concept`). | They took row locks on knowledge tables in different orders. | Every writer of `knowledge.*` starts its transaction with the same `LOCK TABLE … IN SHARE ROW EXCLUSIVE MODE` list, in the same order as `import_pedagogy.import_manifest` (`KNOWLEDGE_LOCK` in the importer). New writers must reuse that list. |
| GOT-PG-2 | The watcher could see a problem without skills and charge a paid model call for it. | Its `select_work` picks problems lacking `problem_skill` OR `problem_pedagogy`. | Problems, solutions and their knowledge rows are written in one transaction. Safety SQL "watcher would pick 0 Prasolov problems" must return 0. |
| GOT-PG-3 | Relationship enrichment costs appear after the textbook import. | `--relationships` mode queues newly bridged skills and concepts. | Expected and auto-approved; monitor it in the job console. Pause the watcher before importing if spend must be avoided. |
| GOT-PG-4 | `CHECK` violation when showing a learning item to students. | `student_visible` requires `review_status='APPROVED'` (`learning_item_visible_requires_approval`). | Approve first; never bypass the check. Re-imports only update rows still `PENDING_REVIEW`, so admin decisions survive. |
| GOT-PG-5 | Two `solution_step` tables exist. | Legacy `core.solution_step` (0 rows) predates v2. | Use `pedagogy.solution_step`; leave the legacy table untouched until a dedicated migration. |
| GOT-PG-6 | Textbook edition insert fails on `year NOT NULL`. | Contest-only schema. | Migration 010 made `core.competition_edition.year` nullable. Code that assumes a year must handle NULL. |
| GOT-PG-7 | `core.problem_image.local_path` breaks on another machine. | It stores absolute paths. | Treat it as host-specific; resolve through the data root when moving machines. |
| GOT-PG-8 | `psql: command not found`, or the wrong version. | Homebrew `postgresql@16` is keg-only. | Use `/opt/homebrew/opt/postgresql@16/bin/psql` (Makefile `PG_BIN`), not the data-directory path. |
| GOT-PG-9 | Advisory lock acquired "twice", and a duplicate runner starts. | Neon's pooled endpoint does not keep session-scoped locks. | Use the **direct** endpoint (`_connect(direct=True)`) for `pg_try_advisory_lock(hashtext('mathbank-paper-batches'))`. |
| GOT-PG-10 | Unqualified pgvector operators/types fail on Neon. | `neondb_owner` has an empty `search_path` (root §15). | Schema-qualify, or `SET search_path` explicitly. |
| GOT-PG-11 | `:param::type` binds silently fail. | SQLAlchemy `text()` with an adjacent cast (root §9). | Use `CAST(:param AS type)`. |
| GOT-PG-12 | JSON shows `"0E-20"`, or numbers arrive as strings. | `NUMERIC` serialization (root §20–21). | Cast to `float8` in SQL or convert in the API layer. |
| GOT-PG-13 | Queries by a broad concept slug match almost nothing. | The concept taxonomy is hierarchical (root §16). | Expand descendants (HAS_SUBCONCEPT) before filtering. |
| GOT-PG-14 | Local Postgres connection refused on 5432. | The project runs Postgres 16 on **5433** (root §2). | Use port 5433. |
| GOT-PG-15 | `CREATE EXTENSION vector` fails locally. | Homebrew pgvector targets PG17/18 only, and owner privileges are needed (root §3–5). | Build pgvector for PG16 as documented in root §4–5. |
| GOT-PG-16 | A Neon quota-exceeded error stops runners. | Account compute/storage quota. | The runner fails explicitly. Resume only after `SELECT 1` succeeds; never auto-restart paid work blindly. |
| GOT-PG-17 | The "latest graph projection" can be a textbook step run rather than a batch corpus run. | `pipeline.graph_projection` now holds several `graph_name`s (`corpus_graph`, `textbook_step_graph`). | The admin list (`list_graph_projections`) shows `graph_name`. Any code reading "the latest projection" must filter by `graph_name`. |
| GOT-PG-18 | The spec's `learner.attempt` would collide with the existing table. | The existing `learner.attempt` (003) is an append-only per-answer log (`is_correct NOT NULL`) that drives mastery; the spec's attempt is a stateful session with a current step. | Session lives in new `learner.solve_attempt`. On completion the runtime writes one `learner.attempt` row (`source='step_runtime'`), links it by `outcome_attempt_id`, and recomputes mastery **after commit**. Never repurpose `learner.attempt`. |
| GOT-PG-19 | Idempotent replay can't be stored on the event. | `learner.event` is append-only (trigger), and one request writes several events. | Replay responses live in `learner.idempotency_record` (student, key, operation, request_hash). A matching hash replays; a mismatch returns 422 `IDEMPOTENCY_KEY_REUSED`. Only one event per request carries the key (UNIQUE `(student_id, idempotency_key)`). |
| GOT-PG-20 | `UPDATE`/`DELETE` on `learner.event` raises `append-only`. | Trigger `event_append_only` (012). Erasure of a student is a soft delete. | Corrections are new events. A hard delete of a student profile must explicitly disable the trigger as an audited admin action. |
| GOT-PG-21 | Double "start" clicks or races could create two open sessions. | Concurrent requests. | Partial unique index `solve_attempt_one_open` plus `pg_advisory_xact_lock(hashtext(student:problem))`; start resumes the open session. Mutations lock the attempt `FOR UPDATE` and check `state_version` (stale → 409). |

## 3. Graph / Neo4j Aura (`GR`)

| ID | Symptom | Cause | Rule / fix |
|---|---|---|---|
| GOT-GR-1 | `RETURN count(x) papers` is a syntax error on Aura. | Current Cypher requires `AS` for aliases. | Always write `RETURN count(x) AS papers`. |
| GOT-GR-2 | A projector deleted another projector's edges. | The paper-batch `--pedagogy` projection is an atomic replacement of everything with `projection_kind='pedagogy'`. | Every projector tags its writes with its own `projection_kind` and prunes only that kind. The textbook step layer uses `solution_steps` and was verified to survive `--pedagogy` ([project_textbook_steps.py](../mathbank-graph/etl/project_textbook_steps.py)). |
| GOT-GR-3 | Graph writes fail intermittently (routing/disconnect/deadlock). | Aura transient errors. | Write through `session.execute_write` (driver retries) plus an outer retry on `TransientError/ServiceUnavailable/SessionExpired`. The legacy corpus functions use auto-commit `session.run` without retries; don't copy that pattern. |
| GOT-GR-4 | `MERGE` silently created nothing for edges. | The `MATCH` endpoint node did not exist yet. | Return `count(r)` per batch and fail when written ≠ sent. Base Problem/Solution/Skill/Concept nodes come from `project_from_postgres.py --pedagogy` first (`make -C mathbank-db textbook-graph-remote` runs both). |
| GOT-GR-5 | A provenance query stalled the graph subprocess. | Unlabeled `MATCH (n)` full scans. | Always match on an indexed label plus `canonical_id`. Uniqueness constraints exist for every projected label, including `SolutionPart`, `SolutionStep` and `LearningItem`. |
| GOT-GR-6 | Solution text duplicated in the graph. | The spec makes Postgres canonical. | Project metadata only: no `step_text`, no learning-item `question_text`. The graph is never the import target ([pack 22_WHAT_NOT_TO_DO](../math_tutor_new_requirements_copilot_pack_v2_expanded/runtime_extension/22_WHAT_NOT_TO_DO.md)). |
| GOT-GR-7 | Unreviewed content becomes reachable through the graph. | Projecting PENDING_REVIEW learning items. | Only APPROVED and `student_visible` items are projected. Items that lose approval are pruned on the next run. |
| GOT-GR-8 | "Edges upserted" in the logs differs from the live edge count. | Log counts are write operations, not inventory. | Reconcile with `--status`/live counts. Graph failures display UNKNOWN, never 0. |
| GOT-GR-9 | No dedicated Subconcept nodes. | Subconcepts are `knowledge.concept` level-2 rows. | They are `:Concept` nodes with an extra `:Subconcept` label; `USES_SUBCONCEPT` targets that label. |
| GOT-GR-10 | The step projector can't share the batch advisory lock. | The batch runner holds `mathbank-paper-batches` for its whole run. | The step layer is independent (own kind, idempotent MERGE plus prune). Check `pipeline.graph_projection` for IN_PROGRESS rows before running it manually. |
| GOT-GR-11 | `NEO4J_CONF` Makefile variable breaks Neo4j startup. | It collides with Neo4j's own environment variable (root §11). | Don't use that name. |

## 4. Pipeline runners and batches (`RUN`)

| ID | Symptom | Cause | Rule / fix |
|---|---|---|---|
| GOT-RUN-1 | Two runners process the same papers. | A retry was started while the original runner held the lock, and process IDs were confused. | Before resuming: run `SELECT 1` on Neon, check the advisory lock is free, and check that no runner or classifier process is alive. Use `--resume RUN_UUID --paper CODE --wait-for-lock` for scoped retries. |
| GOT-RUN-2 | Papers fail with a 900 s parse timeout (`HMMT_2023_HMIC`, `HMMT_2022_HMIC`, `SMT_2022_GENERAL`). | Large CPU Docling parses. | Exclude them from bulk retries and retry individually with a longer timeout. A timeout is a FAILED status, not success. |
| GOT-RUN-3 | A `TimeoutExpired` traceback after 15 s. | The subprocess polling loop. | It is not a 15 s classification limit; read the stage log. |
| GOT-RUN-4 | Docling GPU filled the system disk and produced bad parses. | MPS model caches on the system volume. | Docling runs on **CPU** with formula enrichment. `HF_HOME`, `TORCH_HOME` and `TMPDIR` point at the external drive. Never switch to GPU. Never claim a native-text fallback as a Docling success. |
| GOT-RUN-5 | `graph_verified` was read as "everything done". | It covers only the batch graph stage. | Vectors, teaching metadata and relationships are measured separately (nine-layer completion, [doc 16](16_PIPELINE_JOB_CONSOLE_AND_HYBRID_RAG.md)). |
| GOT-RUN-6 | A stale heartbeat or IN_PROGRESS row. | The process died or stopped reporting. | Evidence of stalled reporting, not proof of exit. Verify the PID before acting. |
| GOT-RUN-7 | ARML must not start early. | It depends on the full Purple Comet snapshot. | ARML stays blocked until Purple Comet covers 44 sources with classification, graph and vectors complete. |
| GOT-RUN-8 | Background runs were invisible afterward. | There was no persistent progress record (root §17). | Every run writes `pipeline.*` rows and logs under `mathbank_data_ingestion/logs/`. |
| GOT-RUN-9 | ETL scripts wrote to local Postgres while Neon was intended. | Hard-coded local connection (root §18). | Use `PG_ENV_FILE=…/mathbank-graph/remote.env` for remote work. |
| GOT-RUN-10 | Running workers still use old code. | Python modules are loaded at start. | Code changes apply only after a safe restart; record which PID runs which code. |
| GOT-RUN-11 | Killing a process by a stale shell ID hit the wrong one. | Replacement processes were not started under the tracked IDs. | Kill only by a verified PID. Never use name-based kills. |
| GOT-RUN-12 | The enrichment watcher silently stopped (exit 1) during another job's import. | PostgreSQL chose the watcher as the victim of the Prasolov pilot deadlock. Nothing restarts it. | After any deadlock, import or migration, check `ps` for exactly one `enrich_corpus.py --watch` process and the last `logs/automatic-enrichment.log` timestamp. Restart it only after confirming no watcher is running. |
| GOT-RUN-13 | A paper batch run ends with `exit=1` although most papers loaded. | The runner exits non-zero if any paper failed. Run `ae2a966c…` (SMT/HMMT) ended at 257 completed / 29 failed. Most failures are 1999–2000 HMMT layouts that raise `Whole-paper fallback is not a question-level parse`, plus parse timeouts (900 s). | Read the final `RUN … completed=…, failed=…` line, not only the exit code. The whole-paper guard is intentional (GOT-SRC-16): fix the splitter for that layout or exclude the paper; never accept a whole-paper block as a question. |

## 5. Enrichment and approval (`ENR`)

| ID | Symptom | Cause | Rule / fix |
|---|---|---|---|
| GOT-ENR-1 | HTTP 200 from the model, but bad metadata. | A successful call is not validated output. | Schema, cycle and independent semantic verification all run before automatic approval ([doc 14](14_AUTOMATIC_ENRICHMENT_RECOVERY.md), [doc 15](15_RELATIONSHIP_ENRICHMENT.md)). |
| GOT-ENR-2 | `COMPLETED` jobs with null `published_at`. | Generation and graph publication are separate. | Retry publication without new model calls. |
| GOT-ENR-3 | Four watchers caused lock contention. | Parallelism was applied at the wrong level. | Run one watcher with `--workers 4`. SIGTERM drains the threads; wait for the PID to exit before replacing it. |
| GOT-ENR-4 | Other problems were falsely labeled human-reviewed. | Teaching publication replaces the whole owned edge layer. | Include `approval_method` inside the atomic replacement. |
| GOT-ENR-5 | Model enum budget exceeded. | The concept catalog was duplicated in the structured-output schema. | Share it with `$ref`. |
| GOT-ENR-6 | Synonyms, reversed edges and false prerequisites in pilots. | Relationship semantics are subtle. | PART_OF is component → composite; BUILDS_ON is prior → dependent; PREREQUISITE_OF is foundation → dependent. Independent verifier; never relabel existing edges to fill an empty view. |
| GOT-ENR-7 | Changing the model creates more paid work. | The model is part of the job input fingerprint. | Change `RELATIONSHIP_MODEL` and similar settings deliberately. |
| GOT-ENR-8 | Auto approval mistaken for expert certification. | — | Model agreement is not certification; the UI and glossary keep the distinction ([doc 17](17_DOMAIN_AND_TECHNICAL_GLOSSARY.md)). |
| GOT-ENR-9 | Textbook learning items need review although "auto approve" is the default elsewhere. | The v2 spec requires PENDING_REVIEW isolation for generated student content. | **Superseded in Phase 10**: the product owner chose auto-approval. `textbook-approve-learning-items-remote` approves structurally valid items with `approval_method='automatic'`. Keep the review UI (Phase 12) on the backlog to spot-check them. |
| GOT-ENR-10 | After the Prasolov import, every teaching-metadata call failed with OpenAI 400 `Expected at most 1000 enum values … received 1164`. Each failure used up one of the job's 3 attempts. | The taxonomy bridge added textbook concepts and techniques to `knowledge.*`. The generation schema lists every catalog slug as an enum: 885 + 279 = 1,164. | `_enrich_problem` now leaves out textbook-only taxonomy nodes that no contest problem uses (scoped catalog: 641 + 225 = 866). `generation_schema` rejects catalogs over `STRUCTURED_OUTPUT_ENUM_LIMIT` (1000) before any paid call (unit-tested). The 55 jobs that failed with this error had their attempts reset. Any future catalog import must keep the scoped total ≤ 1,000. |

## 6. Credentials, environment and tools (`ENV`)

| ID | Symptom | Cause | Rule / fix |
|---|---|---|---|
| GOT-ENV-1 | LiteLLM reports an invalid key on a collaborator machine. | A shell-exported `OPENAI_API_KEY` from `~/.zshrc` overrode or diverged from the project key. | Project code loads the key **only** from the root `.env` ([scripts/project_env.py](../scripts/project_env.py)). Shell keys are ignored, and `.zshrc` is never edited. Verify with `make check-openai` and `make check-openai CHAT=1` (root §6). |
| GOT-ENV-2 | Environment variables leak into later commands. | `set -a; source .env` in an interactive shell (root §14). | Load env inside Make recipes/subshells only. |
| GOT-ENV-3 | A venv with the wrong Python or broken wheels. | `python3.11 -m venv` (root §1). | Use `uv venv`. |
| GOT-ENV-4 | `pytest` not found in `mathbank-graph/.venv`. | The graph venv has runtime dependencies only. | Run graph tests with `mathbank-rest/.venv/bin/python -m pytest mathbank-graph/tests`. |
| GOT-ENV-5 | The importer test can't load the module (dataclass error). | `importlib` exec without a `sys.modules` entry breaks dataclass resolution. | Register the module in `sys.modules` before `exec_module` ([test_textbook_import.py](../mathbank-db/tests/test_textbook_import.py)). |
| GOT-ENV-6 | Credentials printed in logs or chat. | — | Never print keys or passwords. Checks report presence, equality or validity as booleans or hashes. |
| GOT-ENV-7 | Port conflicts on `make up`. | A stale server is still on the port (root §12). | The service Make targets kill the port owner; `make up` prints every access URL. |

## 7. Web UI, REST and agent (`WEB`)

| ID | Symptom | Cause | Rule / fix |
|---|---|---|---|
| GOT-WEB-1 | React hydration mismatch on `/`. | Server and client rendered different text and whitespace nodes (`{" · "}` siblings) and changing values. | Render deterministic markup; build separators inside one string or element; anything time-dependent goes in client effects. |
| GOT-WEB-2 | `ReferenceError: controller is not defined` / `AbortError` noise. | AbortController scoped inside the effect incorrectly. | Create the controller in the effect scope, abort it in cleanup, and ignore the expected `AbortError`. |
| GOT-WEB-3 | Next.js API route import fails. | Relative import depth miscounted (root §22). | Count the directories, or use the alias paths. |
| GOT-WEB-4 | The browser can't call the ADK server. | `adk api_server` rejects cross-origin requests (root §13). | Allow origins explicitly or proxy through Next.js. |
| GOT-WEB-5 | Agent session storage silently fell back to SQLite. | Missing schema selection. | Isolated `agent_sessions` schema with `SET LOCAL search_path`. Startup fails explicitly instead of falling back. |
| GOT-WEB-6 | Streamed "thinking" exposed private reasoning. | — | Stream public tool names and status only, never private thoughts or raw tool payloads. |
| GOT-WEB-7 | A graph outage looked like "no results". | — | Disclosed as degraded retrieval. Vector and model errors stay errors. |
| GOT-WEB-8 | The ADK agent was not discovered. | Directory/module convention (root §10). | Follow the agent package layout. |
| GOT-WEB-9 | Agent wants to run arbitrary Cypher/SQL. | Spec rule. | The agent is an orchestrator: it calls deterministic tools and owns no state ([pack 22](../math_tutor_new_requirements_copilot_pack_v2_expanded/runtime_extension/22_WHAT_NOT_TO_DO.md)). |
| GOT-WEB-10 | Student payload leaks the worked solution. | The runtime is built from `pedagogy.solution_step`, which holds canonical `step_text`. | `get_runtime` selects metadata columns only; future steps are counts only; the practice endpoint drops `step_text`. The live test asserts no step text of the problem appears in the JSON. |
| GOT-WEB-11 | A student could mark their own step correct. | An outcome endpoint under student auth. | `POST …/outcome` requires `X-Admin-Api-Key` (tutor/evaluator) until Phase 8; `record_step_outcome` rejects actor `STUDENT`. |
| GOT-WEB-12 | A hint request returns `hint_text: null` (historic, Phase 6). | Hint content was Phase 8. | Resolved in Phase 8: the route attaches generated text. `hint_text` null with `hint_source = UNAVAILABLE` now means the model call failed; the level is still recorded. |
| GOT-WEB-13 | Every step route returned 404 over HTTP although the service tests passed. | Step IDs contain `/` (`PRASOLOV_PGV1/STEP-1.1-A-01`); Starlette's `{step_id}` stops at the slash. | Use `{step_id:path}` on every step route; the web proxy sends the ID as one URL-encoded segment. Regression test covers encoded and raw slashes. |
| GOT-WEB-14 | A grader call holds a row lock for seconds / deadlocks with a second tab. | Calling the model inside the `FOR UPDATE` transaction. | Commit the response first, call the model with no lock, then apply the outcome with the saved `state_version`. A 409 → `evaluation_status = PENDING`; a model error → `UNAVAILABLE`. The response is never lost. |
| GOT-WEB-15 | Feedback or a hint gives away the step. | The model sees the canonical step. | A 7-word n-gram leak guard (ignoring n-grams the student already has). Leaking FAILED feedback is replaced (`feedback_redacted`); a leaking hint (levels 1–3) gets one stricter retry, then a fixed template. Level 4 is near-explicit by design; level 5 is the reveal. |
| GOT-WEB-16 | A changed hint prompt keeps serving old text. | Hints are cached in `pedagogy.step_hint`. | The cache key includes `prompt_version`; bump `HINT_PROMPT_VERSION` in `step_tutor.py` to regenerate. |
| GOT-WEB-17 | "Solve step by step" link shows on a problem without steps. | The link uses a code-prefix heuristic (`hasStepSolution`: `PRASOLOV_`). | The page handles it: start returns 409 and the page says there is no step solution yet. Replace with a flag from the API when more sources get steps. |
| GOT-WEB-18 | Playwright clicks time out on the workspace in the shared VS Code browser ("waiting for element to be stable"). | The background tab throttles `requestAnimationFrame`. | Not an app bug: requests show no loop. Use `click({force:true})` or a DOM `click()` when scripting. |

## 8. Tests and verification (`TEST`)

| ID | Symptom | Cause | Rule / fix |
|---|---|---|---|
| GOT-TEST-1 | A "fix" verified against a convenient proxy. | — | Verify the actual acceptance criterion: reconciliation tables, safety SQL returning 0, graph `--status` reconciling 13/13. |
| GOT-TEST-2 | Live fixtures permanently changed real metadata. | — | Live SQL tests use rolled-back transactions; no persisted fixture or audit trace. |
| GOT-TEST-3 | Idempotency assumed. | — | Re-run every import or projection and confirm new=0/upd=0 (import) or pruned 0 with all types reconciled (graph). |
| GOT-TEST-4 | Paid calls during tests. | — | Offline fixture tests by default; paid checks are explicit (`make check-openai CHAT=1`). |
| GOT-TEST-6 | A routing bug passed the live tests. | The live tests called service functions directly, bypassing HTTP routing. | Route-level tests (TestClient with fakes) for every new path, especially with unusual IDs. |
| GOT-TEST-5 | The live runtime test can't run on the default suite. | It writes to Neon (in a rolled-back transaction). | Opt in with `MATHBANK_LIVE_STEP_RUNTIME_TEST=1`; afterwards confirm the runtime tables are still 0 rows. |

## 9. Vectors and step retrieval (`VEC`)

| ID | Symptom | Cause | Rule / fix |
|---|---|---|---|
| GOT-VEC-1 | Can't store a solution step or learning item in `search.representation`. | `source_entity_id` is a `uuid`, but pedagogy IDs are text (`STEP-…`, `LI-…`). | Use a deterministic uuid5 surrogate (`surrogate_id(entity_type, id)`, fixed namespace in [embed_textbook_steps.py](../mathbank-db/etl/embed_textbook_steps.py)). The real text ID lives in the new FK column `search.chunk.solution_step_id` / `learning_item_id` (migration 011), and filters always use those columns, never the surrogate. |
| GOT-VEC-2 | A skill-filtered semantic search returns fewer rows than exist, or none. | The global HNSW index (`embedding::vector(1536)` expression) finds the approximate top-N **first**; the structured filter then removes most of them. | Apply hard filters in an `eligible` CTE first, then compute the **exact** distance `e.embedding <=> CAST(:qv AS vector)` (deliberately not the indexed expression) over that subset ([step_search.py](../mathbank-rest/src/mathbank_rest/db/step_search.py)). Filtered subsets are small, so the exact scan is cheap. |
| GOT-VEC-3 | A hint search reveals the next step of the current problem. | Step text is solution content. | `search_solution_steps` drops `step_text` unless `include_step_text=True`. Callers pass `exclude_problem_id` for the problem being solved. |
| GOT-VEC-4 | An unpublished learning item appears in recovery search. | A stale representation or embedding outlived a review change. | The projector only stages APPROVED + `student_visible` + `no_proof` items and supersedes the rest. Retrieval **also** joins the live `pedagogy.learning_item` row with the same predicate (defence in depth); both are unit-tested. |
| GOT-VEC-5 | Step embedding took 16.5 minutes for 7,814 short chunks (measured). | `embed_corpus.embed_pending_chunks` inserts one embedding row per round trip to Neon. | Expected; run it in the background (`make -C mathbank-db textbook-vector-remote`). It is resumable: a re-run embeds only chunks still missing an embedding. Batch inserts are a possible improvement. |
| GOT-VEC-6 | Metadata changes (hint level, technique) re-bill embeddings. | They would if metadata were part of the content hash. | `content_hash` covers the rendered text only. Metadata-only changes update `representation.metadata` and chunk filter columns in place (unit-tested). |
| GOT-VEC-7 | `0` learning-item vectors after the backfill. | All 11,186 items are `PENDING_REVIEW` (GOT-ENR-9). | Expected before approval. After the Phase 10 auto-approval, `textbook-vector-remote` embeds only the newly eligible items (backfill takes hours at one row per round trip, GOT-VEC-5); then re-run `textbook-graph-remote`. |
| GOT-VEC-8 | The step backfill also embeds contest chunks still waiting to be embedded. | `embed_pending_chunks` selects every chunk without an embedding. | Pass `representation_kinds` (the step projector does) to limit it to pedagogy kinds. |


## 10. Gap diagnosis (`DIAG`)

| ID | Symptom | Cause | Rule / fix |
|---|---|---|---|
| GOT-DIAG-1 | Prerequisite hypotheses never come from the skill graph for Prasolov problems. | Prasolov skills have no skill-level `PREREQUISITE_OF` edges; only the step DAG and concept relations carry order. | Use the step `DEPENDS_ON` DAG inside the attempt (`from_step_id` is the prerequisite), plus approved `knowledge.concept_relation` prerequisites, as the evidence ([step_diagnosis.py](../mathbank-rest/src/mathbank_rest/step_diagnosis.py)). |
| GOT-DIAG-2 | Re-diagnosing right after a failure creates a duplicate diagnosis. | A FAILED step is immediately re-presented as `RETRY_PRESENTED`, so a fingerprint that includes state changes without new evidence. | `evidence_fingerprint` excludes step state and hashes only tries, help, grader verdict, history and predecessor evidence. Same fingerprint → the existing row is returned (`reused=true`, unique key on attempt, step and fingerprint). |
| GOT-DIAG-3 | A new hypothesis is immediately marked CONFIRMED by the failure that created it. | Status updates and auto-diagnosis run on the same outcome. | `record_step_outcome` updates open gaps **before** creating the new diagnosis. Hypotheses are never overwritten; a re-diagnosis is a new row. |
| GOT-DIAG-4 | An error in diagnosis would roll back a grade. | The hook runs inside the outcome transaction. | `_diagnosis_hooks` runs in a savepoint (`conn.begin_nested()`), logs the error, and leaves the outcome committed. |
| GOT-DIAG-5 | Inserting `GAP_DIAGNOSED` events fails with a CHECK violation on an old database. | The `learner.event` type CHECK from 012 didn't list the new types. | Migration 014 drops and re-adds `event_event_type_check`. Apply `migrate-gap-diagnosis-remote` before deploying the Phase 9 REST code. |
| GOT-DIAG-6 | The student diagnose button can't conflict with a concurrent step submission (no 409). | Diagnosis only reads runtime state and writes diagnosis tables and events. | It locks the attempt row for ordering but **does not** bump `state_version` or change `current_mode`. Entering RECOVERY mode from a `RECOVERY_DETOUR` belongs to Phase 10. Students never see confidences, failure modes or evidence; admins use the admin-key routes. |

## 11. Recovery detours (`REC`)

| ID | Symptom | Cause | Rule / fix |
|---|---|---|---|
| GOT-REC-1 | `recovery_plan_item_ordinal_check` violation when an adapted item is inserted. | Inserting before the RETURN item shifts later ordinals with `ordinal + 1`, and Postgres checks rows mid-update, so a temporary collision or a negative value appears. | Shift in two passes: `+100001`, then `-100000`. Never shift into negative ordinals (the CHECK is `ordinal >= 1`). |
| GOT-REC-2 | A subproblem question shows the expected result. | Some imported `SUBPROBLEM_FIRST_MOVE` / `SUBPROBLEM_NEXT_INTERMEDIATE` items put the seed answer into the question text. | Source-data issue; tracked in NYI-P10. Prefer MCQs at those stages when alternatives exist; a reviewer should fix the text. |
| GOT-REC-3 | A worked example, probe or item just says "Solution is similar to … heading a)". | 118 learning items and 204 steps are cross-reference stubs, not standalone content. | `CROSS_REFERENCE_STUB_RE` (in `step_runtime.py`) plus a 25-character minimum filter them out of `_candidates`, `_worked_example` and `find_probes`. The regex uses Postgres `\m`/`\M` and `[)]` because `\)` broke under psql `\set`. A live test asserts stubs are never recovery material. |
| GOT-REC-4 | Recovery reuses the problem the student is stuck on. | Same-skill items are often anchored to the origin problem. | Candidates, worked examples and probes exclude the origin problem. |
| GOT-REC-5 | A gap stays CONFIRMED after a detour. | The plan ended `EXHAUSTED` (ran out of items before the mastery policy was met). | By design: only `COMPLETED` (2 first-try successes + transfer) resolves a gap. The student still returns to the step. |
| GOT-REC-6 | The student isn't sent into recovery automatically. | The detour is **offered** on the diagnosis card, not forced. | By design. `RECOVERY_DETOUR` only changes the call to action; `POST …/recovery-plans` starts it. |
| GOT-REC-7 | AI re-ranking changes nothing. | It is off unless `DIAGNOSIS_LLM_RERANK` is truthy, and it can only reorder rules-v1 hypotheses. | Set `DIAGNOSIS_LLM_RERANK=1` (model: `DIAGNOSIS_RERANK_MODEL` → `STEP_TUTOR_MODEL` → `gpt-4.1-mini`). A failed call keeps the rules order silently; the result is stored in `gap_diagnosis.ai_rerank`. |
| GOT-REC-8 | "Correct.Correct." in recovery feedback. | The grader feedback already starts with "Correct.". | The UI skips feedback that equals the verdict text. |
| GOT-REC-9 | A typed answer carries over to the next recovery item. | React reused the same component instance. | Key `RecoveryItem` by `${item_id}:${tries}` instead of resetting state in an effect. |
| GOT-REC-10 | Older diagnoses still show practice-step probes, not learning items. | Diagnoses are reused by fingerprint, and probes are stored when the diagnosis is made. | Expected. New evidence (or a new diagnosis) picks up learning-item probes. |
| GOT-REC-11 | `operator does not exist: text = uuid` comparing learning-item IDs. | `learning_item_id` is text, not uuid. | Compare with `learning_item_id::text = ANY(CAST(:ids AS text[]))`. |
| GOT-REC-12 | `/resume` returns 409 "finish the detour first". | The plan (or a branch) is still ACTIVE/SUSPENDED. | Use `/abort` to leave early; `/resume` is for COMPLETED or EXHAUSTED plans. |

## 12. Tutor walkthrough, transcripts and browser regression (`WALK`)

Found during the Power-of-a-Point student walkthrough (2026-10-05) and the Playwright suite ([23](23_E2E_REGRESSION_SUITE.md)).

| ID | Symptom | Cause | Fix / rule |
|---|---|---|---|
| GOT-WALK-1 | Tutor chat never returned Prasolov problems; `search_problems` timed out. | The hybrid graph leg expanded every reviewed Problem→tag link, then ran a per-pair seed `OPTIONAL MATCH` (~36 s on Aura), beyond the agent's 15 s httpx timeout. | **Fixed.** `hybrid_search.graph_candidates` resolves candidate tags first (`CALL { name match UNION ALL seed tags }`), then expands Problem→tag; graph leg ~2 s, full hybrid ~2.5 s. Agent timeout raised to 30 s. Keep graph Cypher tag-first. |
| GOT-WALK-2 | "power of a point" ranks an unrelated projective-transformation problem first. | Only **1 of 1,697** Prasolov problems carries `TECH.GEO.POWER_OF_A_POINT`; the real ones are under subconcept `GEO.C03.S10` "radical axis". | Data gap (NYI-WALK-1). The agent docstring tells the model to enrich the query ("power of a point radical axis"). |
| GOT-WALK-3 | Conversation list times were off by the local UTC offset. | ADK stores `timestamp without time zone` holding UTC; the browser parsed them as local time. | **Fixed.** `agent_transcripts._iso_utc()` emits explicit `+00:00`. Treat every `agent_sessions` timestamp as naive UTC. |
| GOT-WALK-4 | Worked example said "Skill inferred from ordered solution steps." | 14 SKILL taxonomy nodes carry import-provenance text as `description`. | **Fixed.** `step_recovery._student_description()` hides provenance text (`_PROVENANCE_DESCRIPTION_RE`). Never show raw taxonomy descriptions without that filter. |
| GOT-WALK-5 | Recovery worked example / practice items came from an unrelated chapter (e.g. CH28 inversion for a CH03 radical-axis step). | Candidates were ranked only by skill match, then random. | **Fixed.** `_worked_example` and `_candidates` rank by `topic_closeness` (same subconcept 2, same concept 1) via `pedagogy.problem_enrichment`. |
| GOT-WALK-6 | MCQ "Pick the first move" correct option is guessable. | Distractors are generic templates, stylistically different from the true option. | Open (NYI-WALK-2). Needs generated, topic-specific distractors with validation. |
| GOT-WALK-7 | Item text says "For source Problem 17.30" and shows `◦`/`∗` glyphs. | Imported Prasolov text keeps book numbering and PDF glyphs instead of LaTeX. | Open (NYI-WALK-3). Normalise at presentation or re-canonicalise; do not rewrite raw source rows. |
| GOT-WALK-8 | `get_problem_learning_context` takes ~28 s. | Several sequential Postgres + Aura reads for one problem. | Open (NYI-WALK-4). Agent timeout is 30 s, so it is near the limit; cache or parallelise. |
| GOT-WALK-9 | Step label reads "Attempt 2" right after the first submit. | Label counts the next attempt, not the submitted one. | Cosmetic, open. |
| GOT-WALK-10 | A student cannot see an anonymous chat after signing in. | By design: links are only created for sessions whose ADK `user_id` is that student; anonymous sessions stay unlinked ([22](22_AGENT_SESSION_TRANSCRIPTS.md) TRN-6/7). | Expected; admin list shows `unlinked_count`. |
| GOT-WALK-11 | Admin conversations response has no `sessions` key. | The REST shape is `{linked[], unlinked_count}`. | Use `linked`. |
| GOT-WALK-12 | Hydration error from server-rendered "signed in" state. | Reading cookies/learner during SSR differs from the client. | `AppShell` fetches `/api/rest/learner/me` in `useEffect` with initial `null`. Keep auth-dependent UI client-only. |
| GOT-WALK-13 | Playwright specs picked up by `node --test`, or vice versa. | Mixed globs. | Unit tests are `tests/*.test.mjs` (node); browser specs are `e2e/*.spec.mjs` (Playwright `testMatch`). Keep them separate. |
| GOT-WALK-14 | `@llm` specs cost money / fail without a key. | They call the agent and the step grader. | Skipped unless `E2E_LLM=1` (`grepInvert`). Default `make -C mathbank-web e2e` is free. |

## 13. Admin textbook corpus dashboard and coverage (`ATB`)

Found while building [24](24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md) (2026-10-05).

| ID | Symptom | Cause | Fix / rule |
|---|---|---|---|
| GOT-ATB-1 | "Postgres has fewer rows than the CSVs." | Source rows are summed across both packages before de-duplication. Taxonomy ids repeat across packages (544→501); (chapter, section) keys repeat (239→214); 1 duplicate problem; 2 orphan solutions; 163 ambiguous step dependencies. | Expected. Compare against `ingest.import_conflict` and the reconciliation, not raw `wc -l`. The matrix note explains each row. |
| GOT-ATB-2 | Taxonomy graph count looked like 0 when matching on `taxonomy_node_id`. | Neo4j Concept/Skill/Technique nodes are keyed by the **core uuid** (`taxonomy_node.concept_id`/`skill_id`/`technique_id`), not the textbook taxonomy id. | Match `n.canonical_id IN` the linked core uuids. |
| GOT-ATB-3 | Solution vector count was 0 for the book. | Solution chunks carry `solution_id`, not `problem_id`. | Join `search.chunk.solution_id` → `pedagogy.solution_source_ref` for the book. |
| GOT-ATB-4 | Diagram image route returned 404 / 422 for every diagram. | `pedagogy.diagram.diagram_id` is **text** (`{book}/{source_diagram_id}`), not a uuid, and it contains `/`. | Address images by `source_diagram_id` (`^[A-Za-z0-9_.-]+$`) plus `book`. Never put `diagram_id` in a URL path. |
| GOT-ATB-5 | Deleting `math_tutor_new_requirements_copilot_pack_v2_expanded/` would break every diagram. | All 250 `local_path` values point inside the pack's `GEOMETRY-TEXTBOOKS/*/diagrams/`. | **Blocker:** copy the assets to a durable location and update `local_path` first (NYI-ATB-3). |
| GOT-ATB-6 | Taxonomy nodes show a `GAP` in the matrix. | Taxonomy nodes were never embedded. The old count also counted `TAXONOMY_NODE` representations across every book, embedded or not. | Fixed 2026-10-05: 501/501 embedded. The count is book-scoped and counts embedded chunks only. |
| GOT-ATB-10 | Taxonomy `description` values are boilerplate (`Skill from existing enrichment.`, `Method/subtopic from Chapter N.` …). | The CSV descriptions only record provenance. Embedding them makes every skill look alike. | `BOILERPLATE_DESCRIPTION` in `embed_textbook_steps.py` drops all six patterns; meaning comes from the name, parent path and edge neighbours. |
| GOT-ATB-11 | Changing the rendered text after `build` leaves `SUPERSEDED` representations whose chunks were never embedded. | `embed_corpus.py backfill` without a kind/paper filter selects chunks lacking an embedding regardless of representation status, so it would pay to embed dead text. | Run `build` and inspect texts **before** `backfill`. After a text change, delete never-embedded `SUPERSEDED` `TAXONOMY_NODE` representations (cascade removes their chunks), as was done for 45 drafts on 2026-10-05. |
| GOT-ATB-12 | `MATCH (li:LearningItem)-->(:Concept)` returns 2 rows per item. | `Subconcept` nodes also carry the `Concept` label, so both `TARGETS_CONCEPT` and `TARGETS_SUBCONCEPT` match an untyped pattern. | Always name the relationship type, as the dashboard does (`[:TARGETS_CONCEPT]->(:Concept)`), or use `count(DISTINCT li)`. |
| GOT-ATB-13 | The concept reached through `DERIVED_FROM -> Problem -[:TESTS]->` is not the item's target. | A transformation can focus on one sub-idea of a multi-concept source problem. | Select practice items by `TARGETS_*` (or `target_*_node_id` in PG), never by the source problem's concepts. |
| GOT-ATB-14 | `project_textbook_steps.py` fails with `wrote N/M; graph endpoints are missing`. | The new edges `MATCH` existing `Concept`/`Subconcept` nodes, which only `project_from_postgres.py --pedagogy` creates (and labels `Subconcept`). | Run `make -C mathbank-db textbook-graph-remote` (both projectors in order) on a fresh graph. The partial-write check is intentional. |
| GOT-ATB-15 | Concept search finds nothing for a node that clearly exists. | Taxonomy chunks have no `skill/subconcept_node_id` for TECHNIQUE and DOMAIN nodes, and `source_entity_id` is a uuid5 surrogate. | Key taxonomy retrieval on `chunk.metadata->>'taxonomy_node_id'` joined to `pedagogy.taxonomy_node`, as `step_search` does. |
| GOT-ATB-16 | `search_concepts` says a technique has 6 problems but `/v1/techniques/{slug}/problems` lists 1. | `problem_count`/`example_problem_codes` come from published solution steps (approved `solution_step_technique` links for techniques); the slug routes list legacy corpus tags (`core.problem_*`). | Use `example_problem_codes` for practice; the agent instruction says so. Do not "fix" one count to match the other. |
| GOT-ATB-17 | "power of a point" also returns *Regular polygons* lexically. | Taxonomy texts list neighbouring technique names ("Techniques: … Power of a point …"), so lexical matches neighbours. | Expected with RRF; filter by `node_types` when only one kind is wanted. Richer texts are NYI-ATB-8. |
| GOT-ATB-7 | The `learning_item` columns are not `item_type` / `approval_status`. | The v2 schema names are `transformation_type` and `review_status`. | Use the v2 names in any new query. |
| GOT-ATB-8 | Cypher deprecation warnings flood the REST log. | The Aura driver emits notifications for `labels()`-style queries. | Query with `notifications_min_severity="OFF"` in scripts; the REST helpers swallow the warnings. |
| GOT-ATB-9 | Browser shows `ERR_ABORTED` for dashboard fetches in dev. | React StrictMode mounts effects twice, and the first fetch is aborted by design. | Harmless. Data loads from the second fetch. |

## 14. Geometry runtime completion: techniques, outbox, agent tools, admin import UI (`GEO`)

Found while delivering [26](26_GEOMETRY_RUNTIME_COMPLETION_PLAN.md) WP1–WP4 (2026-10-06).

| ID | Symptom | Cause | Fix / rule |
|---|---|---|---|
| GOT-GEO-1 | "Step → Technique = 0" in the coverage matrix. | The Prasolov CSVs tag techniques per **problem** only. | Derived tags in `pedagogy.solution_step_technique` (migration 017) with per-row `source_type`/`confidence`. Never copy problem techniques onto every step (most steps are setup/algebra) and do not infer from the step's subconcept (~12k noisy tags). |
| GOT-GEO-2 | Re-running the technique derivation would erase an admin correction. | Naive delete-and-reinsert. | Rows with `source_type = 'HUMAN'` or `review_status = 'REJECTED'` are never overwritten or pruned; only stale RULE rows of the current scope are pruned. |
| GOT-GEO-3 | `FOR UPDATE is not allowed with GROUP BY clause`. | Locking an aggregate query. | Lock the base row, aggregate in a `LATERAL` subquery. |
| GOT-GEO-4 | An outbox consumer double-counted analytics after a crash. | Side effect and "consumed" marker in separate transactions. | Write the side effect and `pipeline.outbox_consumption (outbox_event_id, consumer)` in **one** transaction; replay is a no-op. |
| GOT-GEO-5 | Many identical "reproject" rows pile up. | Each step edit raises a projection request. | Partial unique index: one `PENDING` request per (target, scope_type, scope_id); inserts use `ON CONFLICT … WHERE status = 'PENDING' DO NOTHING`. |
| GOT-GEO-6 | Draining the projection queue spent money. | Embedding targets call the paid embeddings API. | `projection-queue-run-remote` only runs the free graph projector and **lists** embedding targets; paid runs need `projection-queue-run-paid-remote` (`--allow-paid`). |
| GOT-GEO-7 | The student REST token showed up in `agent_sessions`. | Token stored in ordinary session state. | Pass it as ADK **temp** state (`temp:student_token`), which ADK strips before persisting; anonymous chats get `SIGN_IN_REQUIRED`. |
| GOT-GEO-8 | Agent retries created duplicate step submissions. | Model re-issues a tool call. | Tools send the server `state_version` and an idempotency key derived from the ADK function-call id; REST returns the original result. |
| GOT-GEO-9 | Clicking "Accept incoming" on a conflict changed nothing in the data. | By design: conflict decisions are **recorded**, not executed. | The decision is applied by the next package re-import or by a DAG edit; the UI says so. |
| GOT-GEO-10 | An admin step edit was reverted by a re-import. | Importer upserted every row. | Importer skips steps with `admin_edited_at` and dependency rows with `approval_method = 'human'` (migration 019). |
| GOT-GEO-11 | A rejected dependency still appeared in Neo4j. | Projection only merges. | `project_textbook_steps.py` excludes `REJECTED` edges and prunes them on the next run; rejected learning items are pruned the same way (`LEARNING_ITEM_WITHDRAWN` → projection request). |
| GOT-GEO-12 | Step routes 404 for some ids. | Step ids contain `/` (all) and `#` (167, e.g. `…-A-01#2`). | URL-encode the id (`encodeURIComponent`) and declare the FastAPI path as `{step_id:path}`; the web proxy regex allows `/` and `#`. |
| GOT-GEO-13 | Adding a `DEPENDS_ON` edge returned 409. | It would close a cycle (recursive-CTE check). | Expected; pick another edge or retype it. Only non-rejected `DEPENDS_ON` edges within the same problem are traversed; other edge types are not cycle-checked. |
| GOT-GEO-14 | Audit trail rows came back in random order in tests. | Rows written in one transaction share `now()`. | Order by `created_at, action_id`. |
| GOT-GEO-15 | A route-registration test failed though the route worked. | This FastAPI version does not flatten included routers in `app.routes`. | Assert against `app.openapi()["paths"]` (strip the `:path` converter). |
| GOT-GEO-16 | Reconciliation "embedding" numbers looked wrong. | Counting `search.embedding` rows of every model. | Use only the ACTIVE `search.embedding_model`; profile version comes from `search.preprocessing_profile`, not chunk metadata. |
| GOT-GEO-17 | Non-Prasolov problems show no steps/techniques/DAG. | Only the Prasolov packages are decomposed. | Intended NULL policy; runtime population plan in doc 26 §3. |
| GOT-GEO-18 | `ingest.admin_review_action` UPDATE/DELETE fails. | Append-only trigger. | Correct by appending a new action; never edit audit rows. |

## 15. Fluid widgets, live classroom and student add-ons (`FW`, `LIVE`, `UXA`)

Found while delivering [27](27_FLUID_WIDGET_LAYER.md), [28](28_DISTRIBUTED_LIVE_PLATFORM.md) and [29](29_STUDENT_INPUT_ADDONS.md) (2026-10-06).

| ID | Symptom | Cause | Fix / rule |
|---|---|---|---|
| GOT-FW-1 | A widget spec with a `template` key was rejected (422). | `template` is in `FORBIDDEN_KEYS` (string templates could smuggle markup). | Reference templates by `template_id`; widget generation resolves them server-side. |
| GOT-FW-2 | One rejected live command aborted the whole request transaction. | A failed SQL statement poisons the transaction. | `execute_command` runs each command in a **savepoint**; a rejection rolls back the savepoint but still stores a `REJECTED` `live.command_receipt`, so retries stay idempotent. |
| GOT-FW-3 | Changes to `mathbank-widgets` did not show in web/live. | The apps use a **copy** in `node_modules/mathbank-widgets`, not a live link. | Run `make -C mathbank-web sync-widgets` / `make -C mathbank-live sync-widgets` (`start`/`dev` do it automatically), then restart. |
| GOT-FW-4 | Hydration error: "server rendered HTML didn't match the client" around the 🎤 button. | `MicButton` checked `window.MediaRecorder` during render. | Detect browser features in `useEffect` after mount; render the same markup on server and client. |
| GOT-FW-5 | Inline code in tutor answers turned into a block, or KaTeX inside code broke. | Overriding the Markdown `code` renderer affects inline code too. | Override `pre` (the block wrapper), not `code`. |
| GOT-FW-6 | Pack poll names (`PREPLANNED`, `AGENT_CREATED`) don't match the database. | The DB uses `source_type` PRECOMPILED / CORPUS_DERIVED / LIVE_AGENT_CREATED / INSTRUCTOR_CREATED. | Map the pack names onto these values; do not add duplicate enum values. |
| GOT-FW-7 | Creating an activity of type `POLL` returned 500. | An unknown `activity_type` hit the CHECK constraint. | Validated up front: 422 `ACTIVITY_INVALID`; the type is `LIVE_POLL`. |
| GOT-FW-8 | A student could not preview a widget (`/v1/widgets/generate` 401). | The route required the admin key. | It is now `staff_or_student`; storing/reviewing specs is still admin-only. |
| GOT-FW-9 | An edit to a published plan failed with `PLAN_IMMUTABLE` or a trigger error. | Published plans are immutable (`authoring.guard_published_plan`/`guard_published_topic`). | `POST /v1/authoring/presentation-plans/{id}/new-version`, edit the DRAFT, then publish (which supersedes the old version). Purges need `SET authoring.allow_purge = 'on'`. |
| GOT-LIVE-1 | The pack references upstream zips that are not in the repo. | Only the handoff/fluid Markdown packs were delivered. | Minimal compatible models were implemented; re-audit when the upstream packs arrive (NYI-FW-9, NYI-LIVE-9). |
| GOT-LIVE-2 | Expecting two independent MFE builds. | `mathbank-live` is one Next app with `/s/[sid]` (student) and `/i/[sid]` (instructor). | Separate deployable from `mathbank-web`; module federation not adopted. |
| GOT-LIVE-3 | Next dev HMR stopped working once Socket.IO was mounted. | Socket.IO destroyed upgrade requests that it did not own. | `new Server(httpServer, { destroyUpgrade: false })` in `server.mjs`. |
| GOT-LIVE-4 | `next build` with `output: "standalone"` produced a server without sockets. | Standalone output generates its own server and ignores `server.mjs`. | Do not use standalone; run `npm start` (custom server). |
| GOT-LIVE-5 | The browser bundle failed on `node:crypto`. | A client component imported `lib/gateway.mjs`. | Clients import only `lib/events.mjs` (pure); the gateway is server-only. |
| GOT-LIVE-6 | Logged in on :5173 but also logged in on :5174 (or logged out of both). | Cookies are host-scoped, not port-scoped. | Expected: `mb_student_token` / `mb_admin_session` are shared by web and live on localhost. Use different hosts for isolation. |
| GOT-LIVE-7 | A student's own question did not appear in their feed. | `QUESTION_ASK` events have audience INSTRUCTOR and are not echoed to the student. | The classroom echoes the question locally; do not broaden the audience. |
| GOT-LIVE-8 | AI action returned 409 `STALE_VERSION` / `AI_NOT_IN_CONTROL`. | `AI_TUTOR` must send `expected_session_version`; during a takeover or lock AI messages are blocked. | Re-read `/v1/tutor/sessions/{sid}/context` and re-propose; never retry blindly. |
| GOT-LIVE-9 | Event names in the fluid pack (`SCENE_CHANGED`) differ from the live ones (`scene.changed`). | The packs disagree. | Dotted lowercase from the distributed pack 04 is canonical. |
| GOT-LIVE-10 | Events arrive up to ~0.7 s late. | The gateway polls `/events?after=` every 700 ms (no NATS/Redis yet). | Acceptable for a classroom; the event bus is NYI-LIVE-1. Clients dedupe by `sequence`. |
| GOT-LIVE-11 | Playwright `getByText("Poll")` matched several elements. | Labels repeat across the console. | Use `exact: true` or `data-testid`. |
| GOT-UXA-1 | STT returned 400 / empty. | ElevenLabs expects the multipart field **`file`** (not `audio`). | `MicButton` and `createVoiceHandlers` use `file`. |
| GOT-UXA-2 | `ELEVEN_API_KEY` disappeared from `mathbank-web/.env` after `make sync-env`. | `sync-env` rewrote service env files from a fixed key list. | `sync-env.sh` now also runs the Eleven and live syncs; or run `make sync-eleven-key`. Restart web/live after key changes. |
| GOT-UXA-3 | `check-eleven` / voice cost money unexpectedly. | TTS and STT are billed; `/v1/models` is free. | `check-eleven` is free by default; `TTS=1` is the explicit paid opt-in. Playwright mocks TTS/STT. |
| GOT-UXA-4 | The ✨ button returned the deterministic result. | Not logged in, model failure, or the model's output failed validation. | Read `engine` and `warnings` in the response; this fallback is intended. |
| GOT-UXA-5 | The terminal showed `Bearer ******` in copied commands. | The terminal masks secrets. | Not a bug in the scripts; never paste real keys into docs. |

---

## Change log

- 2026-10-06: Added GOT-ATB-15…17 (concept search over taxonomy vectors).
- 2026-10-06: Added §15 (GOT-FW-1…9, GOT-LIVE-1…11, GOT-UXA-1…5) for the fluid widget layer, the `mathbank-live` socket deployable and the student input add-ons.

- 2026-10-06 (Doc 26 WP1–WP4): Added GOT-GEO-1…18.
- 2026-10-05 (Learning-item concept edges): Added GOT-ATB-12…14.
- 2026-10-05 (Taxonomy embeddings): GOT-ATB-6 resolved; added GOT-ATB-10 (boilerplate descriptions) and GOT-ATB-11 (superseded unembedded drafts).
- 2026-10-05 (Admin corpus dashboard): Added the `ATB` section (GOT-ATB-1…9): summed-source counts, core-uuid graph identity, solution chunk join, text diagram ids, diagrams inside the pack, missing taxonomy vectors, v2 column names, Cypher notifications, StrictMode aborts.

- 2026-10-05 (Walkthrough / transcripts / e2e): Added the `WALK` section (GOT-WALK-1…14): tag-first graph Cypher, POWER_OF_A_POINT tagging gap, naive-UTC ADK timestamps, provenance description leak, topic-aware examples, template MCQ distractors, book references and PDF glyphs, slow learning-context tool, attempt label, anonymous sessions, admin response shape, client-only auth UI, test globs, paid `@llm` specs.

- 2026-10-05 (Phase 10): Added the `REC` section (GOT-REC-1…12): ordinal shift, seed leaks, cross-reference stubs, origin exclusion, EXHAUSTED semantics, offered detour, opt-in AI re-rank, UI duplication/state carry-over, reused probes, text IDs, resume vs abort. GOT-ENR-9 and GOT-VEC-7 updated for auto-approval.

- 2026-10-05 (Phase 9): Added the `DIAG` section (GOT-DIAG-1…6): DAG as prerequisite source, state-free fingerprint, update-before-diagnose order, savepoint, event CHECK replacement, no `state_version` bump.

- 2026-10-05 (Phases 7–8): Added GOT-WEB-13…18 (slash step IDs, model call outside the lock, leak guard, hint cache version, step-link heuristic, background-tab clicks) and GOT-TEST-6; GOT-WEB-12 marked resolved.

- 2026-10-05 (Phase 6): Added GOT-PG-18…21 (attempt collision, idempotency store, append-only events, concurrency), GOT-WEB-10…12 (no step-text leak, no self-grading, hint content pending) and GOT-TEST-5. Corrected GOT-VEC-5 to the measured 16.5 minutes.

- 2026-10-05 (Phase 5): Added the `VEC` section (GOT-VEC-1…8): uuid surrogates, filtered-ANN recall loss, step-text leakage, defence-in-depth eligibility, slow per-row inserts, metadata-only updates, learning items with no vectors, and scoped pending-chunk embedding.

- 2026-10-05: Added GOT-ENR-10 (enum budget after taxonomy import), GOT-RUN-12 (watcher was the deadlock victim) and GOT-RUN-13 (batch exit code vs. per-paper failures).
- 2026-10-05: Created. It consolidates root GOTCHAS.md §1–22 and its topical sections with the Prasolov import (Phases 1–3) and graph projection (Phase 4) pitfalls.
