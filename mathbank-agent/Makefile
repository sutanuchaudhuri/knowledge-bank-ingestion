# mathbank-agent — Google ADK agentic backend (OpenAI models via LiteLLM).
#
# Quick start:
#   cp .env.example .env            # edit MATHBANK_AGENT_MODEL / REST URL if needed
#   make install
#   make run                         # ADK's own FastAPI server on :8001
#   make web                         # or: ADK's interactive dev UI on :8000 (needs mathbank-rest on a different port)
#
# Requires: mathbank-rest running (the tools call it over HTTP) and
# OPENAI_API_KEY exported in the environment (already in ~/.zshrc on this machine).

PYTHON_VERSION ?= 3.11
VENV      := .venv
BIN       := $(VENV)/bin
AGENT_PORT ?= 8001
PID_FILE  := .server.pid
LOG_FILE  := .server.log
# Browser clients should go through mathbank-web's server-side proxy instead
# (see GOTCHAS.md #13) — this is defense-in-depth for direct/future callers.
# adk's --allow_origins is a repeatable flag, NOT comma-separated.
AGENT_ALLOW_ORIGINS ?= --allow_origins=http://localhost:5173 --allow_origins=http://127.0.0.1:5173

.DEFAULT_GOAL := help

.PHONY: access
access:                         ## Show agent API and Swagger URLs
	@printf '  %-20s %s\n' 'Agent API (base)' 'http://localhost:$(AGENT_PORT)' \
	  'Agent Swagger' 'http://localhost:$(AGENT_PORT)/docs'

.PHONY: install
install:                        ## Create venv + install google-adk/litellm/httpx
	uv venv $(VENV) --python $(PYTHON_VERSION)
	uv pip install --python $(BIN)/python -e ".[dev]"

.PHONY: run
run:                             ## Serve the agent as a REST API on :$(AGENT_PORT) in the foreground
	$(BIN)/python server.py --port $(AGENT_PORT) $(AGENT_ALLOW_ORIGINS)

.PHONY: start
start:                           ## Start on :$(AGENT_PORT), verify HTTP readiness, and report failures (never kills an occupied port)
	@bash ../scripts/start-service.sh mathbank-agent "$(AGENT_PORT)" "$(PID_FILE)" "$(LOG_FILE)" \
	  "http://127.0.0.1:$(AGENT_PORT)/list-apps" "$(BIN)/python" server.py --port $(AGENT_PORT) $(AGENT_ALLOW_ORIGINS)

.PHONY: stop
stop:                            ## Stop the background daemon (by pidfile, then by port as a fallback)
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE); fi
	@lsof -ti:$(AGENT_PORT) | xargs kill -9 2>/dev/null || true
	@echo "mathbank-agent stopped"

.PHONY: restart
restart: stop start              ## Restart the background daemon

.PHONY: status
status:                          ## Show whether the agent server is listening on :$(AGENT_PORT)
	@lsof -ti:$(AGENT_PORT) >/dev/null 2>&1 && echo "mathbank-agent: running on :$(AGENT_PORT)" || echo "mathbank-agent: not running"

.PHONY: web
web:                             ## ADK's built-in interactive dev UI (manual testing)
	$(BIN)/python server.py --web --port $(AGENT_PORT) $(AGENT_ALLOW_ORIGINS)

.PHONY: chat
chat:                            ## Chat with the agent directly in the terminal (no HTTP)
	$(BIN)/adk run agents/mathbank_tutor

.PHONY: test
test:                            ## Run the test suite
	$(BIN)/python -m pytest

.PHONY: eval-agent
eval-agent:                      ## Tool-selection accuracy against golden cases (needs mathbank-rest running + OPENAI_API_KEY; costs credits)
	$(BIN)/python scripts/evaluate_agent.py

.PHONY: help
help:                            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
