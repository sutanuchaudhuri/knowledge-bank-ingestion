# Root convenience Makefile — delegates to the per-service Makefiles.
# See mathbank-db/Makefile, mathbank-graph/Makefile, mathbank-rest/Makefile,
# mathbank-agent/Makefile, mathbank-web/Makefile, mathbank-live/Makefile for details.
# Shared UI package: mathbank-widgets/ (no Makefile; web/live copy it via sync-widgets).
#
# Individual service lifecycle:  make <svc>-start | <svc>-stop | <svc>-restart | <svc>-status
#   where <svc> is one of: db, graph, rest, agent, web, live
# Whole-stack lifecycle:         make up | make down | make status
# rest/agent/web/live "start" checks HTTP readiness, restarts its own unhealthy process,
# and refuses ports held by any other process. make up = remote Neon/AuraDB only.
# Tests:                         make test-unit | make smoke | make e2e | make e2e-llm (paid)
# New pieces from scratch:       make sync-env && make setup && make migrate-live-fluid-remote && make up
#
# ── Extra/parallel services (independent of the core 4 above; see README.md for what
#    each one is and how it fits) ──────────────────────────────────────────────────
#   mcp            mathbank-mcp-competitions  — standalone FastMCP server (stdio), no daemon
#   manim          mathbank-manim-studio      — research + video-render agents, :8020
#   ml-training    mathbank-ml-training       — offline notebooks, no daemon (make ml-training-notebook)
#   ml-inference   mathbank-ml-inference      — FastAPI ML service, :8010
#   ml-frontend    mathbank-ml-frontend       — ML-ops dashboard, :5175
#   geometry       mathbank-geometry-engine   — deterministic geometry compiler, library only
#   neural-geom    mathbank-neural-geometry   — neural-symbolic compiler on top of geometry, library only
#   ingestion      mathbank-data-ingestion    — corpus crawl/classify/export pipeline, CLI only
# Same per-service pattern as the core 4: make <svc>-install | <svc>-start | <svc>-stop |
#   <svc>-restart | <svc>-status (daemon-backed services only) | <svc>-test (where real tests exist)
# Aggregate:                     make up-extra | make down-extra | make status-extra | make access-extra

.DEFAULT_GOAL := help

ROUTE_PYTHON ?= $(CURDIR)/mathbank-rest/.venv/bin/python
ROUTE_MODEL ?= qwen2.5:7b
ROUTE_CRITIC ?= 0
ROUTE_CRITIC_MODEL ?= llama3.2:3b
ROUTE_CONTEXT ?= 16384
ROUTE_NUM_PREDICT ?= 4096
ROUTE_LOG_ROOT ?= /Volumes/External/Developer/databases/logs/ollama-routes
ROUTE_LOG_DIR ?= $(ROUTE_LOG_ROOT)/$(shell hostname)-$(shell date -u +%Y%m%dT%H%M%SZ)
ROUTE_ARGS = --model "$(ROUTE_MODEL)" --context "$(ROUTE_CONTEXT)" --num-predict "$(ROUTE_NUM_PREDICT)" --log-dir "$(ROUTE_LOG_DIR)" $(if $(filter 1 true yes,$(ROUTE_CRITIC)),--critic-model "$(ROUTE_CRITIC_MODEL)",) $(if $(ROUTE_WORKERS),--workers "$(ROUTE_WORKERS)",) $(if $(ROUTE_LIMIT),--limit "$(ROUTE_LIMIT)",) $(if $(ROUTE_APPROVE_BY),--approve-by "$(ROUTE_APPROVE_BY)",) $(if $(filter 1,$(ROUTE_RETRY_FAILED)),--retry-failed,)

.PHONY: routes-plan routes-prepare routes-ingest routes-migrate routes-status routes-progress routes-test
routes-plan:                    ## Discover OS/RAM/CPU/model and print safe local worker ceiling; no inference or SQL writes
	@cd mathbank-rest && "$(ROUTE_PYTHON)" -m mathbank_rest.route_batch plan $(ROUTE_ARGS)

