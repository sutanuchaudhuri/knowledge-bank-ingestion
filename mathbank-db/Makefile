# mathbank-db — local PostgreSQL 16 cluster stored on the external APFS drive.
#
# Quick start:
#   cp .env.example .env            # then edit the passwords
#   make install init start create-db status
#
# All state lives under $(EXTERNAL_DB_ROOT)/postgres$(PG_VERSION)/ — nothing is
# written inside this repo, so `make destroy` only ever touches the external drive.

-include .env
export

PG_VERSION       ?= 16
EXTERNAL_DB_ROOT ?= /Volumes/External/Developer/databases
PG_PORT          ?= 5433
PG_SUPERUSER     ?= mathbank_admin
APP_DB           ?= mathbank
APP_USER         ?= mathbank_app

PG_PREFIX := $(shell brew --prefix postgresql@$(PG_VERSION) 2>/dev/null)
PG_BIN    := $(PG_PREFIX)/bin
PGDATA    := $(EXTERNAL_DB_ROOT)/postgres$(PG_VERSION)/data
PG_LOG    := $(EXTERNAL_DB_ROOT)/postgres$(PG_VERSION)/postgres.log

.DEFAULT_GOAL := help

.PHONY: access
access:                         ## Show local Postgres connection details (without passwords)
	@printf '  %-20s %s\n' 'Postgres (local)' 'localhost:$(PG_PORT) / database: $(APP_DB) / user: $(APP_USER)' \
	  'Postgres shell' 'make -C mathbank-db psql (local admin)'

# ── Lifecycle ────────────────────────────────────────────────────────────

.PHONY: install
install:                       ## Install PostgreSQL via Homebrew
	brew install postgresql@$(PG_VERSION)

.PHONY: install-pgvector
install-pgvector:               ## Build+install pgvector from source (brew's bottle only targets pg@17/18)
	rm -rf /tmp/build/pgvector
	mkdir -p /tmp/build
	git clone --branch v0.8.0 --depth 1 https://github.com/pgvector/pgvector.git /tmp/build/pgvector
	cd /tmp/build/pgvector && \
	  FIXED_CPPFLAGS=$$($(PG_BIN)/pg_config --cppflags | sed "s#MacOSX26.sdk#$$(basename $$(xcrun --show-sdk-path))#") && \
	  FIXED_LDFLAGS=$$($(PG_BIN)/pg_config --ldflags | sed "s#MacOSX26.sdk#$$(basename $$(xcrun --show-sdk-path))#") && \
	  make PG_CONFIG=$(PG_BIN)/pg_config CPPFLAGS="$$FIXED_CPPFLAGS" LDFLAGS="$$FIXED_LDFLAGS"
	cp /tmp/build/pgvector/vector.dylib "$(PG_PREFIX)/lib/postgresql/vector.dylib"
	cp /tmp/build/pgvector/sql/vector--*.sql "$(PG_PREFIX)/share/postgresql@$(PG_VERSION)/extension/"
	cp /tmp/build/pgvector/vector.control "$(PG_PREFIX)/share/postgresql@$(PG_VERSION)/extension/"
	grep -q '^trusted' "$(PG_PREFIX)/share/postgresql@$(PG_VERSION)/extension/vector.control" \
	  || echo "trusted = true" >> "$(PG_PREFIX)/share/postgresql@$(PG_VERSION)/extension/vector.control"
	@echo "pgvector installed for postgresql@$(PG_VERSION) (no restart needed — run 'make migrate-vector' now)."

.PHONY: check-pgvector
check-pgvector:                 ## Verify pgvector is installed + loadable (diagnostic, see GOTCHAS.md)
	@test -f "$(PG_PREFIX)/lib/postgresql/vector.dylib" || (echo "vector.dylib missing — run: make install-pgvector" && exit 1)
	@test -f "$(PG_PREFIX)/share/postgresql@$(PG_VERSION)/extension/vector.control" || (echo "vector.control missing — run: make install-pgvector" && exit 1)
	@grep -q '^trusted = true' "$(PG_PREFIX)/share/postgresql@$(PG_VERSION)/extension/vector.control" \
	  || (echo "vector.control missing 'trusted = true' — run: make install-pgvector" && exit 1)
	@echo "pgvector files OK. Verifying CREATE EXTENSION as app owner..."
	@PGPASSWORD="$(APP_DB_PASSWORD)" "$(PG_BIN)/psql" -h 127.0.0.1 -p $(PG_PORT) -U "$(APP_USER)" -d $(APP_DB) \
	  -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extversion FROM pg_extension WHERE extname='vector';"

