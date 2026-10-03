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

.PHONY: install
install:                        ## Create venv + install google-adk/litellm/httpx
	uv venv $(VENV) --python $(PYTHON_VERSION)
	uv pip install --python $(BIN)/python -e ".[dev]"

.PHONY: run
run:                             ## Serve the agent as a REST API on :$(AGENT_PORT) in the foreground
	$(BIN)/adk api_server agents --port $(AGENT_PORT) $(AGENT_ALLOW_ORIGINS)

.PHONY: start
start:                           ## Start as a background daemon on :$(AGENT_PORT) (kills whatever already holds the port)
	@lsof -ti:$(AGENT_PORT) | xargs kill -9 2>/dev/null || true
	@nohup $(BIN)/adk api_server agents --port $(AGENT_PORT) $(AGENT_ALLOW_ORIGINS) > $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE)
	@sleep 1
	@echo "mathbank-agent started on :$(AGENT_PORT) (pid $$(cat $(PID_FILE))), logs in $(LOG_FILE)"

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
	$(BIN)/adk web agents

.PHONY: chat
chat:                            ## Chat with the agent directly in the terminal (no HTTP)
	$(BIN)/adk run agents/mathbank_tutor

.PHONY: test
test:                            ## Run the test suite
	$(BIN)/pytest

.PHONY: help
help:                            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