routes-ingest:                  ## Local Ollama mandatory-enrichment pipeline; resource-sized, shared multi-machine queue
	@cd mathbank-rest && "$(ROUTE_PYTHON)" -m mathbank_rest.route_batch run $(ROUTE_ARGS)

routes-prepare:                 ## Install missing Ollama model(s), then check safe resources; no inference or database writes
	@cd mathbank-rest && "$(ROUTE_PYTHON)" -m mathbank_rest.route_batch prepare $(ROUTE_ARGS)

routes-migrate:                 ## Apply distributed queue migration 028/029 once to configured PostgreSQL (requires 026/027)
	@cd mathbank-rest && "$(ROUTE_PYTHON)" -m mathbank_rest.route_batch migrate --log-dir "$(ROUTE_LOG_DIR)"

routes-status:                  ## Show shared queue counts for current compiler version; no generation
	@cd mathbank-rest && "$(ROUTE_PYTHON)" -m mathbank_rest.route_batch status --log-dir "$(ROUTE_LOG_DIR)" $(if $(ROUTE_RUN_ID),--run-id "$(ROUTE_RUN_ID)",)

routes-progress: routes-status  ## Check shared completion/failures/leases and latest machine runs (ROUTE_RUN_ID optional)

routes-test:                    ## Run targeted route/compiler/resource/queue tests; DB checks opt-in with ROUTE_DB_TESTS=1
	@cd mathbank-rest && "$(ROUTE_PYTHON)" -m pytest -q tests/test_route_contracts.py tests/test_route_compiler.py tests/test_route_ollama.py tests/test_route_enrichment.py tests/test_route_batch.py tests/test_route_critic.py tests/test_tutoring_routes.py


.PHONY: sync-env
sync-env:                        ## Distribute the shared root .env into every service's own .env (backs up existing files first)
	@bash sync-env.sh

.PHONY: sync-openai-key
sync-openai-key:                  ## Copy OPENAI_API_KEY from root .env only to service env files, without printing it
	@node mathbank-scripts/sync-openai-key.mjs

.PHONY: check-openai
check-openai:                     ## Check file-only OpenAI auth; CHAT=1 also makes a small paid LiteLLM model check
	@mathbank-agent/.venv/bin/python mathbank-scripts/check-openai.py $(if $(filter 1,$(CHAT)),--chat,)

.PHONY: sync-eleven-key
sync-eleven-key:                  ## Copy ELEVEN_API_KEY (ElevenLabs voice) from root .env only to mathbank-web/.env and mathbank-live/.env, hidden
	@node mathbank-scripts/sync-eleven-key.mjs

.PHONY: check-eleven
check-eleven:                     ## Check ElevenLabs auth (free models/voices); TTS=1 also synthesises one tiny paid phrase
	@node mathbank-scripts/check-eleven.mjs $(if $(filter 1,$(TTS)),--tts,)

.PHONY: sync-live-env
sync-live-env:                    ## Write mathbank-live/.env (REST URL, admin key/login, session secret, ELEVEN key) from root .env only, hidden
	@node mathbank-scripts/sync-live-env.mjs

.PHONY: sync-neon-env
sync-neon-env:                   ## Copy Neon production S3 + AI Gateway settings from root .env to server env files, hidden
	@node mathbank-scripts/sync-neon-env.mjs

.PHONY: migrate-multimodal-remote
migrate-multimodal-remote:       ## Apply multimodal evidence + instructional artifact migrations 021/022 to configured Neon
	$(MAKE) -C mathbank-db migrate-multimodal-remote

.PHONY: sync-keys
sync-keys: sync-openai-key sync-eleven-key sync-live-env sync-neon-env  ## Sync provider/Neon credentials from root .env (server-only)

.PHONY: setup
setup:                           ## Check/create .env files, flag missing secrets (OPENAI_API_KEY etc.), install every venv/node_modules not already present
	@bash mathbank-scripts/setup.sh

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
rest-start:                      ## Start mathbank-rest on :8000 and verify HTTP readiness
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
agent-start:                     ## Start mathbank-agent on :8001 and verify HTTP readiness
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
web-start:                       ## Start mathbank-web on :5173 and verify HTTP readiness
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