.PHONY: init
init:                          ## initdb a fresh cluster on the external drive (idempotent)
	@test -n "$(PG_SUPERUSER_PASSWORD)" || (echo "Set PG_SUPERUSER_PASSWORD in .env first (see .env.example)" && exit 1)
	@if [ -f "$(PGDATA)/PG_VERSION" ]; then \
	  echo "Cluster already initialized at $(PGDATA)"; \
	else \
	  mkdir -p "$(PGDATA)" && chmod 700 "$(PGDATA)" && \
	  pwfile=$$(mktemp) && echo "$(PG_SUPERUSER_PASSWORD)" > "$$pwfile" && \
	  LC_ALL="en_US.UTF-8" "$(PG_BIN)/initdb" --locale=en_US.UTF-8 -E UTF-8 \
	    -U "$(PG_SUPERUSER)" --pwfile="$$pwfile" -D "$(PGDATA)" && \
	  rm -f "$$pwfile" && \
	  $(MAKE) harden-hba; \
	fi

.PHONY: harden-hba
harden-hba:                    ## Require scram-sha-256 for TCP connections (local socket stays trust)
	@sed -i '' \
	  -e 's/^host[[:space:]]\+all[[:space:]]\+all[[:space:]]\+127\.0\.0\.1\/32[[:space:]]\+trust/host    all             all             127.0.0.1\/32            scram-sha-256/' \
	  -e 's/^host[[:space:]]\+all[[:space:]]\+all[[:space:]]\+::1\/128[[:space:]]\+trust/host    all             all             ::1\/128                 scram-sha-256/' \
	  "$(PGDATA)/pg_hba.conf"
	@echo "pg_hba.conf hardened (host connections now require scram-sha-256)"

.PHONY: start
start:                          ## Start Postgres (background) on $(PG_PORT) — no-op if already running
	@test -x "$(PG_BIN)/pg_ctl" || (echo "Local PostgreSQL $(PG_VERSION) is not installed. For Neon use root 'make up-app'; for local DB run 'make install' and configure/init the cluster." >&2; exit 1)
	@if "$(PG_BIN)/pg_ctl" -D "$(PGDATA)" status >/dev/null 2>&1; then \
	  echo "Postgres already running on $(PGDATA)"; \
	else \
	  LC_ALL="en_US.UTF-8" "$(PG_BIN)/pg_ctl" -D "$(PGDATA)" -l "$(PG_LOG)" -o "-p $(PG_PORT)" start; \
	fi

.PHONY: stop
stop:                           ## Stop Postgres
	"$(PG_BIN)/pg_ctl" -D "$(PGDATA)" stop -m fast

.PHONY: restart
restart: stop start             ## Restart Postgres

.PHONY: status
status:                         ## Show server status
	"$(PG_BIN)/pg_ctl" -D "$(PGDATA)" status

.PHONY: create-db
create-db:                      ## Create the app role + database (idempotent)
	@test -n "$(APP_DB_PASSWORD)" || (echo "Set APP_DB_PASSWORD in .env first" && exit 1)
	"$(PG_BIN)/psql" -h /tmp -p $(PG_PORT) -U "$(PG_SUPERUSER)" -d postgres -v ON_ERROR_STOP=1 \
	  -v appuser="$(APP_USER)" -v apppass="$(APP_DB_PASSWORD)" -v appdb="$(APP_DB)" \
	  -f sql/create_app_db.sql

.PHONY: psql
psql:                           ## Open an admin psql shell (local socket, trust auth)
	"$(PG_BIN)/psql" -h /tmp -p $(PG_PORT) -U "$(PG_SUPERUSER)" -d $(APP_DB)

.PHONY: migrate
migrate:                        ## Apply sql/001_schema.sql (idempotent, runs as app owner)
	@test -n "$(APP_DB_PASSWORD)" || (echo "Set APP_DB_PASSWORD in .env first" && exit 1)
	PGPASSWORD="$(APP_DB_PASSWORD)" "$(PG_BIN)/psql" -h 127.0.0.1 -p $(PG_PORT) -U "$(APP_USER)" -d $(APP_DB) \
	  -v ON_ERROR_STOP=1 -f sql/001_schema.sql

