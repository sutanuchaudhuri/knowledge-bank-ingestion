# mathbank-live — separately deployable realtime classroom (Next.js + Socket.IO on one Node server).
#
# Browser ⇄ Socket.IO (this process) ⇄ mathbank-rest /v1/live/* (the only state owner). The gateway
# relays the append-only session event log to namespaced rooms and replays from last_sequence on reconnect.
#
# Quick start:
#   make -C .. sync-live-env   # writes .env from the root .env (REST URL, admin key, Eleven key …)
#   make install
#   make start                 # http://localhost:5174

LIVE_PORT ?= 5174
PID_FILE := .server.pid
LOG_FILE := .server.log

.DEFAULT_GOAL := help

.PHONY: help
help:                           ## List targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  %-14s %s\n", $$1, $$2}'

.PHONY: access
access:                         ## Show live classroom URLs
	@printf '  %-20s %s\n' 'Live (join/console)' 'http://localhost:$(LIVE_PORT)' \
	  'Live sign-in' 'http://localhost:$(LIVE_PORT)/login' \
	  'Live socket' 'ws://localhost:$(LIVE_PORT)/socket.io'

.PHONY: install
install:                        ## npm install (+ copy ../mathbank-widgets)
	npm install
	@$(MAKE) --no-print-directory sync-widgets

.PHONY: sync-widgets
sync-widgets:                   ## Refresh node_modules/mathbank-widgets from ../mathbank-widgets
	@mkdir -p node_modules/mathbank-widgets
	@rsync -a --delete --exclude node_modules --exclude tests ../mathbank-widgets/ node_modules/mathbank-widgets/

.PHONY: test
test:                           ## Node unit tests (gateway, events) — no services needed
	node --test tests/*.test.mjs

.PHONY: smoke
smoke:                          ## Two-socket realtime smoke against running REST + live (no paid calls)
	node scripts/live-smoke.mjs

.PHONY: dev
dev: sync-widgets               ## Run in the foreground on :$(LIVE_PORT)
	LIVE_PORT=$(LIVE_PORT) node server.mjs

.PHONY: start
start: sync-widgets             ## Start in background on :$(LIVE_PORT) and verify readiness
	@test -f node_modules/next/dist/bin/next || (echo "ERROR: dependencies missing. Run make install in mathbank-live." >&2; exit 1)
	@LIVE_PORT=$(LIVE_PORT) bash ../scripts/start-service.sh mathbank-live "$(LIVE_PORT)" "$(PID_FILE)" "$(LOG_FILE)" \
	  "http://127.0.0.1:$(LIVE_PORT)/login" node server.mjs

.PHONY: stop
stop:                           ## Stop the background server
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE); fi
	@lsof -ti:$(LIVE_PORT) | xargs kill 2>/dev/null || true
	@echo "mathbank-live stopped"

.PHONY: restart
restart: stop start             ## Restart

.PHONY: status
status:                         ## Is the server listening?
	@lsof -ti:$(LIVE_PORT) >/dev/null 2>&1 && echo "mathbank-live: running on :$(LIVE_PORT)" || echo "mathbank-live: not running"

.PHONY: build
build: sync-widgets             ## Production build (then: npm start)
	npx next build
