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

.PHONY: install
install:                        ## npm install
	npm install

.PHONY: dev
dev:                             ## Start the Next.js dev server on :$(WEB_PORT) in the foreground
	npm run dev

.PHONY: start
start:                           ## Start as a background daemon on :$(WEB_PORT) (kills whatever already holds the port)
	@lsof -ti:$(WEB_PORT) | xargs kill -9 2>/dev/null || true
	@nohup npm run dev > $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE)
	@sleep 1
	@echo "mathbank-web started on :$(WEB_PORT) (pid $$(cat $(PID_FILE))), logs in $(LOG_FILE)"

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