.PHONY: migrate-vector
migrate-vector:                 ## Apply sql/002_vector_schema.sql (needs install-pgvector first)
	@test -n "$(APP_DB_PASSWORD)" || (echo "Set APP_DB_PASSWORD in .env first" && exit 1)
	PGPASSWORD="$(APP_DB_PASSWORD)" "$(PG_BIN)/psql" -h 127.0.0.1 -p $(PG_PORT) -U "$(APP_USER)" -d $(APP_DB) \
	  -v ON_ERROR_STOP=1 -f sql/002_vector_schema.sql

.PHONY: migrate-learner
migrate-learner:                ## Apply sql/003_learner_schema.sql (student login/attempts/mastery, idempotent)
	@test -n "$(APP_DB_PASSWORD)" || (echo "Set APP_DB_PASSWORD in .env first" && exit 1)
	PGPASSWORD="$(APP_DB_PASSWORD)" "$(PG_BIN)/psql" -h 127.0.0.1 -p $(PG_PORT) -U "$(APP_USER)" -d $(APP_DB) \
	  -v ON_ERROR_STOP=1 -f sql/003_learner_schema.sql

.PHONY: migrate-learner-remote
migrate-learner-remote:         ## Apply sql/003_learner_schema.sql to the remote Neon Postgres
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/003_learner_schema.sql

.PHONY: migrate-admin
migrate-admin:                  ## Apply sql/004_admin_pipeline.sql (source_kind column, idempotent)
	@test -n "$(APP_DB_PASSWORD)" || (echo "Set APP_DB_PASSWORD in .env first" && exit 1)
	PGPASSWORD="$(APP_DB_PASSWORD)" "$(PG_BIN)/psql" -h 127.0.0.1 -p $(PG_PORT) -U "$(APP_USER)" -d $(APP_DB) \
	  -v ON_ERROR_STOP=1 -f sql/004_admin_pipeline.sql

.PHONY: migrate-admin-remote
migrate-admin-remote:           ## Apply sql/004_admin_pipeline.sql to the remote Neon Postgres
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/004_admin_pipeline.sql

.PHONY: migrate-student-names
migrate-student-names:          ## Apply sql/005_student_profile_names.sql (first_name/last_name, idempotent)
	@test -n "$(APP_DB_PASSWORD)" || (echo "Set APP_DB_PASSWORD in .env first" && exit 1)
	PGPASSWORD="$(APP_DB_PASSWORD)" "$(PG_BIN)/psql" -h 127.0.0.1 -p $(PG_PORT) -U "$(APP_USER)" -d $(APP_DB) \
	  -v ON_ERROR_STOP=1 -f sql/005_student_profile_names.sql

.PHONY: migrate-student-names-remote
migrate-student-names-remote:   ## Apply sql/005_student_profile_names.sql to the remote Neon Postgres
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/005_student_profile_names.sql

.PHONY: progress
progress:                       ## Show recent pipeline.run / pipeline.graph_projection rows (local Postgres)
	@test -n "$(APP_DB_PASSWORD)" || (echo "Set APP_DB_PASSWORD in .env first" && exit 1)
	PGPASSWORD="$(APP_DB_PASSWORD)" "$(PG_BIN)/psql" -h 127.0.0.1 -p $(PG_PORT) -U "$(APP_USER)" -d $(APP_DB) \
	  -c "SELECT run_type, status, started_at, completed_at, completed_items, failed_items FROM pipeline.run ORDER BY started_at DESC LIMIT 20;" \
	  -c "SELECT graph_name, status, started_at, completed_at, nodes_upserted, edges_upserted FROM pipeline.graph_projection ORDER BY started_at DESC LIMIT 20;"

.PHONY: progress-remote
progress-remote:                ## Show recent pipeline.run / pipeline.graph_projection rows (remote Neon)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -c "SELECT run_type, status, started_at, completed_at, completed_items, failed_items FROM pipeline.run ORDER BY started_at DESC LIMIT 20;" \
	  -c "SELECT graph_name, status, started_at, completed_at, nodes_upserted, edges_upserted FROM pipeline.graph_projection ORDER BY started_at DESC LIMIT 20;"

# ── Corpus ETL (Python) ────────────────────────────────────────────────────

