PYTHON_VERSION ?= 3.11
VENV      := .venv
BIN       := $(VENV)/bin
UVICORN   := $(BIN)/uvicorn

PORT      ?= 8010
PID_FILE  := .server.pid
LOG_FILE  := .server.log

.DEFAULT_GOAL := help

.PHONY: help
help:                            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*##"}; {printf "  %-20s %s\n", $$1, $$2}'

.PHONY: venv
venv:                            ## Create the virtual environment
	uv venv $(VENV) --python $(PYTHON_VERSION)

.PHONY: install
install: venv                   ## Install runtime + dev dependencies
	uv pip install --python $(BIN)/python -e ".[dev]"

.PHONY: run
run:                            ## Run the dev server in the foreground (--reload, Ctrl+C to stop)
	$(UVICORN) mathbank_ml_inference.main:app --reload --port $(PORT)

.PHONY: start
start:                          ## Start on :$(PORT) in the background and verify HTTP readiness
	@bash ../mathbank-scripts/start-service.sh mathbank-ml-inference "$(PORT)" "$(PID_FILE)" "$(LOG_FILE)" \
	  "http://127.0.0.1:$(PORT)/docs" "$(BIN)/python" -m uvicorn mathbank_ml_inference.main:app --port $(PORT)

.PHONY: stop
stop:                           ## Stop the background daemon (by pidfile, then by port as a fallback)
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE); fi
	@lsof -ti:$(PORT) | xargs kill -9 2>/dev/null || true
	@echo "mathbank-ml-inference stopped"

.PHONY: restart
restart: stop start             ## Restart the background daemon

.PHONY: status
status:                         ## Show whether the server is listening on :$(PORT)
	@lsof -ti:$(PORT) >/dev/null 2>&1 && echo "mathbank-ml-inference: running on :$(PORT)" || echo "mathbank-ml-inference: not running"

.PHONY: access
access:                         ## Show the service URL and Swagger docs URL
	@printf '  %-20s %s\n' 'ML inference API' 'http://localhost:$(PORT)' \
	  'Swagger' 'http://localhost:$(PORT)/docs'

# TODO: add `test` target once tests/ has real tests (requirements/54 §6 — scaffold only
# for now). Deliberately not added yet so `make test` doesn't silently report success on
# an empty/placeholder suite.
