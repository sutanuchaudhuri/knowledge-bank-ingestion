PYTHON_VERSION ?= 3.12
VENV      := .venv
BIN       := $(VENV)/bin
PORT      ?= 8040
PID_FILE  := .server.pid
LOG_FILE  := .server.log
RUNTIME   := .runtime
SMOKE_TEXT ?= Hi. Can you help me understand the angle bisector theorem?

.DEFAULT_GOAL := help

.PHONY: help
help:                            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*##"}; {printf "  %-16s %s\n", $$1, $$2}'

.PHONY: install
install:                         ## Create the Python 3.12 venv and install runtime + dev dependencies
	@test -d $(VENV) || uv venv $(VENV) --python $(PYTHON_VERSION)
	uv pip install --python $(BIN)/python -e ".[dev]"

.PHONY: test
test:                            ## Offline tests (no AWS/OpenAI/network), lint and type check
	$(BIN)/python -m pytest -q
	$(BIN)/python -m ruff check src tests
	$(BIN)/python -m mypy src
	node --check src/mathbank_genai_poc/static/app.js
	node --check src/mathbank_genai_poc/static/pcm-worklet.js

.PHONY: check-aws
check-aws:                       ## Read-only: model access, vector indexes and content table (no paid calls)
	$(BIN)/python scripts/check_aws.py

.PHONY: search
search:                          ## One retrieval only (1 OpenAI embedding, no voice): make search TOPIC="power of a point"
	@test -n "$(TOPIC)" || (echo 'Usage: make search TOPIC="angle bisector theorem"' && exit 1)
	$(BIN)/python -c 'import json,sys; from mathbank_genai_poc.config import Settings; from mathbank_genai_poc.knowledge import KnowledgeBase, public_view; print(json.dumps(public_view(KnowledgeBase(Settings()).search(sys.argv[1])), indent=2))' "$(TOPIC)"

.PHONY: run
run:                             ## Run in the foreground on http://127.0.0.1:$(PORT) (Ctrl+C to stop)
	GENAI_POC_PORT=$(PORT) $(BIN)/python -m mathbank_genai_poc.server

.PHONY: start
start:                           ## Start in the background on :$(PORT) and verify readiness
	@GENAI_POC_PORT=$(PORT) bash ../mathbank-scripts/start-service.sh mathbank-aws-genai-poc "$(PORT)" "$(PID_FILE)" "$(LOG_FILE)" \
	  "http://127.0.0.1:$(PORT)/health" "$(BIN)/python" -m mathbank_genai_poc.server
	@echo "Open http://127.0.0.1:$(PORT)/"

.PHONY: stop
stop:                            ## Stop the background server started by `make start` (pidfile only)
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE); echo "mathbank-aws-genai-poc: stopped"; \
	else echo "mathbank-aws-genai-poc: not started by make start"; fi

.PHONY: restart
restart: stop start              ## Restart the background server

.PHONY: status
status:                          ## Show whether the server is listening, plus budget/targets from /health
	@curl -fsS http://127.0.0.1:$(PORT)/health 2>/dev/null && echo || echo "mathbank-aws-genai-poc: not running on :$(PORT)"

.PHONY: budget
budget:                          ## Show the local paid-audio ledger
	@cat $(RUNTIME)/usage.json 2>/dev/null || echo "No paid sessions recorded yet."

.PHONY: smoke
smoke:                           ## PAID (~1 min audio): Chromium fake mic -> live tutor; requires `make start` and CONFIRM=1
	@test "$(CONFIRM)" = "1" || (echo "Paid Nova Sonic call. Re-run with CONFIRM=1." && exit 1)
	@mkdir -p $(RUNTIME)
	say -o $(RUNTIME)/question.aiff "$(SMOKE_TEXT)"
	afconvert -f WAVE -d LEI16@48000 -c 1 $(RUNTIME)/question.aiff $(RUNTIME)/question.wav
	node scripts/smoke_browser.mjs $(RUNTIME)/question.wav
