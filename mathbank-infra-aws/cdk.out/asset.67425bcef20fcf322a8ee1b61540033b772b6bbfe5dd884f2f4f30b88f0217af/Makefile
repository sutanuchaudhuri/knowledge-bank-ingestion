WEB_PORT ?= 5175
PID_FILE := .server.pid
LOG_FILE := .server.log

.DEFAULT_GOAL := help

.PHONY: help
help:                             ## List targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

.PHONY: install
install:                         ## npm install
	npm install

.PHONY: dev
dev:                              ## Run in the foreground on :$(WEB_PORT)
	npm run dev

.PHONY: start
start:                           ## Start in background on :$(WEB_PORT) and verify readiness
	@test -f node_modules/next/dist/bin/next || (echo "ERROR: Next.js is missing. Run make install." >&2; exit 1)
	@bash ../mathbank-scripts/start-service.sh mathbank-ml-frontend "$(WEB_PORT)" "$(PID_FILE)" "$(LOG_FILE)" \
	  "http://127.0.0.1:$(WEB_PORT)" node node_modules/next/dist/bin/next dev -p $(WEB_PORT)

.PHONY: stop
stop:                             ## Stop the background server
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE); fi
	@lsof -ti:$(WEB_PORT) | xargs kill -9 2>/dev/null || true
	@echo "mathbank-ml-frontend stopped"

.PHONY: restart
restart: stop start              ## Restart

.PHONY: status
status:                           ## Is the server listening?
	@lsof -ti:$(WEB_PORT) >/dev/null 2>&1 && echo "mathbank-ml-frontend: running on :$(WEB_PORT)" || echo "mathbank-ml-frontend: not running"

.PHONY: access
access:                           ## Show the dashboard URL
	@printf '  %-20s %s\n' 'ML ops dashboard' 'http://localhost:$(WEB_PORT)'

.PHONY: build
build:                           ## Production build (then: npm start)
	npm run build
