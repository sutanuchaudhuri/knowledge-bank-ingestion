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
	uv pip install --python $(BIN)/python -e ".[dev]"

# ── Quality ────────────────────────────────────────────────────────────────

.PHONY: lint
lint:                           ## Run ruff linter
	$(RUFF) check src tests scripts

.PHONY: test
test:                           ## Run the test suite
	$(PYTEST)

# ── Run ──────────────────────────────────────────────────────────────────

.PHONY: run
run:                            ## Start the FastAPI dev server on :$(PORT) in the foreground (--reload)
	$(UVICORN) mathbank_rest.main:app --app-dir src --reload --port $(PORT)

.PHONY: start
start:                          ## Start on :$(PORT), verify HTTP readiness, and report failures (never kills an occupied port)
	@bash ../scripts/start-service.sh mathbank-rest "$(PORT)" "$(PID_FILE)" "$(LOG_FILE)" \
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
