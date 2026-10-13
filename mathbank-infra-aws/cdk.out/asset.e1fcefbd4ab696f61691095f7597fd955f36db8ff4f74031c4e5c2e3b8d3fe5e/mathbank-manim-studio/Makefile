PYTHON_VERSION ?= 3.11
VENV      := .venv
BIN       := $(VENV)/bin
PYTHON    := $(BIN)/python3

PORT      ?= 8020
PID_FILE  := .server.pid
LOG_FILE  := .server.log

.DEFAULT_GOAL := help

.PHONY: help
help:                            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*##"}; {printf "  %-20s %s\n", $$1, $$2}'

.PHONY: venv
venv:                            ## Create the virtual environment
	python3 -m venv $(VENV)

.PHONY: install
install: venv                   ## Install runtime + dev dependencies (includes manim)
	$(BIN)/pip install -e ".[dev]"

.PHONY: test
test:                            ## Run the full test suite (includes a real OpenAI call + real manim render, ~30s)
	$(PYTHON) -m pytest -v

.PHONY: run
run:                             ## Run the dev server in the foreground (--reload, Ctrl+C to stop)
	$(BIN)/uvicorn mathbank_manim_studio.main:app --reload --port $(PORT)

.PHONY: start
start:                           ## Start on :$(PORT) in the background and verify HTTP readiness
	@bash ../mathbank-scripts/start-service.sh mathbank-manim-studio "$(PORT)" "$(PID_FILE)" "$(LOG_FILE)" \
	  "http://127.0.0.1:$(PORT)/v1/render-jobs" "$(BIN)/python3" -m uvicorn mathbank_manim_studio.main:app --port $(PORT)

.PHONY: stop
stop:                            ## Stop the background daemon (by pidfile, then by port as a fallback)
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE); fi
	@lsof -ti:$(PORT) | xargs kill -9 2>/dev/null || true
	@echo "mathbank-manim-studio stopped"

.PHONY: restart
restart: stop start              ## Restart the background daemon

.PHONY: status
status:                          ## Show whether the server is listening on :$(PORT)
	@lsof -ti:$(PORT) >/dev/null 2>&1 && echo "mathbank-manim-studio: running on :$(PORT)" || echo "mathbank-manim-studio: not running"

.PHONY: access
access:                          ## Show the service URL
	@printf '  %-20s %s\n' 'Manim Video Studio' 'http://localhost:$(PORT)'

.PHONY: cleanup
cleanup:                         ## Delete expired (>1 day old) research/render jobs and their videos
	$(PYTHON) scripts/cleanup_expired_jobs.py

.PHONY: clean
clean:                           ## Remove build artifacts and caches
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null; \
	rm -rf .pytest_cache *.egg-info src/*.egg-info
