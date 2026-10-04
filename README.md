# MathBank Platform

A competition-math corpus (AMC/AIME/HMMT/SMT/PUMaC/CHMMC/CMM/Math Prize for
Girls) with hybrid (semantic + lexical) RAG search, a knowledge graph, an
agentic tutor, and a student-profile web UI — built from five independent
services:

| Service | What it is | Port |
|---|---|---|
| `mathbank-db` | Postgres 16 + pgvector — `core.*`/`knowledge.*`/`search.*`/`learner.*`/`pipeline.*` schema + ETL/embedding pipelines | 5433 (local) |
| `mathbank-graph` | Neo4j — knowledge graph projection (`TESTS`, `USES_TECHNIQUE`, `MASTERED`, ...) | 7474/7687 (local) |
| `mathbank-rest` | FastAPI — the only service that talks to Postgres/Neo4j directly; hybrid search, learner auth/mastery, admin pipeline endpoints | 8000 |
| `mathbank-agent` | Google ADK agent (OpenAI via LiteLLM) — calls `mathbank-rest` as tools, never touches the DBs directly | 8001 |
| `mathbank-web` | Next.js — student chat/login/profile UI + admin ingestion UI, proxies to `mathbank-rest`/`mathbank-agent`/Neo4j server-side | 5173 |

Production/demo data lives on managed cloud services (Neon Postgres + Neo4j
AuraDB) — see [DATABASES.md](DATABASES.md) for the full local-vs-remote
picture and the end-to-end corpus pipeline (crawl → classify → ETL → graph →
vector embeddings). See [GOTCHAS.md](GOTCHAS.md) for environment
troubleshooting accumulated across this project's history.

## Quick start

### New collaborator with a shared `.env`

If someone on the team sent you a consolidated `.env` over a **secure
channel** (it contains live database/API credentials — never over email or
chat that isn't end-to-end secured), set up with:

```bash
# 1. Save the file they sent you as .env at this repo's root (same folder as
#    this README — it's gitignored, never commit it).
# 2. Distribute it into every service's own .env (mathbank-db/.env,
#    mathbank-rest/.env, etc. — each service only ever reads its own):
make sync-env            # or: ./sync-env.sh
# 3. Export your own OPENAI_API_KEY in your shell (~/.zshrc) — this is
#    intentionally NOT in the shared .env, never written to any file.
# 4. Install whatever isn't already installed, and see what (if anything) is
#    still missing:
make setup
# 5. Start everything:
make up
```

`sync-env.sh` backs up any existing per-service `.env` to
`<file>.bak.<timestamp>` before overwriting it, and clearly flags any key
that's missing/empty in the root `.env` (writes the rest anyway, exits
non-zero so you notice). Re-run it any time the shared `.env` changes.

### Everyone else (`.env` files already in place)

```bash
make setup    # check/create .env files, flag missing secrets, install every
              # venv/node_modules not already present — safe to re-run anytime
make up       # start every service (db, graph, rest, agent, web), in order
make status   # confirm everything is running
make down     # stop everything
```

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
  ⚠ OPENAI_API_KEY is NOT set — required by mathbank-rest (embeddings), mathbank-agent (chat), mathbank_data_ingestion (classification). Export it in ~/.zshrc, then open a new terminal.

Python virtual environments
  ✓ mathbank-rest/.venv already present
  ...

Summary
Some configuration needs attention (see ⚠ above) before running: make up
```

For a genuinely fresh clone with no `.venv`/`node_modules` anywhere yet,
`make setup` creates every `.env` from its `.env.example`, builds every
Python venv (`mathbank_data_ingestion`, `mathbank-db`, `mathbank-graph`,
`mathbank-rest`, `mathbank-agent`), and runs `npm install` for
`mathbank-web` — then tells you exactly which `.env` files still need real
secrets filled in before `make up` will work.

### Individual services

Every service also has its own lifecycle targets from the root:

```bash
make <svc>-start | <svc>-stop | <svc>-restart | <svc>-status   # svc = db | graph | rest | agent | web
```

See each service's own `Makefile`/`README.md` for the full command
reference (`mathbank-db/README.md`, `mathbank-agent/README.md`,
`mathbank-graph/README.md`, `mathbank-web/README.md`).

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
- [mathematics_tutor_db_plan/](mathematics_tutor_db_plan/) — the detailed Postgres/Neo4j/vector/agent architecture these requirements are built from.
- [presentation/](presentation/) — a static HTML walkthrough of the whole system (`index.html`) for a mixed technical/business audience, including real screenshots and live-captured data.
