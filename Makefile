# Root convenience Makefile — delegates to the per-service Makefiles.
# See mathbank-db/Makefile, mathbank-graph/Makefile, mathbank-rest/Makefile,
# mathbank-agent/Makefile, mathbank-web/Makefile for details.
#
# Individual service lifecycle:  make <svc>-start | <svc>-stop | <svc>-restart | <svc>-status
#   where <svc> is one of: db, graph, rest, agent, web
# Whole-stack lifecycle:         make up | make down | make status
# rest/agent/web "start" runs as a background daemon and auto-kills anything
# already bound to its port first (see each sub-project's Makefile).

.DEFAULT_GOAL := help

.PHONY: sync-env
sync-env:                        ## Distribute the shared root .env into every service's own .env (backs up existing files first)
	@bash sync-env.sh

.PHONY: setup
setup:                           ## Check/create .env files, flag missing secrets (OPENAI_API_KEY etc.), install every venv/node_modules not already present
	@bash scripts/setup.sh

.PHONY: db-setup
db-setup:                       ## Bootstrap Postgres on the external drive (install+init+start+create-db)
	$(MAKE) -C mathbank-db setup

.PHONY: db-start
db-start:                       ## Start Postgres
	$(MAKE) -C mathbank-db start

.PHONY: db-stop
db-stop:                        ## Stop Postgres
	$(MAKE) -C mathbank-db stop

.PHONY: db-status
db-status:                      ## Show Postgres status
	$(MAKE) -C mathbank-db status

.PHONY: graph-setup
graph-setup:                    ## Bootstrap Neo4j on the external drive (install+configure+set-password+start)
	$(MAKE) -C mathbank-graph setup

.PHONY: graph-start
graph-start:                    ## Start Neo4j
	$(MAKE) -C mathbank-graph start

.PHONY: graph-stop
graph-stop:                     ## Stop Neo4j
	$(MAKE) -C mathbank-graph stop

.PHONY: graph-status
graph-status:                   ## Show Neo4j status
	$(MAKE) -C mathbank-graph status

.PHONY: rest-install
rest-install:                    ## Install the FastAPI service's Python env
	$(MAKE) -C mathbank-rest install

.PHONY: rest-run
rest-run:                        ## Run mathbank-rest in the foreground on :8000 (--reload, Ctrl-C to stop)
	$(MAKE) -C mathbank-rest run

.PHONY: rest-start
rest-start:                      ## Start mathbank-rest as a background daemon on :8000 (kills whatever holds the port)
	$(MAKE) -C mathbank-rest start

.PHONY: rest-stop
rest-stop:                       ## Stop the mathbank-rest background daemon
	$(MAKE) -C mathbank-rest stop

.PHONY: rest-restart
rest-restart:                    ## Restart the mathbank-rest background daemon
	$(MAKE) -C mathbank-rest restart

.PHONY: rest-status
rest-status:                     ## Show whether mathbank-rest is running
	$(MAKE) -C mathbank-rest status

.PHONY: test-connectivity
test-connectivity:                ## Ping Postgres + Neo4j from mathbank-rest
	$(MAKE) -C mathbank-rest test-connectivity

.PHONY: agent-install
agent-install:                    ## Install the Google ADK agentic backend's Python env
	$(MAKE) -C mathbank-agent install

.PHONY: agent-run
agent-run:                        ## Run mathbank-agent in the foreground on :8001 (Ctrl-C to stop)
	$(MAKE) -C mathbank-agent run

.PHONY: agent-start
agent-start:                      ## Start mathbank-agent as a background daemon on :8001 (kills whatever holds the port)
	$(MAKE) -C mathbank-agent start

.PHONY: agent-stop
agent-stop:                       ## Stop the mathbank-agent background daemon
	$(MAKE) -C mathbank-agent stop

.PHONY: agent-restart
agent-restart:                    ## Restart the mathbank-agent background daemon
	$(MAKE) -C mathbank-agent restart

.PHONY: agent-status
agent-status:                     ## Show whether mathbank-agent is running
	$(MAKE) -C mathbank-agent status

.PHONY: web-install
web-install:                      ## Install the React frontend's dependencies
	$(MAKE) -C mathbank-web install

.PHONY: web-run
web-run:                          ## Run mathbank-web in the foreground on :5173 (Ctrl-C to stop)
	$(MAKE) -C mathbank-web dev

.PHONY: web-start
web-start:                        ## Start mathbank-web as a background daemon on :5173 (kills whatever holds the port)
	$(MAKE) -C mathbank-web start

.PHONY: web-stop
web-stop:                         ## Stop the mathbank-web background daemon
	$(MAKE) -C mathbank-web stop

.PHONY: web-restart
web-restart:                      ## Restart the mathbank-web background daemon
	$(MAKE) -C mathbank-web restart

.PHONY: web-status
web-status:                       ## Show whether mathbank-web is running
	$(MAKE) -C mathbank-web status

.PHONY: bootstrap
bootstrap:                        ## Single-command rebuild of the ENTIRE stack on a fresh machine (see GOTCHAS.md)
	$(MAKE) -C mathbank-db bootstrap
	$(MAKE) -C mathbank-graph setup
	$(MAKE) -C mathbank-graph etl-venv
	$(MAKE) -C mathbank-graph project
	$(MAKE) rest-install
	$(MAKE) agent-install
	$(MAKE) web-install
	@echo "Full stack bootstrapped. Start everything with: make up"

.PHONY: up
up:                               ## Start every service. Local Postgres/Neo4j (db/graph) are best-effort — harmless to skip if your .env points at remote Neon/AuraDB (the common case after `make sync-env`)
	-$(MAKE) -C mathbank-db start
	-$(MAKE) -C mathbank-graph start
	$(MAKE) -C mathbank-rest start
	$(MAKE) -C mathbank-agent start
	$(MAKE) -C mathbank-web start
	@$(MAKE) --no-print-directory access

.PHONY: up-local-db
up-local-db: db-start graph-start rest-start agent-start web-start  ## Same as `up`, but local Postgres/Neo4j failures are fatal — use this only if you intend to run a fully local (non-Neon/AuraDB) stack
	@$(MAKE) --no-print-directory access

.PHONY: access
access:                           ## Show web/API URLs and local database connection details (no restart)
	@printf '\nMathBank access\n\n'
	@$(MAKE) --no-print-directory -s -C mathbank-web access
	@$(MAKE) --no-print-directory -s -C mathbank-rest access
	@$(MAKE) --no-print-directory -s -C mathbank-agent access
	@$(MAKE) --no-print-directory -s -C mathbank-graph access
	@$(MAKE) --no-print-directory -s -C mathbank-db access
	@printf '\n  Database addresses above are LOCAL and require running local services.\n'
	@printf '  The app may instead use Neon/AuraDB configured in each service .env.\n'
	@printf '  Passwords are not displayed; use your configured database credentials.\n'
	@printf '  Check running services: make status | Show this again: make access\n\n'

.PHONY: down
down:                             ## Stop every service
	-$(MAKE) -C mathbank-web stop
	-$(MAKE) -C mathbank-agent stop
	-$(MAKE) -C mathbank-rest stop
	-$(MAKE) -C mathbank-db stop
	-$(MAKE) -C mathbank-graph stop

.PHONY: status
status:                           ## Show status of every service
	-$(MAKE) -C mathbank-db status
	-$(MAKE) -C mathbank-graph status
	-$(MAKE) -C mathbank-rest status
	-$(MAKE) -C mathbank-agent status
	-$(MAKE) -C mathbank-web status

.PHONY: help
help:                             ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
