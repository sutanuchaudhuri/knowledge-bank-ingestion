PYTHON_VERSION ?= 3.11
VENV      := .venv
BIN       := $(VENV)/bin
PYTEST    := $(BIN)/pytest
RUFF      := $(BIN)/ruff
UVICORN   := $(BIN)/uvicorn

PORT      ?= 8000
PID_FILE  := .server.pid
LOG_FILE  := .server.log

.DEFAULT_GOAL := help

.PHONY: access
access:                         ## Show REST API and Swagger URLs
	@printf '  %-20s %s\n' 'REST API (base)' 'http://localhost:$(PORT)' \
	  'REST Swagger' 'http://localhost:$(PORT)/docs'

.PHONY: migrate-corpus-authoring
migrate-corpus-authoring:        ## Explicitly apply migration 025 to REST's configured PostgreSQL (no ingestion/models)
	$(BIN)/python scripts/migrate_corpus_authoring.py --apply

.PHONY: migrate-exam-resume-state
migrate-exam-resume-state:        ## Explicitly apply migration 051 for durable exam drafts and resume position
	$(BIN)/python scripts/migrate_exam_resume_state.py --apply --direct

# ── Environment ────────────────────────────────────────────────────────────
# Uses `uv` (https://docs.astral.sh/uv/) to manage the venv — plain
# `python3.11 -m venv` can produce a broken interpreter on this machine when
# python3.11 is a uv-installed standalone build invoked outside of uv.

.PHONY: venv
venv:                           ## Create the virtual environment
	uv venv $(VENV) --python $(PYTHON_VERSION)
	@echo "Virtual environment created at $(VENV)/"

.PHONY: install
install: venv                   ## Install runtime + dev dependencies
	uv pip install --python $(BIN)/python -e ../mathbank-geometry-engine
	uv pip install --python $(BIN)/python -e ".[dev]"

.PHONY: migrate-geometry-scenes
migrate-geometry-scenes:        ## Explicitly apply additive geometry storage migration 026
	$(BIN)/python scripts/migrate_geometry_scenes.py --apply --direct

.PHONY: test-geometry
test-geometry:                  ## Geometry REST/unit tests (PG integration opt-in via GEOMETRY_TEST_POSTGRES_DSN)
	$(PYTEST) tests/test_geometry_storage.py tests/test_geometry_api.py tests/test_geometry_postgres.py

# ── Quality ────────────────────────────────────────────────────────────────

.PHONY: lint
lint:                           ## Run ruff linter
	$(RUFF) check src tests scripts

.PHONY: test
test:                           ## Run the test suite
	$(PYTEST)

.PHONY: test-socratic-offline setup-socratic-local
test-socratic-offline:           ## Test staff sessions/setup locally with synthetic providers; no AWS/database/model calls
	$(PYTEST) -q tests/test_socratic_auth.py tests/test_socratic_local_auth.py tests/test_socratic_auth_setup.py tests/test_socratic_users.py tests/test_security.py

setup-socratic-local:            ## Configure loopback-only staff login; prompts for a local password, never prints it
	$(BIN)/python scripts/setup_socratic_auth.py --mode local --origin http://127.0.0.1:5186 --apply

.PHONY: socratic-password
socratic-password:               ## Generate/rotate local staff password into .env (SOCRATIC_LOCAL_PASSWORD + hash); keeps auth mode
	$(BIN)/python scripts/setup_socratic_auth.py --mode local --origin http://127.0.0.1:5186 --generate-password --credentials-only --apply

.PHONY: run-socratic-local
run-socratic-local:              ## Run configured local staff session API on loopback (single process, no reload)
	$(BIN)/python scripts/run_socratic_local.py --port $(PORT)

# Background copy of run-socratic-local on its own port/pidfile so it never collides with
# the full REST daemon on :$(PORT). DRAFTS=1 adds real draft storage in configured Postgres.
SOCRATIC_PORT     ?= 8019
SOCRATIC_PID_FILE := .socratic.pid
SOCRATIC_LOG_FILE := .socratic.log

.PHONY: start-socratic-local stop-socratic-local status-socratic-local
start-socratic-local:            ## Start local staff API on :$(SOCRATIC_PORT) in background (DRAFTS=1 = real Postgres drafts)
	@bash ../mathbank-scripts/start-service.sh mathbank-socratic-api "$(SOCRATIC_PORT)" "$(SOCRATIC_PID_FILE)" "$(SOCRATIC_LOG_FILE)" \
	  "http://127.0.0.1:$(SOCRATIC_PORT)/openapi.json" "$(BIN)/python" scripts/run_socratic_local.py --port $(SOCRATIC_PORT) $(if $(filter 1,$(DRAFTS)),--with-drafts,)

