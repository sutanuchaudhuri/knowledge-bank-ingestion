# mathbank-graph — local Neo4j Community server storing data on the external APFS drive.
#
# Quick start:
#   cp .env.example .env            # then edit NEO4J_PASSWORD
#   make install init-dirs configure set-password start status
#
# NOTE: `brew upgrade neo4j` / `brew reinstall neo4j` regenerates neo4j.conf from
# the formula defaults, which wipes the external-drive paths. Re-run
# `make configure` after any such upgrade.

-include .env
export

EXTERNAL_DB_ROOT ?= /Volumes/External/Developer/databases
NEO4J_BOLT_PORT  ?= 7687
NEO4J_HTTP_PORT  ?= 7474

NEO4J_PREFIX := $(shell brew --prefix neo4j 2>/dev/null)
NEO4J_BIN    := $(NEO4J_PREFIX)/bin
NEO4J_CONF_FILE := $(NEO4J_PREFIX)/libexec/conf/neo4j.conf
CYPHER_SHELL := $(shell brew --prefix cypher-shell 2>/dev/null)/bin/cypher-shell

NEO4J_DATA := $(EXTERNAL_DB_ROOT)/neo4j/data
NEO4J_LOGS := $(EXTERNAL_DB_ROOT)/neo4j/logs
NEO4J_IMPORT := $(EXTERNAL_DB_ROOT)/neo4j/import
NEO4J_TX := $(EXTERNAL_DB_ROOT)/neo4j/transactions

.DEFAULT_GOAL := help

.PHONY: access
access:                         ## Show local graph connection details (without passwords)
	@printf '  %-20s %s\n' 'Graph Browser (local)' 'http://localhost:$(NEO4J_HTTP_PORT)/browser/' \
	  'Graph Bolt (local)' 'bolt://localhost:$(NEO4J_BOLT_PORT)' \
	  'Graph shell (local)' 'make -C mathbank-graph cypher-shell'

# ── Lifecycle ────────────────────────────────────────────────────────────

.PHONY: install
install:                       ## Install Neo4j (+ cypher-shell, openjdk@21) via Homebrew
	brew install neo4j

.PHONY: init-dirs
init-dirs:                     ## Create the data/logs/import/transactions dirs on the external drive
	mkdir -p "$(NEO4J_DATA)" "$(NEO4J_LOGS)" "$(NEO4J_IMPORT)" "$(NEO4J_TX)"

.PHONY: configure
configure: init-dirs            ## Point neo4j.conf at the external drive (idempotent)
	@if grep -q '^server.directories.data=$(NEO4J_DATA)$$' "$(NEO4J_CONF_FILE)" 2>/dev/null; then \
	  echo "neo4j.conf already points at $(NEO4J_DATA)"; \
	else \
	  sed -i '' \
	    -e 's#^server.directories.import=import$$#server.directories.import=$(NEO4J_IMPORT)#' \
	    -e 's#^server.directories.data=/opt/homebrew/var/neo4j/data$$#server.directories.data=$(NEO4J_DATA)#' \
	    -e 's#^server.directories.logs=/opt/homebrew/var/log/neo4j$$#server.directories.logs=$(NEO4J_LOGS)#' \
	    "$(NEO4J_CONF_FILE)"; \
	  grep -q '^server.directories.transaction.logs.root=' "$(NEO4J_CONF_FILE)" \
	    || echo "server.directories.transaction.logs.root=$(NEO4J_TX)" >> "$(NEO4J_CONF_FILE)"; \
	  echo "neo4j.conf now points at $(EXTERNAL_DB_ROOT)/neo4j"; \
	fi

.PHONY: set-password
set-password:                   ## Set the initial neo4j user password (must run before first start)
	@test -n "$(NEO4J_PASSWORD)" || (echo "Set NEO4J_PASSWORD in .env first" && exit 1)
	@if [ -d "$(NEO4J_DATA)/databases" ]; then \
	  echo "Database already initialized — use cypher-shell to change the password instead:"; \
	  echo "  ALTER CURRENT USER SET PASSWORD FROM 'old' TO 'new';"; \
	else \
	  "$(NEO4J_BIN)/neo4j-admin" dbms set-initial-password "$(NEO4J_PASSWORD)"; \
	fi

.PHONY: start
start:                          ## Start Neo4j as a background daemon — no-op if already running
	@"$(NEO4J_BIN)/neo4j" status >/dev/null 2>&1 && echo "Neo4j already running" || "$(NEO4J_BIN)/neo4j" start

.PHONY: stop
stop:                           ## Stop Neo4j
	"$(NEO4J_BIN)/neo4j" stop

.PHONY: restart
restart: stop start             ## Restart Neo4j

.PHONY: status
status:                         ## Show server status
	"$(NEO4J_BIN)/neo4j" status

.PHONY: console
console:                        ## Run Neo4j in the foreground (for debugging)
	"$(NEO4J_BIN)/neo4j" console

.PHONY: cypher-shell
cypher-shell:                    ## Open an interactive cypher-shell session
	@test -n "$(NEO4J_PASSWORD)" || (echo "Set NEO4J_PASSWORD in .env first" && exit 1)
	"$(CYPHER_SHELL)" -a bolt://localhost:$(NEO4J_BOLT_PORT) -u neo4j -p "$(NEO4J_PASSWORD)"

.PHONY: test
test:                            ## Run a one-shot connectivity query
	@test -n "$(NEO4J_PASSWORD)" || (echo "Set NEO4J_PASSWORD in .env first" && exit 1)
	"$(CYPHER_SHELL)" -a bolt://localhost:$(NEO4J_BOLT_PORT) -u neo4j -p "$(NEO4J_PASSWORD)" \
	  "RETURN 'connected' AS status;"

.PHONY: setup
setup: install configure set-password start  ## One-shot bootstrap: install, configure, set-password, start

# ── Projection ETL (Python) ────────────────────────────────────────────────

.PHONY: etl-venv
etl-venv:                        ## Create the Python venv used by etl/project_from_postgres.py
	uv venv .venv --python 3.11
	uv pip install --python .venv/bin/python "neo4j>=5.23" "psycopg[binary]>=3.2"

.PHONY: project
project:                          ## Project Postgres (mathbank-db) into the Neo4j corpus graph (idempotent)
	@test -n "$(NEO4J_PASSWORD)" || (echo "Set NEO4J_PASSWORD in .env first" && exit 1)
	.venv/bin/python etl/project_from_postgres.py

.PHONY: project-remote
project-remote:                   ## Project the remote Neon Postgres into the remote AuraDB graph (see remote.env)
	GRAPH_ENV_FILE=$(CURDIR)/remote.env .venv/bin/python etl/project_from_postgres.py

.PHONY: destroy
destroy:                        ## Stop server and DELETE the external data directory
	-"$(NEO4J_BIN)/neo4j" stop
	rm -rf "$(NEO4J_DATA)" "$(NEO4J_TX)"

.PHONY: help
help:                           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