PEDAGOGY_PYTHON ?= $(CURDIR)/.venv/bin/python
PEDAGOGY_GRAPH_PYTHON ?= $(CURDIR)/../mathbank-graph/.venv/bin/python
GRAPH_ENV_FILE ?= $(CURDIR)/../mathbank-graph/.env

.PHONY: migrate-pedagogy migrate-pedagogy-remote pedagogy-validate pedagogy-dry-run pedagogy-import project-pedagogy
migrate-pedagogy:               ## Explicit local-only migration 006 (no automatic import/projection)
	@test -n "$(APP_DB_PASSWORD)" || (echo "Set APP_DB_PASSWORD in .env first" && exit 1)
	PGPASSWORD="$(APP_DB_PASSWORD)" "$(PG_BIN)/psql" -h 127.0.0.1 -p $(PG_PORT) -U "$(APP_USER)" -d $(APP_DB) \
	  -v ON_ERROR_STOP=1 -f sql/006_pedagogy.sql

migrate-pedagogy-remote:        ## Explicit migration 006 on the remote Neon app database
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/006_pedagogy.sql

pedagogy-validate:              ## Offline manifest validation; set MANIFEST=path.json
	@test -n "$(MANIFEST)" || (echo "Set MANIFEST=path/to/authoring.json" && exit 1)
	"$(PEDAGOGY_PYTHON)" etl/import_pedagogy.py validate "$(MANIFEST)"

pedagogy-dry-run:               ## Read-only DB FK/cycle validation; set MANIFEST=path.json
	@test -n "$(MANIFEST)" || (echo "Set MANIFEST=path/to/authoring.json" && exit 1)
	"$(PEDAGOGY_PYTHON)" etl/import_pedagogy.py import "$(MANIFEST)" --dry-run

pedagogy-import:                ## Explicit atomic authoring upsert; set MANIFEST=path.json
	@test -n "$(MANIFEST)" || (echo "Set MANIFEST=path/to/authoring.json" && exit 1)
	"$(PEDAGOGY_PYTHON)" etl/import_pedagogy.py import "$(MANIFEST)"

project-pedagogy:               ## Explicit Neo4j projection including migration-006 skills
	GRAPH_ENV_FILE="$(GRAPH_ENV_FILE)" "$(PEDAGOGY_GRAPH_PYTHON)" ../mathbank-graph/etl/project_from_postgres.py --pedagogy

.PHONY: pedagogy-dry-run-remote pedagogy-import-remote project-pedagogy-remote
pedagogy-dry-run-remote:        ## Read-only manifest check against remote Neon
	PG_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" $(MAKE) pedagogy-dry-run

pedagogy-import-remote:         ## Explicit atomic manifest import into remote Neon
	PG_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" $(MAKE) pedagogy-import

project-pedagogy-remote:        ## Explicit remote Neon to AuraDB metadata projection
	$(MAKE) project-pedagogy GRAPH_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env"

.PHONY: migrate-pedagogy-review migrate-pedagogy-review-remote
.PHONY: migrate-automatic-metadata-remote
.PHONY: migrate-textbook-import-remote textbook-import-dry-run textbook-import-remote textbook-import-status-remote
TEXTBOOK_ROOT     ?= $(CURDIR)/../math_tutor_new_requirements_copilot_pack_v2_expanded/GEOMETRY-TEXTBOOKS
TEXTBOOK_PACKAGES ?= $(TEXTBOOK_ROOT)/Prasolov_Geometry_Corpus_Ch01_20 $(TEXTBOOK_ROOT)/Prasolov_Geometry_Corpus_Ch21_30
TEXTBOOK_PYTHON   ?= $(CURDIR)/../mathbank-rest/.venv/bin/python
TEXTBOOK_CHAPTER_ARGS = $(foreach c,$(CHAPTER),--chapter $(c))
migrate-textbook-import-remote: ## Add ingest.* package/staging/reconciliation + pedagogy.* step tables (migration 010)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/010_textbook_import.sql
textbook-import-dry-run:        ## Validate Prasolov packages offline (CHAPTER="1 2" for a pilot)
	$(TEXTBOOK_PYTHON) etl/import_textbook_package.py $(TEXTBOOK_PACKAGES) $(TEXTBOOK_CHAPTER_ARGS) --dry-run
