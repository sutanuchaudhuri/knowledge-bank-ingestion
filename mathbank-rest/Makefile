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
start:                          ## Start as a background daemon on :$(PORT) (kills whatever already holds the port)
	@lsof -ti:$(PORT) | xargs kill -9 2>/dev/null || true
	@nohup $(UVICORN) mathbank_rest.main:app --app-dir src --port $(PORT) > $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE)
	@sleep 1
	@echo "mathbank-rest started on :$(PORT) (pid $$(cat $(PID_FILE))), logs in $(LOG_FILE)"

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

# ── Help ───────────────────────────────────────────────────────────────────

.PHONY: help
help:                           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