.PHONY: live-install
live-install:                     ## Install the realtime Socket.IO live-classroom deployable's dependencies
	$(MAKE) -C mathbank-live install

.PHONY: live-run
live-run:                         ## Run mathbank-live in the foreground on :5174 (Ctrl-C to stop)
	$(MAKE) -C mathbank-live dev

.PHONY: live-start
live-start:                       ## Start mathbank-live (Socket.IO gateway + live classroom UI) on :5174
	$(MAKE) -C mathbank-live start

.PHONY: live-stop
live-stop:                        ## Stop mathbank-live
	$(MAKE) -C mathbank-live stop

.PHONY: live-restart
live-restart:                     ## Restart mathbank-live
	$(MAKE) -C mathbank-live restart

.PHONY: live-status
live-status:                      ## Show whether mathbank-live is running
	$(MAKE) -C mathbank-live status


# ── Extra/parallel services (see README.md for the role of each) ───────────────────

.PHONY: mcp-install
mcp-install:                      ## Install mathbank-mcp-competitions (standalone FastMCP server)
	$(MAKE) -C mathbank-mcp-competitions install

.PHONY: mcp-test
mcp-test:                         ## Run mathbank-mcp-competitions's test suite
	$(MAKE) -C mathbank-mcp-competitions test

.PHONY: mcp-demo
mcp-demo:                         ## Run the bundled OpenAI agent demo against the MCP server
	$(MAKE) -C mathbank-mcp-competitions demo

.PHONY: infra-install
infra-install:                     ## Install the AWS CDK deployment project's venv (requirements/62-63)
	$(MAKE) -C mathbank-infra-aws install

.PHONY: infra-bootstrap
infra-bootstrap:                   ## One-time: bootstrap the AWS account/region for CDK
	$(MAKE) -C mathbank-infra-aws bootstrap

.PHONY: infra-synth
infra-synth:                       ## Validate the CDK stacks without deploying
	$(MAKE) -C mathbank-infra-aws synth

.PHONY: infra-deploy
infra-deploy:                      ## Build + deploy every service to AWS Lambda; override STACKS=MathBankXStack to target one (redeploy = rerun this)
	$(MAKE) -C mathbank-infra-aws deploy STACKS="$(STACKS)"

.PHONY: infra-diff
infra-diff:                        ## Show what infra-deploy would change, without deploying
	$(MAKE) -C mathbank-infra-aws diff

.PHONY: infra-destroy
infra-destroy:                     ## Tear down every deployed AWS stack (stops all charges for this project)
	$(MAKE) -C mathbank-infra-aws destroy

.PHONY: infra-destroy-one
infra-destroy-one:                 ## "Pause"/stop one service: make infra-destroy-one STACK=MathBankManimStudioStack
	$(MAKE) -C mathbank-infra-aws destroy-one STACK="$(STACK)"

.PHONY: infra-outputs
infra-outputs:                     ## Print every deployed Function URL and stack output; override STACK=MathBankXStack for just one
	$(MAKE) -C mathbank-infra-aws outputs STACK="$(STACK)"

.PHONY: infra-colima-start
infra-colima-start:                ## Start the local Docker-compatible runtime (colima) needed to build images
	$(MAKE) -C mathbank-infra-aws colima-start

.PHONY: infra-colima-stop
infra-colima-stop:                 ## Stop the local Docker-compatible runtime (colima) when not building/deploying
	$(MAKE) -C mathbank-infra-aws colima-stop

.PHONY: manim-install
manim-install:                     ## Install mathbank-manim-studio (research + video-render agents)
	$(MAKE) -C mathbank-manim-studio install

.PHONY: manim-start
manim-start:                       ## Start mathbank-manim-studio on :8020 and verify HTTP readiness
	$(MAKE) -C mathbank-manim-studio start

.PHONY: manim-stop
manim-stop:                        ## Stop the mathbank-manim-studio background daemon
	$(MAKE) -C mathbank-manim-studio stop