textbook-import-remote:         ## Idempotent Prasolov import into Neon (CHAPTER="1" for a pilot)
	PG_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" $(TEXTBOOK_PYTHON) etl/import_textbook_package.py $(TEXTBOOK_PACKAGES) $(TEXTBOOK_CHAPTER_ARGS)
textbook-import-status-remote:  ## Package status + reconciliation from Neon
	PG_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" $(TEXTBOOK_PYTHON) etl/import_textbook_package.py --status
TEXTBOOK_GRAPH = GRAPH_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" "$(PEDAGOGY_GRAPH_PYTHON)" ../mathbank-graph/etl/project_textbook_steps.py
.PHONY: textbook-graph-dry-run-remote textbook-graph-remote textbook-graph-status-remote
textbook-graph-dry-run-remote:  ## Planned SolutionPart/SolutionStep graph counts from Neon (no graph writes)
	$(TEXTBOOK_GRAPH) --dry-run
textbook-graph-remote:          ## Base --pedagogy projection, then idempotent step layer (Phase 4) into Aura
	GRAPH_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" "$(PEDAGOGY_GRAPH_PYTHON)" ../mathbank-graph/etl/project_from_postgres.py --pedagogy
	$(TEXTBOOK_GRAPH)
textbook-graph-status-remote:   ## Reconcile Neon step counts against Aura (read-only)
	$(TEXTBOOK_GRAPH) --status
TEXTBOOK_VECTOR = PG_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" .venv/bin/python etl/embed_textbook_steps.py
.PHONY: migrate-step-vector-remote textbook-vector-build-remote textbook-vector-remote textbook-vector-status-remote textbook-problem-vector-remote
migrate-step-vector-remote:     ## Add step/learning-item vector metadata columns (migration 011)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/011_step_vector_metadata.sql
textbook-vector-build-remote:   ## Step/learning-item/taxonomy-node representations + chunks only (no paid calls)
	$(TEXTBOOK_VECTOR) build
textbook-vector-remote:         ## Build + embed step/published learning-item/taxonomy-node chunks (Phase 5, paid, idempotent)
	$(TEXTBOOK_VECTOR) backfill
textbook-vector-status-remote:  ## Reconcile eligible steps/items/taxonomy nodes against ACTIVE embeddings (read-only)
	$(TEXTBOOK_VECTOR) status
PROJECTION_QUEUE = PG_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" .venv/bin/python etl/run_projection_requests.py
.PHONY: projection-queue-status-remote projection-queue-run-remote projection-queue-run-paid-remote
projection-queue-status-remote:    ## Pending pipeline.projection_request rows by target (read-only)
	$(PROJECTION_QUEUE) --status
projection-queue-run-remote:       ## Free: run textbook-graph-remote for pending graph requests, mark DONE; list paid ones
	$(PROJECTION_QUEUE)
projection-queue-run-paid-remote:  ## PAID: also run textbook-vector-remote for pending embedding requests
	$(PROJECTION_QUEUE) --allow-paid
textbook-problem-vector-remote: ## Embed textbook problem statements/solutions via the existing corpus embedder (paid)
	PG_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" .venv/bin/python etl/embed_corpus.py backfill \
	  $$(PG_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" .venv/bin/python etl/embed_textbook_steps.py papers)
.PHONY: migrate-step-runtime-remote
migrate-step-runtime-remote:    ## Student step runtime: solve_attempt, step state, events, tutor.runtime_state, outbox (migration 012)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/012_step_runtime.sql
.PHONY: migrate-step-hints-remote
migrate-step-hints-remote:      ## Shared per-step hint cache for the Phase 8 hint ladder (migration 013)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/013_step_hints.sql
.PHONY: migrate-gap-diagnosis-remote
migrate-gap-diagnosis-remote:   ## Phase 9 gap diagnosis + knowledge-gap hypotheses (migration 014)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/014_gap_diagnosis.sql
.PHONY: migrate-recovery-remote textbook-approve-learning-items-remote
migrate-recovery-remote:        ## Phase 10 recovery plans/items + learning-item approval columns (migration 015)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/015_recovery_runtime.sql
.PHONY: migrate-agent-session-link-remote
migrate-agent-session-link-remote: ## Student ↔ ADK agent session link for transcripts (migration 016)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/016_agent_session_link.sql
.PHONY: migrate-step-technique-remote textbook-step-techniques-remote
migrate-step-technique-remote:  ## Step → technique tags + derivation runs (migration 017)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/017_step_techniques.sql
textbook-step-techniques-remote: ## Derive rule-tier step techniques for the Prasolov book (free, idempotent)
	cd etl && PG_ENV_FILE=../../mathbank-graph/remote.env ../.venv/bin/python derive_step_techniques.py
	cd etl && PG_ENV_FILE=../../mathbank-graph/remote.env ../.venv/bin/python derive_step_techniques.py --status
