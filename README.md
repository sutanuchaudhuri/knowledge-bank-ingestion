# MathBank Platform

A competition-math corpus (AMC/AIME/HMMT/SMT/PUMaC/CHMMC/CMM/Math Prize for
Girls) with hybrid (semantic + lexical) RAG search, a knowledge graph, an
agentic tutor, and a student-profile web UI — built from five independent
services:

| Service | What it is | Port |
|---|---|---|
| `mathbank-db` | Postgres 16 + pgvector — `core.*`/`knowledge.*`/`search.*`/`learner.*`/`pipeline.*` schema + ETL/embedding pipelines | 5433 (local, **optional** — see below) |
| `mathbank-graph` | Neo4j — knowledge graph projection (`TESTS`, `USES_TECHNIQUE`, `MASTERED`, ...) | 7474/7687 (local, **optional** — see below) |
| `mathbank-rest` | FastAPI — the only service that talks to Postgres/Neo4j directly; hybrid search, learner auth/mastery, admin pipeline endpoints | 8000 |
| `mathbank-agent` | Google ADK agent (OpenAI via LiteLLM) — calls `mathbank-rest` as tools, never touches the DBs directly | 8001 |
| `mathbank-web` | Next.js — student chat/login/profile UI + admin ingestion UI, proxies to `mathbank-rest`/`mathbank-agent`/Neo4j server-side | 5173 |
| `mathbank-live` | Next.js + Socket.IO — **separately deployable** realtime live classroom (instructor console + student classroom); relays the `mathbank-rest` live event log | 5174 |
| `mathbank-widgets` | Shared React package (not a service) — WidgetHost renderer, MathComposer (LaTeX), ElevenLabs voice controls; copied into web and live | — |

Production/demo data lives on managed cloud services (Neon Postgres + Neo4j
AuraDB) — see [DATABASES.md](DATABASES.md) for the full local-vs-remote
picture and the end-to-end corpus pipeline (crawl → classify → ETL → graph →
vector embeddings). See [GOTCHAS.md](GOTCHAS.md) for environment
troubleshooting accumulated across this project's history.

For the source-derived implementation reference, see
[requirements/reference/](requirements/reference/): PostgreSQL DDL/DML,
Neo4j projection schema, FastAPI/Swagger OpenAPI, web proxy routes and
agent-session ownership.

## Do I need local Postgres/Neo4j at all?

**Usually no.** `mathbank-db` and `mathbank-graph` are literally the names
of the *schema/ETL* projects, not something the other three services talk
to at runtime — `mathbank-rest` and `mathbank-web` each read their own
`.env` and connect **directly** to whatever `POSTGRES_HOST`/`NEO4J_URI`
point at. After `make sync-env` (the common path — see below), those point
at the shared remote **Neon Postgres + Neo4j AuraDB**, so a local Postgres
16 / Neo4j install is not required to run the app at all.

Local Postgres/Neo4j (via Homebrew, on the external APFS drive) are only
needed if you're doing **local-only** corpus pipeline work (ingestion
scripts without `-remote`, schema changes before pushing them to Neon,
etc.) — see `mathbank-db/README.md` / `mathbank-graph/README.md`.

Because of this, `make up`, `make status` and `make down` cover only
rest/agent/web/live and never touch local Postgres/Neo4j. `make up` is the
same as `make up-app`. For a fully local stack, run
`make -C mathbank-db install && make -C mathbank-graph install` (then
`make -C mathbank-db init start create-db` / `make -C mathbank-graph setup`),
and use `make up-local-db`, `make access-local` and `make down-local-db`.

## Quick start

### New collaborator with a shared `.env`