.PHONY: manim-restart
manim-restart:                     ## Restart the mathbank-manim-studio background daemon
	$(MAKE) -C mathbank-manim-studio restart

.PHONY: manim-status
manim-status:                      ## Show whether mathbank-manim-studio is running
	$(MAKE) -C mathbank-manim-studio status

.PHONY: manim-test
manim-test:                        ## Run mathbank-manim-studio's test suite (real OpenAI + manim render, ~30s)
	$(MAKE) -C mathbank-manim-studio test

.PHONY: exam-agent-install
exam-agent-install:                ## Install mathbank-exam-agent (requirements/64 — Strands SDK mock-exam agent)
	$(MAKE) -C mathbank-exam-agent install

.PHONY: exam-agent-test
exam-agent-test:                   ## Run mathbank-exam-agent's unit test suite (no network/LLM calls)
	$(MAKE) -C mathbank-exam-agent test

.PHONY: exam-agent-run
exam-agent-run:                    ## Run mathbank-exam-agent locally on :8030 (needs mathbank-rest already running)
	$(MAKE) -C mathbank-exam-agent run

.PHONY: ml-training-install
ml-training-install:               ## Install mathbank-ml-training (offline notebooks; scaffolded, requirements/54-55)
	$(MAKE) -C mathbank-ml-training install

.PHONY: ml-training-notebook
ml-training-notebook:              ## Launch Jupyter Lab over mathbank-ml-training's notebooks
	$(MAKE) -C mathbank-ml-training notebook

.PHONY: ml-inference-install
ml-inference-install:              ## Install mathbank-ml-inference (ML prediction/recommendation FastAPI service)
	$(MAKE) -C mathbank-ml-inference install

.PHONY: ml-inference-start
ml-inference-start:                ## Start mathbank-ml-inference on :8010 and verify HTTP readiness
	$(MAKE) -C mathbank-ml-inference start

.PHONY: ml-inference-stop
ml-inference-stop:                 ## Stop the mathbank-ml-inference background daemon
	$(MAKE) -C mathbank-ml-inference stop

.PHONY: ml-inference-restart
ml-inference-restart:              ## Restart the mathbank-ml-inference background daemon
	$(MAKE) -C mathbank-ml-inference restart

.PHONY: ml-inference-status
ml-inference-status:               ## Show whether mathbank-ml-inference is running
	$(MAKE) -C mathbank-ml-inference status

.PHONY: ml-frontend-install
ml-frontend-install:               ## Install mathbank-ml-frontend (ML-ops dashboard)
	$(MAKE) -C mathbank-ml-frontend install

.PHONY: ml-frontend-start
ml-frontend-start:                 ## Start mathbank-ml-frontend on :5175 and verify HTTP readiness
	$(MAKE) -C mathbank-ml-frontend start

.PHONY: ml-frontend-stop
ml-frontend-stop:                  ## Stop the mathbank-ml-frontend background daemon
	$(MAKE) -C mathbank-ml-frontend stop

.PHONY: ml-frontend-restart
ml-frontend-restart:               ## Restart the mathbank-ml-frontend background daemon
	$(MAKE) -C mathbank-ml-frontend restart

.PHONY: ml-frontend-status
ml-frontend-status:                ## Show whether mathbank-ml-frontend is running
	$(MAKE) -C mathbank-ml-frontend status

.PHONY: geometry-install
geometry-install:                  ## Install mathbank-geometry-engine (deterministic geometry scene compiler, library only)
	$(MAKE) -C mathbank-geometry-engine install

.PHONY: geometry-test
geometry-test:                     ## Run mathbank-geometry-engine's test suite
	$(MAKE) -C mathbank-geometry-engine test

.PHONY: neural-geom-install
neural-geom-install:               ## Install mathbank-neural-geometry (neural-symbolic compiler, library only)
	$(MAKE) -C mathbank-neural-geometry install

.PHONY: neural-geom-test
neural-geom-test:                  ## Run mathbank-neural-geometry's test suite
	$(MAKE) -C mathbank-neural-geometry test

