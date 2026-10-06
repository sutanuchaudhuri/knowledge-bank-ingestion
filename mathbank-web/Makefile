# mathbank-web — Next.js chat frontend for the MathBank tutor agent.
#
# The browser only ever talks to THIS app (same-origin); app/api/agent/*
# route handlers proxy server-side to mathbank-agent, so mathbank-agent needs
# no CORS configuration for the browser.
#
# Quick start:
#   cp .env.example .env     # point at mathbank-agent's REST server if not on :8001
#   make install
#   make dev                  # http://localhost:5173

WEB_PORT ?= 5173
PID_FILE := .server.pid
LOG_FILE := .server.log

.DEFAULT_GOAL := help

.PHONY: access
access:                         ## Show frontend access URLs
	@printf '  %-20s %s\n' 'Web (student)' 'http://localhost:$(WEB_PORT)/login' \
	  'Web (admin)' 'http://localhost:$(WEB_PORT)/admin/login'

.PHONY: test
test:                           ## Node unit tests (no browser, no services)
	node --test tests/*.test.mjs

.PHONY: e2e-install
e2e-install:                    ## Install the Playwright Chromium browser (one-time)
	npx playwright install chromium

.PHONY: e2e
e2e:                            ## Playwright regression suite against running stack (no paid model calls)
	npx playwright test

.PHONY: e2e-llm
e2e-llm:                        ## Playwright suite INCLUDING @llm specs (small paid OpenAI calls)
	E2E_LLM=1 npx playwright test

.PHONY: e2e-report
e2e-report:                     ## Open the last Playwright HTML report
	npx playwright show-report

.PHONY: install
install:                        ## npm install
	npm install

.PHONY: dev
dev:                             ## Start the Next.js dev server on :$(WEB_PORT) in the foreground
	node node_modules/next/dist/bin/next dev -p $(WEB_PORT)

.PHONY: start
start:                           ## Start on :$(WEB_PORT), verify HTTP readiness, and report failures (never kills an occupied port)
	@test -f node_modules/next/dist/bin/next || (echo "ERROR: Next.js is missing. Run make install in mathbank-web." >&2; exit 1)
	@bash ../scripts/start-service.sh mathbank-web "$(WEB_PORT)" "$(PID_FILE)" "$(LOG_FILE)" \
	  "http://127.0.0.1:$(WEB_PORT)/login" node node_modules/next/dist/bin/next dev -p $(WEB_PORT)

.PHONY: stop
stop:                            ## Stop the background daemon (by pidfile, then by port as a fallback)
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE); fi
	@lsof -ti:$(WEB_PORT) | xargs kill -9 2>/dev/null || true
	@echo "mathbank-web stopped"

.PHONY: restart
restart: stop start              ## Restart the background daemon

.PHONY: status
status:                          ## Show whether the dev server is listening on :$(WEB_PORT)
	@lsof -ti:$(WEB_PORT) >/dev/null 2>&1 && echo "mathbank-web: running on :$(WEB_PORT)" || echo "mathbank-web: not running"

.PHONY: build
build:                           ## Production build
	npm run build

.PHONY: help
help:                            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