If someone on the team sent you a consolidated `.env` over a **secure
channel** (it contains live database/API credentials — never over email or
chat that isn't end-to-end secured), set up with:

```bash
# 1. Save the file they sent you as .env at this repo's root (same folder as
#    this README — it's gitignored, never commit it).
# 2. Distribute it into every service's own .env (mathbank-db/.env,
#    mathbank-rest/.env, etc.):
make sync-env            # or: ./sync-env.sh
# 3. Set OPENAI_API_KEY in the gitignored root .env. Shell keys are ignored.
#    Never share it through an unsecured channel.
#    make sync-openai-key copies it without printing it.
#    Also set ELEVEN_API_KEY (ElevenLabs voice) and the live-classroom keys
#    MATHBANK_REST_BASE_URL, MATHBANK_ADMIN_API_KEY, ADMIN_LOGIN_USERNAME,
#    ADMIN_LOGIN_PASSWORD, ADMIN_SESSION_SECRET (optional LIVE_PORT=5174).
#    sync-env/make up stop with "Missing in root .env: ..." if any are absent.
# 4. Install whatever isn't already installed, and see what (if anything) is
#    still missing:
make setup
# 5. Start rest/agent/web/live against the remote Neon/AuraDB:
make up
```

For a machine using Neon/AuraDB, prefer `make up-app`: it starts only
REST, agent, web and the live classroom, without trying to start local
Postgres/Neo4j.

### Bringing up the new pieces (live classroom, widgets, voice)

The fluid widgets, the separately deployable Socket.IO live classroom
(`mathbank-live`, :5174), the shared `mathbank-widgets` package and the
ElevenLabs voice add-on need this one-time sequence on each machine:

```bash
# 1. Root .env: OPENAI_API_KEY, ELEVEN_API_KEY and the live keys listed above.
make sync-env                    # writes every service .env incl. mathbank-live/.env
make setup                       # venvs + node_modules for web AND live
# 2. Database objects for live sessions/widgets/authoring (migration 020).
#    Idempotent; already applied on the shared Neon database.
make migrate-live-fluid-remote
# 3. Start and print every URL (web, Swagger, REST, agent, live, graph, Postgres).
make up-app                      # or: make up
make access
# 4. Verify (none of these spend money).
make test-unit                   # web + mathbank-widgets + live unit tests
make smoke                       # two-socket live-classroom smoke (needs REST + live)
make -C mathbank-web e2e-install # once: Playwright Chromium
make e2e                         # Playwright regression incl. add-ons and live
make check-eleven                # ElevenLabs key check, no audio generated
```

`make check-eleven TTS=1` and `make e2e-llm` make small **paid** calls; run
them only deliberately. After editing `mathbank-widgets/`, run
`make widgets-sync` (start/install also copy it) and restart web/live.
Live-only lifecycle: `make live-install | live-run | live-start | live-stop |
live-restart | live-status`. Requirements: [27 fluid widgets](requirements/27_FLUID_WIDGET_LAYER.md),
[28 distributed live platform](requirements/28_DISTRIBUTED_LIVE_PLATFORM.md),
[29 student input add-ons](requirements/29_STUDENT_INPUT_ADDONS.md).
These service start targets now wait for HTTP readiness (up to 60 seconds,
override with `START_TIMEOUT=120`) and fail if the process exits or never
responds with HTTP 200. They do not kill an unrelated process holding a port.
An access summary confirms startup HTTP readiness, not database connectivity,
model credentials, or successful tutoring.

#### Another developer Mac: startup troubleshooting

`pg_ctl` / `neo4j` missing only means local database software is absent.
It does not explain why Swagger or the web server cannot be reached when
the service configuration uses Neon/AuraDB. The older start targets printed
"started" after one second even if the process had already crashed.

On the affected Mac, use the current code, configure per-service environment
files securely, and install dependencies **on that machine**. Never copy
`.venv`, `node_modules`, `.next`, PID files or runtime logs from another Mac;
Python entrypoints contain absolute interpreter paths.

```sh
make setup
# If environments/dependencies were copied or are broken, rebuild only those:
make rest-install agent-install web-install live-install
make up-app

# Diagnose crashes locally. Redact credentials before sharing log excerpts.
tail -n 80 mathbank-rest/.server.log
tail -n 80 mathbank-agent/.server.log
tail -n 80 mathbank-web/.server.log
tail -n 80 mathbank-live/.server.log

# Foreground commands expose import/configuration/dependency errors directly.
# Run each in its own terminal after stopping the corresponding owned service.
make rest-run
make agent-run
make web-run
make live-run
```

Check access from a terminal **on that same Mac**:

```sh
curl --noproxy '*' -I http://127.0.0.1:8000/docs
curl --noproxy '*' http://127.0.0.1:8000/health
curl --noproxy '*' http://127.0.0.1:8001/list-apps
curl --noproxy '*' -I http://127.0.0.1:5173/login
curl --noproxy '*' -I http://127.0.0.1:5174/login
```

If these fail, inspect the relevant log rather than treating the startup PID
as proof of success. If they succeed but the browser fails, try `127.0.0.1`
instead of `localhost` and check proxy/VPN settings and the exact browser error.
`localhost` always means the machine running the browser, not a teammate's
Mac. Do not expose the development services to the network just to troubleshoot.
After HTTP works, run `make test-connectivity` to verify the configured
Postgres and Neo4j backends separately. Do not paste environment files,
API keys or passwords into an issue or chat.

#### Purple Comet archive

`make -C mathbank-db purple-comet-discover-remote` discovers both English divisions
from the official [archive](https://purplecomet.org/answers), downloads valid PDFs
and answer keys, registers Postgres sources and extracts numbered questions.
Use `YEAR=2026` for a bounded pilot. Original PDFs, page renders, answer HTML/JSON
and source manifests are retained under `mathbank_data_ingestion/data/crawl_pdf/purple_ms`
and `purple_hs`. Student diagrams are tight figure crops inside verified spatial
question boundaries, including continuation pages. Whole-page renders are audit
evidence only, never question diagrams. Problem and solution assets have separate
provenance; ambiguous numbering/layouts are left unverified, not guessed.

`make -C mathbank-db purple-comet-batches-remote` waits for the existing exclusive
paper runner, then processes batches of two through paid classification,
Postgres and verified Neo4j publication. It supports `BATCH_SIZE=`, `LIMIT=` and
`RESUME=`. Purple Comet classification uses `gpt-4.1` and sends the actual
question-specific figure/region crops as vision inputs, along with the official answer key.
New metadata follows the existing automatic-approval policy; protected human
corrections/rejections are not overwritten.

Do not equate an answer key with a worked solution or HTTP 200 with a PDF.
Some PDF endpoints return HTML rather than documents; these are explicit
failed sources, never successful parses. Valid legacy PDFs may have whitespace
before their `%PDF-` signature; rejecting those was a parser bug, now corrected.
Both official bare and `www` hosts are accepted. Missing worked-solution PDFs
are distinct from missing problem PDFs. The recovered archive inventory was
verified at 44 valid problem PDFs and 1,050 official answers (2005-2026, both
divisions), with four available worked-solution PDFs for 2025-2026. Historical
worked solutions are reported as unavailable, not fabricated. Completion requires
all available numbered solutions and verified question-specific figures, exact question/answer
coverage and graph inventory agreement. Source copyright remains with Purple
Comet; this workflow does not grant redistribution rights.

#### Repair existing source diagrams (no paid model calls)

```sh
make -C mathbank_data_ingestion repair-diagrams       # local audit; no writes
make -C mathbank_data_ingestion repair-diagrams-apply # artifacts + existing staging rows
# Optional PAPER=PAPER_SMT_2010_GEOM or COMPETITION=smt
# Optional DOWNLOAD_MISSING=1 explicitly fetches missing cached AoPS image URLs.

PG_ENV_FILE=mathbank-graph/remote.env mathbank-db/.venv/bin/python \
  mathbank-db/etl/backfill_question_figures.py         # Postgres audit
# Add --apply after reviewing the source manifests.
```

The repair refreshes manifests, source-side image lists, trailing Markdown figures
and staging visual provenance without changing statements, answers or enrichment.
It does not create missing staging questions. Per-question `diagram_status.json`
distinguishes extraction, verified absence of graphics, unverified PDFs, missing
sources and missing AoPS downloads. Student routes reject solution/answer images,
whole-page references and legacy assets with unknown provenance. See
[requirements 31](requirements/31_QUESTION_SPECIFIC_DIAGRAMS.md) for results and gaps.

#### Automatic teaching metadata

The admin jobs console at `/admin` now reports each paper's download, parse,
Postgres import, classification, vectors, corpus graph, generated pedagogy,
pedagogy publication and taxonomy graph independently. Filter by competition
or paper, expand inventory/errors/job history, and inspect UTC timestamps and
live counts. A completed paper batch alone is not an end-to-end success.
Graph outages and missing historical timestamps are reported explicitly.

Tutor search uses reviewed Neo4j graph evidence plus pgvector similarity and
Postgres lexical retrieval, fused by distinct problem with per-source ranks.
Retrieval warnings disclose unavailable graph evidence. For contracts see
[requirements 16](requirements/16_PIPELINE_JOB_CONSOLE_AND_HYBRID_RAG.md).

Existing PENDING and future generated corpus metadata are automatically
approved, with `approval_method=automatic` to distinguish machine estimates
from human review. Admin corrections and rejections are protected. Learning
context enriches missing skills/prerequisites/difficulty automatically; this
uses paid model requests and does not create learner mastery records.

Apply `mathbank-db/sql/008_automatic_metadata.sql` after migrations 006/007.
From `mathbank-rest`, `make enrich-corpus WATCH=1 WORKERS=4` backfills all questions
and watches newly ingested ones. Per-question status, attempts and failures
are recorded in `knowledge.enrichment_job`; invalid output is not approved.
For catalog relationships, also apply `mathbank-db/sql/009_relationship_enrichment.sql`
(`make -C mathbank-db migrate-relationship-enrichment-remote` for the configured
remote database), then run the **same watcher**, not a second publisher:
`make -C mathbank-rest enrich-corpus WATCH=1 WORKERS=4 RELATIONSHIPS=1`.
At most one slot generates skill PART_OF/BUILDS_ON or concept PREREQUISITE_OF
edges; other slots enrich questions. Generation and independent semantic review
default to `gpt-4.1`, configurable with `RELATIONSHIP_MODEL` and
`RELATIONSHIP_VERIFIER_MODEL`. Both incur paid calls. Zero-edge proposals are valid;
bounded candidates do not guarantee exhaustive relationships. Jobs, evidence,
errors and publication state are recorded in `knowledge.relationship_enrichment_job`.
Admins can inspect and correct concept relations alongside skill relations.
See the [relationship plan](requirements/15_RELATIONSHIP_ENRICHMENT.md).
The worker reselects work between every problem and prioritizes failed jobs
whose five-minute cooldown has elapsed, up to three job attempts. Non-watch
`LIMIT=...` bounds generation attempts; watch mode continues without a total cap.
Graph publication uses batches of at most 25, scheduled every 60 seconds or when
a full batch is ready (checked between jobs). Completed-but-unpublished jobs
are replayed without paying for regeneration. Transient graph failures use
three attempts with 2/4-second backoff, then watch mode retries after 60 seconds.
Generation and publication errors are logged separately.
`WORKERS` defaults to 1 and accepts 1-8. Four concurrent model jobs are currently
authorized. Imports retain their table locks for global cycle safety; only the
coordinator publishes graph batches, draining in-flight imports first so its
own jobs do not invalidate the publication fingerprint. In-flight codes are excluded from dispatch
and Postgres claims remain authoritative. SIGTERM/SIGINT stops dispatch, drains
active jobs, and flushes publication work before exit. Do not launch multiple
independent coordinators to increase concurrency. Provider rate limits and
serialized imports mean throughput will not necessarily scale linearly.
Watch mode also retries temporary Postgres read failures. Each generation can
request up to three structured model responses with exact catalog enums and
validation feedback, including existing-graph cycle conflicts. Metadata and its
COMPLETED publication job are saved in the same transaction. The admin UI lists
failed generation errors and offers reclassification.
The admin pedagogy UI supports attribute corrections, tag decisions and
reclassification; explicitly publish corrections to update Neo4j.

The running background backfill logs to
`mathbank-rest/logs/automatic-enrichment.log`. Full corpus completion is not
claimed until the remaining job count is zero and graph publication succeeds.
See the [recovery plan](requirements/14_AUTOMATIC_ENRICHMENT_RECOVERY.md)
for acceptance criteria and operational gotchas.

#### Model-key synchronization details

`make sync-openai-key` copies `OPENAI_API_KEY` from the root `.env` only
into REST, agent and ingestion
`.env` files, creating those files if absent. It also updates existing database,
graph and web `.env` files. It preserves unrelated settings, removes duplicate
key assignments, writes atomically with owner-only permissions (`0600`), and
never prints the value. The key is server-side only, never `NEXT_PUBLIC_*`.

`make sync-env`, `make up`, `make up-app` and `make up-local-db` include this
sync. Existing running services must be restarted to load changed values;
syncing alone does not restart them. REST, ADK/LiteLLM, classifiers, reviewers
and vector backfills use the shared file-only credential loader, even when run
directly or from a different working directory. A root `.env` is authoritative:
an empty/missing key there is an error, not a fallback to an inherited shell key
or a stale service key. A service `.env` key is supported only if no root `.env`
exists. Provider URL/organization/project settings also come from files, not
inherited shell values. Other variables such as worker database destinations
retain their existing precedence. No shell profile needs changing.

#### OpenAI / LiteLLM troubleshooting on either developer's machine

> **Note:** After saving or updating `OPENAI_API_KEY` in the root `.env`,
> run these commands from the repository root on each developer's machine.
> The `CHAT=1` check makes a small paid LiteLLM model request.

```sh
make sync-openai-key
make check-openai          # authenticate without a paid chat completion
make check-openai CHAT=1   # small paid LiteLLM model check
```

These checks read project files, never print the key, and do not source or modify
`.zshrc`. Chat uses `MATHBANK_AGENT_MODEL` from the agent `.env`, for example
`openai/gpt-4o-mini` (the `openai/` provider prefix matters). Authentication success
does not imply billing/model access: HTTP 401 means authentication failure,
403/404 can mean model permissions/name, and 429 means quota or rate limiting.
A valid key on this Mac does not prove the other Mac has the same saved file.
Run these checks there too. Do not paste full provider exception bodies into chat;
some include a partial key. Restart REST/agent after changing credentials, and
restart ingestion workers at a safe checkpoint rather than duplicating a live run.

#### ElevenLabs voice key and live-app environment

> **Note:** After saving or updating `ELEVEN_API_KEY` in the root `.env`, run these
> from the repository root. `TTS=1` makes one tiny paid ElevenLabs text-to-speech call.

```sh
make sync-eleven-key       # copy ELEVEN_API_KEY into mathbank-web/.env and mathbank-live/.env (never printed)
make check-eleven          # authenticate (lists voices) — no paid synthesis
make check-eleven TTS=1    # tiny paid text-to-speech check
make sync-live-env         # write mathbank-live/.env (REST URL, admin key/login, session secret, Eleven key, LIVE_PORT)
make sync-keys             # = sync-openai-key + sync-eleven-key + sync-live-env
```

The Eleven key stays server-side: the browser only calls the same-origin
`/api/voice/{tts,stt,health}` routes of web/live. Without a key, the 🔊/🎤
buttons show a brief "!" (voice unavailable) and typing keeps working; there is
no browser speech fallback. `make sync-env`
also runs the Eleven and live syncs, so it no longer drops `ELEVEN_API_KEY`.
Restart web/live after changing the key.

Terminology and exact score semantics are in the
[domain and technical glossary](requirements/17_DOMAIN_AND_TECHNICAL_GLOSSARY.md).

`sync-env.sh` backs up any existing per-service `.env` to
`<file>.bak.<timestamp>` before overwriting it, and clearly flags any key
that's missing/empty in the root `.env` (writes the rest anyway, exits
non-zero so you notice). Re-run it any time the shared `.env` changes.

### Everyone else (`.env` files already in place)

```bash
make setup    # check/create .env files, flag missing secrets, install every
              # venv/node_modules not already present — safe to re-run anytime
make up       # start rest/agent/web/live against remote Neon/AuraDB
make status   # confirm everything is running
make down     # stop rest/agent/web/live
```

After starting the services, `make up` (and `make up-local-db`) prints a
labeled access summary. Run `make access` to display it again without
restarting anything. Default addresses:

| Access | URL or command |
|---|---|
| Student web UI | http://localhost:5173/login |
| Admin web UI | http://localhost:5173/admin/login |
| Live classroom (join / instructor console) | http://localhost:5174 (sign in at `/login`) |
| Live socket | `ws://localhost:5174/socket.io` |
| REST API base | http://localhost:8000 |
| REST Swagger UI | http://localhost:8000/docs |
| Agent API base | http://localhost:8001 |
| Agent Swagger UI | http://localhost:8001/docs |
| Remote Postgres (Neon) | host / database / user from `mathbank-graph/remote.env` |
| Remote Postgres shell | `make psql-remote` |
| Remote graph (Neo4j AuraDB) | `neo4j+s://…` URI / database / user from `mathbank-graph/remote.env` |
| Neon / Aura consoles | https://console.neon.tech · https://console.neo4j.io |

The remote rows are read from `mathbank-graph/remote.env` (`make access-remote`
prints only these). Passwords are never shown. Local Postgres/Neo4j details are
printed only by `make access-local`, which `make up-local-db` uses.
The summary does not check readiness; use `make status` for that.

If a port is busy when a service starts: when the process holding it is the
one that service's `start` recorded in its `.server.pid` but it no longer
answers HTTP 200 (for example, a live server returning 500 after its `.next`
build folder was removed), `start` stops it and starts a fresh one. A
process the script did not start is never killed; you get an error with the
PID to check instead.

Graph relationship views at `/graph` default to 1,000 relationships.
Use the relationship-limit selector to show up to 5,000; each view displays
the number of sampled nodes and relationships alongside the total available
relationships. Snapshots are cached for five minutes per view and limit.

The live app uses locally bundled Bootstrap styling and a responsive,
full-width workspace. Graph views provide
zoom/fit controls, a node legend, and node inspection.

Tutor responses stream through the same-origin `/api/agent/run` proxy to
ADK's `/run_sse` endpoint. The activity panel shows tool calls, completion
status, and progress updates, not private reasoning or raw tool payloads.
Use **Stop** to cancel an active response; failures are displayed explicitly.
The non-streaming API response remains available for existing callers.
Streaming parser and event-mapping tests run with
`node --test mathbank-web/tests/*.test.mjs`.

Browser regression (Playwright) runs against the running stack:
`make -C mathbank-web e2e` (no paid calls) or `make -C mathbank-web e2e-llm`
(includes small paid tutor/grader calls). First run `make -C mathbank-web e2e-install`.
See [requirements/23_E2E_REGRESSION_SUITE.md](requirements/23_E2E_REGRESSION_SUITE.md).
Agent conversations are rebuilt per student at `/learn/conversations` and for
admins at `/admin/conversations` ([requirements/22](requirements/22_AGENT_SESSION_TRANSCRIPTS.md)).

### Student input add-ons and the live classroom

- **Math composer** (chat, Solve workspace, live classroom): symbol palette, live
  KaTeX preview, `$x$` quick-format (deterministic, free) and ✨ agentic format
  (small paid model, falls back to deterministic if it would change meaning),
  🎤 dictation via ElevenLabs speech-to-text. Tutor replies have a 🔊 speak button.
- **Widgets**: the tutor can attach validated, declarative widgets (geometry
  diagram, formula card, step progress, table, poll results) as fenced
  ```` ```widget ```` blocks; nothing is executed. Gallery: http://localhost:5173/admin/widgets.
- **Live classroom** (`mathbank-live`, :5174): instructors create a session from
  topics, share the join code, pace topics, put widgets on the board, run polls with
  reveal, message the class (LaTeX), and take over from the AI tutor; students
  join by code, answer polls, ask the AI tutor or the instructor, and mark
  confusion. Reconnects replay missed events by sequence. Sign-in cookies are
  shared with the web app on the same host.

```sh
make -C mathbank-live install && make -C mathbank-live start
make -C mathbank-live test     # gateway unit tests (no services)
make -C mathbank-live smoke    # two-socket realtime smoke against the running stack (no paid calls)
make -C mathbank-web sync-widgets   # after editing ../mathbank-widgets (also run for live)
```

See [requirements/27](requirements/27_FLUID_WIDGET_LAYER.md),
[28](requirements/28_DISTRIBUTED_LIVE_PLATFORM.md) and
[29](requirements/29_STUDENT_INPUT_ADDONS.md).

### Guided pedagogical practice

Open http://localhost:5173/learn, or choose **Learn with diagnosis and hints**
from a corpus problem. The anonymous workspace loads an answer-free learning
context, asks where you are stuck, and offers one provisional hint at a time.
Update your attempt before requesting the next level (up to three). These
requests do not record learner attempts or mastery.

The teaching graph adds measurable `Skill` nodes, reviewed prerequisite and
hierarchy edges, problem-skill roles/levels, and multidimensional difficulty.
Graph views show metadata and relationship evidence; pedagogical views
default to reviewed-only data. Before metadata is reviewed and projected,
the UI explicitly reports missing enrichment instead of inventing skills,
prerequisites, or lower-level same-skill practice. Lower required levels on a
shared skill are not a guarantee of lower overall problem difficulty.

### Step-by-step solving (Prasolov problems)

Log in as a student (or use a demo account), then open
`http://localhost:5173/learn/solve/{code}`, for example
http://localhost:5173/learn/solve/PRASOLOV_PGV1_CH01_P001, or click **Solve
step by step** on a Prasolov problem. Each step is graded on the server, hints
come one level at a time, and progress is saved: reloading the page resumes
where you left off. The grader and hint writer use `STEP_TUTOR_MODEL` (default
`gpt-4.1-mini`) through the project `.env` key. When a step keeps failing
(two wrong tries or three hints), the **What's tripping you up?** card names
the skill most likely missing and links quick practice checks; students can
also ask for it with **Diagnose where I'm stuck**. From that card the student can
start a **short detour**: a few staged practice items on the missing skill (theory,
multiple choice, a short subproblem, then a transfer check). Afterwards **Return**
brings them back to the exact step they were stuck on. Admins can review gaps and
detours at http://localhost:5173/admin/knowledge-gaps. Optional AI re-ranking of
the diagnosis is off by default; set `DIAGNOSIS_LLM_RERANK=1` (model
`DIAGNOSIS_RERANK_MODEL`, falling back to `STEP_TUTOR_MODEL`) to turn it on.
Details and evidence are in
[tracker 18](requirements/18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md).

The explicitly authorized 2026-10-04 Neon/Aura rollout is complete: migration
006, 6 starter skills, 18 skill-related edges, 65 additional concept-hierarchy
projections, and 3 problem-difficulty assessments. After explicit operator
authorization, the 27 starter assertions were bulk-approved in Postgres and
published to Neo4j: 6 reviewed skills, 18 reviewed skill-related edges and
3 reviewed assessments. The 65 legacy hierarchy assertions remain PENDING.
Uncheck **Reviewed only** in teaching graph views to inspect pending inventory.
The starter set covers three counting problems, not the entire corpus.

Use [the admin approval workspace](http://localhost:5173/admin/pedagogy) to
inspect and approve/reject individual or selected batches of metadata, view
immutable review history, and explicitly publish decisions to Neo4j. Review
requires admin login and a rationale; stale changes and reviewed cycles are
rejected. Approval and graph publication are separate operations.

See [the pedagogical requirements and phased plan](requirements/13_PEDAGOGICAL_GRAPH_AND_TUTOR_REQUIREMENTS.md)
for the implemented P0 scope and planned P1 solution steps, hint ladders,
misconceptions, and versioned courses. The additive migration, validated
metadata import, and opt-in graph projection are explicit rollout steps
described in [mathbank-db/README.md](mathbank-db/README.md) and
[mathbank-graph/README.md](mathbank-graph/README.md); they are not automatically
applied to shared databases by app startup.

The [pedagogical presentation](presentation/pedagogy.html) explains the
diagnostic/micro-lesson/hint/return-to-problem flow and distinguishes deployed
P0 metadata from P1/P2 plans. Runtime validation includes real model coaching,
streamed ADK tool selection, browser hint gating, idempotent writes, and
rolled-back SQL/Neo4j failure tests; see the requirements' live-rollout section.

`make setup` is the first thing to run on a new machine (or after pulling
changes that touch dependencies) — it never reinstalls something that's
already present, it just reports what's missing. Typical first-run output on
a machine that's only partially configured:

```
Environment files
  ✓ mathbank-db/.env present, no placeholder values left
  ⚠ mathbank-agent/.env did not exist — created from .env.example. Edit it before running this service.
  ⚠ mathbank-web/.env present but still has placeholder value(s): ADMIN_LOGIN_PASSWORD

Shell environment
  OPENAI_API_KEY synchronization failed; set it in root .env before startup.
  ELEVEN_API_KEY synchronization failed; set it in root .env (make up runs this sync and stops if it fails).

Python virtual environments
  ✓ mathbank-rest/.venv already present
  ...

Summary
Some configuration needs attention (see ⚠ above) before running: make up
```

For a genuinely fresh clone with no `.venv`/`node_modules` anywhere yet,
`make setup` creates every `.env` from its `.env.example`, builds every
Python venv (`mathbank_data_ingestion`, `mathbank-db`, `mathbank-graph`,
`mathbank-rest`, `mathbank-agent`), runs `npm install` for
`mathbank-web` and `mathbank-live` (both copy the local `mathbank-widgets`
package; it needs no install of its own), syncs the OpenAI/ElevenLabs keys
and writes `mathbank-live/.env` — then tells you exactly which `.env` files still need real
secrets filled in before `make up` will work.

### Individual services

Every service also has its own lifecycle targets from the root:

```bash
make <svc>-start | <svc>-stop | <svc>-restart | <svc>-status   # svc = db | graph | rest | agent | web | live
make rest-run | agent-run | web-run | live-run                  # foreground, for debugging
```

See each service's own `Makefile`/`README.md` for the full command
reference (`mathbank-db/README.md`, `mathbank-agent/README.md`,
`mathbank-graph/README.md`, `mathbank-web/README.md`; `mathbank-live/Makefile`).

### Tests from the root

```bash
make test-unit   # Node unit tests: mathbank-web + mathbank-widgets + mathbank-live
make smoke       # live-classroom two-socket smoke against running REST + live
make e2e         # Playwright regression (needs the stack up; skips live if :5174 is down or E2E_SKIP_LIVE=1)
make e2e-llm     # adds @llm specs — small PAID OpenAI calls
make -C mathbank-rest test   # REST pytest suite
```

See [requirements/23_E2E_REGRESSION_SUITE.md](requirements/23_E2E_REGRESSION_SUITE.md) for coverage and baselines.

### Full corpus pipeline (new competition papers → searchable + graphed)

```bash
cd mathbank_data_ingestion && make crawl-unmapped LIMIT=3200 && make classify LIMIT=3200 && make export-classifications
cd ../mathbank-db          && make etl-remote
cd ../mathbank-graph       && make project-remote
cd ../mathbank-db          && make vector-backfill-remote   # needs OPENAI_API_KEY
```

Full detail, idempotency guarantees, and the performance caveat on the
embedding-backfill step: [DATABASES.md § Full corpus pipeline](DATABASES.md#full-corpus-pipeline-crawl--classify--export--etl--graph--vector).

## Requirements & design docs

- [requirements/00_INDEX.md](requirements/00_INDEX.md) — product/data-model/ingestion/RAG/API/infra/agentic-tutor/student-UI requirements, numbered and cross-referenced.
- [requirements/reference/](requirements/reference/) — canonical source-derived PostgreSQL, graph, DML and REST/OpenAPI reference for the current implementation.
- [mathematics_tutor_db_plan/](mathematics_tutor_db_plan/) — the detailed Postgres/Neo4j/vector/agent architecture these requirements are built from.
- [presentation/](presentation/) — a static HTML walkthrough of the whole system (`index.html`) for a mixed technical/business audience, including real screenshots and live-captured data.