.PHONY: ingestion-install
ingestion-install:                 ## Install mathbank-data-ingestion (corpus crawl/classify/export pipeline, CLI only)
	$(MAKE) -C mathbank-data-ingestion install

.PHONY: ingestion-test
ingestion-test:                    ## Run mathbank-data-ingestion's test suite
	$(MAKE) -C mathbank-data-ingestion test

.PHONY: up-extra
up-extra: manim-start ml-inference-start ml-frontend-start  ## Start the extra standalone HTTP services (manim-studio, ml-inference, ml-frontend)
	@$(MAKE) --no-print-directory access-extra

.PHONY: down-extra
down-extra:                        ## Stop the extra standalone HTTP services
	-$(MAKE) -C mathbank-manim-studio stop
	-$(MAKE) -C mathbank-ml-inference stop
	-$(MAKE) -C mathbank-ml-frontend stop

.PHONY: status-extra
status-extra:                      ## Show status of the extra standalone HTTP services
	-$(MAKE) -C mathbank-manim-studio status
	-$(MAKE) -C mathbank-ml-inference status
	-$(MAKE) -C mathbank-ml-frontend status

.PHONY: access-extra
access-extra:                      ## Show URLs for the extra standalone HTTP services
	@printf '\nExtra/parallel services\n\n'
	@$(MAKE) --no-print-directory -s -C mathbank-manim-studio access
	@$(MAKE) --no-print-directory -s -C mathbank-ml-inference access
	@$(MAKE) --no-print-directory -s -C mathbank-ml-frontend access
	@$(MAKE) --no-print-directory -s -C mathbank-mcp-competitions access
	@printf '\n'


.PHONY: migrate-live-fluid-remote
migrate-live-fluid-remote:        ## Apply migration 020 (live sessions, activities, widget specs, authoring plans) to Neon; idempotent
	$(MAKE) -C mathbank-db migrate-live-fluid-remote

.PHONY: widgets-sync
widgets-sync:                     ## Copy ../mathbank-widgets into web and live node_modules (after editing the shared package)
	$(MAKE) -C mathbank-web sync-widgets
	$(MAKE) -C mathbank-live sync-widgets

.PHONY: test-unit
test-unit:                        ## Node unit tests: web + mathbank-widgets, then live gateway/events (no services, no paid calls)
	$(MAKE) -C mathbank-web test
	$(MAKE) -C mathbank-live test

.PHONY: smoke
smoke:                            ## Two-socket live-classroom smoke against the running REST + live (no paid calls)
	$(MAKE) -C mathbank-live smoke

.PHONY: e2e
e2e:                              ## Playwright regression against the running stack incl. live :5174 (no paid calls)
	$(MAKE) -C mathbank-web e2e

.PHONY: e2e-llm
e2e-llm:                          ## Playwright suite including @llm specs (small PAID OpenAI calls)
	$(MAKE) -C mathbank-web e2e-llm

.PHONY: bootstrap
bootstrap:                        ## Single-command rebuild of the ENTIRE stack on a fresh machine (see GOTCHAS.md)
	$(MAKE) -C mathbank-db bootstrap
	$(MAKE) -C mathbank-graph setup
	$(MAKE) -C mathbank-graph etl-venv
	$(MAKE) -C mathbank-graph project
	$(MAKE) rest-install
	$(MAKE) agent-install
	$(MAKE) web-install
	$(MAKE) live-install
	@echo "Full stack bootstrapped. Start everything with: make up"

.PHONY: up
up: up-app                        ## Sync keys and start REST/agent/web/live against remote Neon/AuraDB (no local databases)

.PHONY: up-local-db
up-local-db: sync-keys db-start graph-start rest-start agent-start web-start live-start  ## Local stack; local Postgres/Neo4j failures are fatal
	@$(MAKE) --no-print-directory access-local

.PHONY: up-app
up-app: sync-keys                 ## Sync keys and start REST/agent/web/live only; use configured Neon/AuraDB
	$(MAKE) -C mathbank-rest start
	$(MAKE) -C mathbank-agent start
	$(MAKE) -C mathbank-web start
	$(MAKE) -C mathbank-live start
	@$(MAKE) --no-print-directory access