stop-socratic-local:             ## Stop the background local staff API (pidfile only; never kills other listeners)
	@if [ -f $(SOCRATIC_PID_FILE) ]; then kill $$(cat $(SOCRATIC_PID_FILE)) 2>/dev/null || true; rm -f $(SOCRATIC_PID_FILE); fi
	@echo "mathbank-socratic-api stopped"

status-socratic-local:           ## Show whether the local staff API is listening on :$(SOCRATIC_PORT)
	@lsof -ti:$(SOCRATIC_PORT) >/dev/null 2>&1 && echo "mathbank-socratic-api: running on :$(SOCRATIC_PORT)" || echo "mathbank-socratic-api: not running"

.PHONY: test-socratic migrate-socratic-drafts verify-socratic-deployment
test-socratic:                   ## All Socratic REST tests; Postgres cases skip unless SOCRATIC_DB_TESTS=1 (rolled back)
	$(PYTEST) -q tests/test_socratic_auth.py tests/test_socratic_local_auth.py tests/test_socratic_auth_setup.py tests/test_socratic_drafts.py tests/test_socratic_postgres.py tests/test_socratic_preview.py tests/test_socratic_preview_postgres.py tests/test_activity_scoring.py tests/test_socratic_users.py tests/test_security.py

migrate-socratic-drafts:         ## Explicitly apply additive migration 053 (orchestration.socratic_*) to configured Postgres
	$(BIN)/python scripts/migrate_socratic_drafts.py --apply --direct

verify-socratic-deployment:      ## Read-only hosted check: make verify-socratic-deployment URL=https://...lambda-url...
	@test -n "$(URL)" || (echo "Usage: make verify-socratic-deployment URL=<Studio URL>" && exit 1)
	$(BIN)/python scripts/verify_socratic_deployment.py --url "$(URL)"

# ── Run ──────────────────────────────────────────────────────────────────

.PHONY: run
run:                            ## Start the FastAPI dev server on :$(PORT) in the foreground (--reload)
	$(UVICORN) mathbank_rest.main:app --app-dir src --reload --port $(PORT)

.PHONY: start
start:                          ## Start on :$(PORT), verify HTTP readiness, and report failures (never kills an occupied port)
	@bash ../mathbank-scripts/start-service.sh mathbank-rest "$(PORT)" "$(PID_FILE)" "$(LOG_FILE)" \
	  "http://127.0.0.1:$(PORT)/docs" "$(BIN)/python" -m uvicorn mathbank_rest.main:app --app-dir src --port $(PORT)

.PHONY: stop
stop:                           ## Stop the background daemon (by pidfile, then by port as a fallback)
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE); fi
	@lsof -ti:$(PORT) | xargs kill -9 2>/dev/null || true
	@echo "mathbank-rest stopped"

.PHONY: restart
restart: stop start             ## Restart the background daemon

.PHONY: status
status:                         ## Show whether the server is listening on :$(PORT)
	@lsof -ti:$(PORT) >/dev/null 2>&1 && echo "mathbank-rest: running on :$(PORT)" || echo "mathbank-rest: not running"

.PHONY: test-connectivity
test-connectivity:              ## Ping Postgres + Neo4j directly (no server needed)
	@test -f .env || (echo "Create .env from .env.example first" && exit 1)
	$(BIN)/python scripts/test_connectivity.py

.PHONY: eval-retrieval
eval-retrieval:                 ## Precision@K/Recall@K/MRR/nDCG@K against the running server ($(PORT))
	$(BIN)/python scripts/evaluate_retrieval.py --base-url http://127.0.0.1:$(PORT) --k 10

# ── Help ───────────────────────────────────────────────────────────────────

.PHONY: help
help:                           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
.PHONY: enrich-corpus
.PHONY: outbox-drain outbox-watch outbox-status abandon-stale-attempts
outbox-drain:                    ## Drain outbox consumers once (analytics rollup + projection requests; free)
	$(BIN)/python -m mathbank_rest.outbox_worker --once

outbox-watch:                    ## Poll the outbox every $(or $(INTERVAL),30)s (free; INTERVAL=seconds)
	$(BIN)/python -m mathbank_rest.outbox_worker --watch $(or $(INTERVAL),30)

outbox-status:                   ## Outbox events, consumer lag and pending projection requests
	$(BIN)/python -m mathbank_rest.outbox_worker --status

abandon-stale-attempts:          ## Mark solve attempts idle for DAYS (default 30) as ABANDONED, then drain
	$(BIN)/python -m mathbank_rest.outbox_worker --abandon-idle-days $(or $(DAYS),30)

enrich-corpus:                   ## Paid, resumable automatic teaching enrichment (WATCH=1 for new questions)
	$(BIN)/python scripts/enrich_corpus.py $(if $(WATCH),--watch,) $(if $(LIMIT),--limit $(LIMIT),) $(if $(WORKERS),--workers $(WORKERS),) $(if $(RELATIONSHIPS),--relationships,)
