UI_PORT ?= 5186
# Same-origin /v1 proxy target for the Vite dev server (full REST :8000 or local staff API :8019).
SOCRATIC_REST_TARGET ?= http://127.0.0.1:8000
PID_FILE := .server.pid
LOG_FILE := .server.log

.DEFAULT_GOAL := help

.PHONY: help
help:                            ## List targets
	@grep -E '^[a-zA-Z0-9_:-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

.PHONY: install dev test typecheck build e2e e2e-local-auth
install:                         ## npm ci
	npm ci
dev:                             ## Run Vite in the foreground on :$(UI_PORT), proxying /v1 to $(SOCRATIC_REST_TARGET)
	SOCRATIC_REST_TARGET=$(SOCRATIC_REST_TARGET) npm run dev
test:                            ## Vitest unit tests
	npm test
typecheck:                       ## TypeScript check only
	npm run typecheck
build:                           ## Typecheck + production build into dist/ (bundled by the AWS Socratic stack)
	npm run build
e2e:                             ## Playwright prototype regression at 1440/390 (test-only intercepted APIs)
	npm run test:e2e
e2e-local-auth:                  ## Playwright real loopback staff login (own API :8018 + Vite :5188; no AWS)
	npm run test:e2e:local-auth

.PHONY: start stop restart status access
start:                           ## Start Vite in background on :$(UI_PORT) and verify readiness
	@test -f node_modules/vite/bin/vite.js || (echo "ERROR: Vite is missing. Run make install." >&2; exit 1)
	@SOCRATIC_REST_TARGET=$(SOCRATIC_REST_TARGET) bash ../mathbank-scripts/start-service.sh mathbank-socratic-admin \
	  "$(UI_PORT)" "$(PID_FILE)" "$(LOG_FILE)" "http://127.0.0.1:$(UI_PORT)" \
	  node node_modules/vite/bin/vite.js --host 127.0.0.1 --port $(UI_PORT) --strictPort
stop:                            ## Stop the background Vite server (pidfile only; never kills other listeners)
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE); fi
	@echo "mathbank-socratic-admin stopped"
restart: stop start              ## Restart the background Vite server
status:                          ## Is the Studio dev server listening?
	@lsof -ti:$(UI_PORT) >/dev/null 2>&1 && echo "mathbank-socratic-admin: running on :$(UI_PORT)" || echo "mathbank-socratic-admin: not running"
access:                          ## Show the local Studio URL
	@printf '  %-20s %s\n' 'Socratic Studio' 'http://127.0.0.1:$(UI_PORT)  (/v1 -> $(SOCRATIC_REST_TARGET))'