.PHONY: up-windows
up-windows: sync-keys              ## Open one real Terminal.app window per core service (foreground, live logs; macOS only)
	@bash mathbank-scripts/open-terminal-windows.sh

.PHONY: up-windows-all
up-windows-all: sync-keys          ## Same as up-windows, plus manim-studio/ml-inference/ml-frontend in their own windows
	@bash mathbank-scripts/open-terminal-windows.sh --all

REMOTE_ENV := mathbank-graph/remote.env

.PHONY: access
access:                           ## Show web/API URLs and the remote Neon/AuraDB details (no passwords, no restart)
	@printf '\nMathBank access\n\n'
	@$(MAKE) --no-print-directory -s -C mathbank-web access
	@$(MAKE) --no-print-directory -s -C mathbank-live access
	@$(MAKE) --no-print-directory -s -C mathbank-rest access
	@$(MAKE) --no-print-directory -s -C mathbank-agent access
	@$(MAKE) --no-print-directory -s access-remote
	@printf '\n  Passwords are never displayed. Status: make status | Again: make access\n'
	@printf '  Extra/parallel services (manim-studio, ml-*, mcp): make access-extra\n\n'

.PHONY: access-remote
access-remote:                    ## Show remote Neon Postgres / Neo4j AuraDB endpoints from mathbank-graph/remote.env (no passwords)
	@if [ ! -f $(REMOTE_ENV) ]; then printf '  %-20s %s\n' 'Remote databases' 'not configured ($(REMOTE_ENV) missing)'; exit 0; fi; \
	  set -a; . ./$(REMOTE_ENV); set +a; \
	  printf '  %-20s %s\n' \
	    'Postgres (Neon)' "$${NEON_PG_HOST:-?}:$${NEON_PG_PORT:-5432} / database: $${NEON_PG_DATABASE:-?} / user: $${NEON_PG_USER:-?}" \
	    'Postgres shell' 'make psql-remote' \
	    'Neon console' 'https://console.neon.tech' \
	    'Graph (AuraDB)' "$${NEO4J_URI:-?} / database: $${NEO4J_DATABASE:-neo4j} / user: $${NEO4J_USERNAME:-?}" \
	    'Aura console' 'https://console.neo4j.io'

.PHONY: access-local
access-local:                     ## Show web/API URLs and LOCAL Postgres/Neo4j details (only for make up-local-db)
	@printf '\nMathBank access (local databases)\n\n'
	@$(MAKE) --no-print-directory -s -C mathbank-web access
	@$(MAKE) --no-print-directory -s -C mathbank-live access
	@$(MAKE) --no-print-directory -s -C mathbank-rest access
	@$(MAKE) --no-print-directory -s -C mathbank-agent access
	@$(MAKE) --no-print-directory -s -C mathbank-graph access
	@$(MAKE) --no-print-directory -s -C mathbank-db access
	@printf '\n  Passwords are never displayed.\n\n'

.PHONY: psql-remote
psql-remote:                      ## Interactive psql on the remote Neon database (credentials from mathbank-graph/remote.env)
	@set -a; . ./$(REMOTE_ENV); set +a; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" psql "host=$$NEON_PG_HOST port=$${NEON_PG_PORT:-5432} dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require"

.PHONY: down
down:                             ## Stop REST/agent/web/live (local databases: make down-local-db)
	-$(MAKE) -C mathbank-live stop
	-$(MAKE) -C mathbank-web stop
	-$(MAKE) -C mathbank-agent stop
	-$(MAKE) -C mathbank-rest stop

.PHONY: status
status:                           ## Show status of every service
	-$(MAKE) -C mathbank-rest status
	-$(MAKE) -C mathbank-agent status
	-$(MAKE) -C mathbank-web status
	-$(MAKE) -C mathbank-live status

.PHONY: down-local-db
down-local-db:                    ## Stop local Postgres and Neo4j (only used by make up-local-db)
	-$(MAKE) -C mathbank-db stop
	-$(MAKE) -C mathbank-graph stop

.PHONY: help
help:                             ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