textbook-approve-learning-items-remote: ## Auto-approve validated PENDING_REVIEW learning items (idempotent; then vector + graph)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/ops/approve_learning_items_auto.sql
.PHONY: migrate-outbox-consumers-remote
migrate-outbox-consumers-remote: ## Outbox consumers: analytics rollup, projection requests, ATTEMPT_ABANDONED (migration 018)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/018_outbox_consumers.sql
.PHONY: migrate-admin-import-review-remote
migrate-admin-import-review-remote: ## Admin import/DAG review audit, conflict decisions, step edit guard (migration 019)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/019_admin_import_review.sql
.PHONY: migrate-relationship-enrichment-remote
migrate-relationship-enrichment-remote: ## Add durable auto-approved relationship jobs (migration 009)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/009_relationship_enrichment.sql
migrate-automatic-metadata-remote: ## Enable automatic metadata approval on Neon (migration 008)
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/008_automatic_metadata.sql
migrate-pedagogy-review:        ## Add admin review audit and publication tables locally
	PGPASSWORD="$(APP_DB_PASSWORD)" "$(PG_BIN)/psql" -h 127.0.0.1 -p $(PG_PORT) -U "$(APP_USER)" -d $(APP_DB) \
	  -v ON_ERROR_STOP=1 -f sql/007_pedagogy_review.sql

migrate-pedagogy-review-remote: ## Add admin review audit and publication tables on Neon
	@. $(CURDIR)/../mathbank-graph/remote.env; \
	  PGPASSWORD="$$NEON_PG_PASSWORD" "$(PG_BIN)/psql" "host=$$NEON_PG_HOST port=$$NEON_PG_PORT dbname=$$NEON_PG_DATABASE user=$$NEON_PG_USER sslmode=require" \
	  -v ON_ERROR_STOP=1 -f sql/007_pedagogy_review.sql

.PHONY: etl-venv
etl-venv:                       ## Create the Python venv used by etl/load_corpus.py
	uv venv .venv --python 3.11
	uv pip install --python .venv/bin/python "psycopg[binary]>=3.2" "openai>=1.50" "tiktoken>=0.7"

.PHONY: etl
etl: migrate                    ## Load the maths_corpus CSV mirror into Postgres (idempotent)
	@test -n "$(APP_DB_PASSWORD)" || (echo "Set APP_DB_PASSWORD in .env first" && exit 1)
	.venv/bin/python etl/load_corpus.py

.PHONY: etl-remote
etl-remote:                     ## Load the maths_corpus CSV mirror into the remote Neon Postgres (see ../mathbank-graph/remote.env)
	PG_ENV_FILE=$(CURDIR)/../mathbank-graph/remote.env .venv/bin/python etl/load_corpus.py

# ── PDF download/parse/ingest pipeline tracker (Python) ─────────────────────

.PHONY: vector-backfill
vector-backfill: migrate-vector ## Build representations/chunks + embed via OpenAI (set LIMIT=)
	.venv/bin/python etl/embed_corpus.py backfill $(if $(LIMIT),--limit $(LIMIT),)

.PHONY: vector-index
vector-index:                   ## Create the HNSW index for the active embedding model
	.venv/bin/python etl/embed_corpus.py index

.PHONY: vector-status
vector-status:                  ## Show representation/chunk/embedding counts
	.venv/bin/python etl/embed_corpus.py status

.PHONY: vector-backfill-remote
vector-backfill-remote:         ## Build representations/chunks + embed via OpenAI, against remote Neon (set LIMIT=; needs OPENAI_API_KEY)
	PG_ENV_FILE=$(CURDIR)/../mathbank-graph/remote.env .venv/bin/python etl/embed_corpus.py backfill $(if $(LIMIT),--limit $(LIMIT),)

.PHONY: vector-index-remote
vector-index-remote:            ## Create the HNSW index for the active embedding model, on remote Neon
	PG_ENV_FILE=$(CURDIR)/../mathbank-graph/remote.env .venv/bin/python etl/embed_corpus.py index

.PHONY: vector-status-remote
vector-status-remote:           ## Show representation/chunk/embedding counts on remote Neon
	PG_ENV_FILE=$(CURDIR)/../mathbank-graph/remote.env .venv/bin/python etl/embed_corpus.py status

.PHONY: pdf-discover
PAPER_BATCH_PYTHON ?= $(CURDIR)/../mathbank-rest/.venv/bin/python
.PHONY: purple-comet-discover-remote purple-comet-batches-remote
purple-comet-discover-remote:    ## Download/register/extract official English Purple Comet archive (YEAR= optional)
	PG_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" "$(PAPER_BATCH_PYTHON)" -u etl/purple_comet.py --register --extract $(if $(YEAR),--year $(YEAR),)

purple-comet-batches-remote:     ## Paid Purple Comet classify -> Neon -> Aura; waits for existing paper runner
	PG_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" GRAPH_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" \
	  "$(PAPER_BATCH_PYTHON)" -u etl/paper_batches.py --competition PURPLE_MS --competition PURPLE_HS \
	  --wait-for-lock --batch-size $(or $(BATCH_SIZE),2) $(if $(LIMIT),--limit $(LIMIT),) $(if $(RESUME),--resume $(RESUME),)
.PHONY: paper-batches-remote
paper-batches-remote:            ## Paid SMT/HMMT backlog -> classify -> Neon -> Aura, batches of 5 (BATCH_SIZE= LIMIT= RESUME=)
	PG_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" GRAPH_ENV_FILE="$(CURDIR)/../mathbank-graph/remote.env" \
	  "$(PAPER_BATCH_PYTHON)" -u etl/paper_batches.py --batch-size $(or $(BATCH_SIZE),5) \
	  $(if $(LIMIT),--limit $(LIMIT),) $(if $(RESUME),--resume $(RESUME),)

pdf-discover:                   ## Track all direct-link PDF papers from paper_registry.csv
	.venv/bin/python etl/pdf_pipeline.py discover

.PHONY: pdf-reconcile
pdf-reconcile:                  ## Update download/parse status from what's already on disk
	.venv/bin/python etl/pdf_pipeline.py reconcile

.PHONY: pdf-ingest
pdf-ingest:                     ## Load PARSED-but-not-INGESTED papers into core.problem/solution
	.venv/bin/python etl/pdf_pipeline.py ingest

.PHONY: pdf-status
pdf-status:                     ## Print per-competition pipeline progress
	.venv/bin/python etl/pdf_pipeline.py status

.PHONY: pdf-pipeline
pdf-pipeline: migrate           ## discover -> reconcile -> ingest -> status (idempotent, no network)
	.venv/bin/python etl/pdf_pipeline.py run

.PHONY: pdf-fetch
pdf-fetch:                      ## Opt-in: real downloads for PENDING papers — PDF via Docling crawler, HTML via stdlib fetch (set LIMIT=)
	.venv/bin/python etl/pdf_pipeline.py fetch --limit $(or $(LIMIT),10)

.PHONY: setup
setup: install init start create-db  ## One-shot bootstrap: install, init, start, create-db

.PHONY: bootstrap
bootstrap:                      ## Full single-command rebuild: db + schema + pgvector + corpus + embeddings
	@test -f .env || (echo "Create mathbank-db/.env from .env.example first (see GOTCHAS.md)" && exit 1)
	$(MAKE) setup
	$(MAKE) install-pgvector
	$(MAKE) migrate
	$(MAKE) migrate-vector
	$(MAKE) check-pgvector
	$(MAKE) etl-venv
	$(MAKE) etl
	$(MAKE) pdf-pipeline
	@test -n "$$OPENAI_API_KEY" && $(MAKE) vector-backfill && $(MAKE) vector-index \
	  || echo "OPENAI_API_KEY not set in this shell -- skipping vector-backfill/index. Export it and re-run 'make vector-backfill vector-index' later."
	@echo "mathbank-db bootstrap complete. Run 'make vector-status' / 'make pdf-status' to review."

.PHONY: destroy
destroy:                        ## Stop server and DELETE the external data directory
	-"$(PG_BIN)/pg_ctl" -D "$(PGDATA)" stop -m fast
	rm -rf "$(PGDATA)"

.PHONY: help
help:                           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
