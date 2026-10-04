PYTHON    ?= python3.11
VENV      := .venv
BIN       := $(VENV)/bin
PIP       := $(BIN)/pip
PYTEST    := $(BIN)/pytest
RUFF      := $(BIN)/ruff
MYPY      := $(BIN)/mypy

.DEFAULT_GOAL := help

# ── Environment ────────────────────────────────────────────────────────────

.PHONY: venv
venv:                          ## Create the virtual environment
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	@echo "Virtual environment created at $(VENV)/"
	@echo "Activate with:  source $(VENV)/bin/activate"

.PHONY: install
install: venv                  ## Install all runtime + dev dependencies
	$(PIP) install -e ".[dev]"

.PHONY: install-ci
install-ci:                    ## Install (no venv creation) for CI environments
	pip install -e ".[dev]"

# ── Quality ────────────────────────────────────────────────────────────────

.PHONY: lint
lint:                          ## Run ruff linter
	$(RUFF) check src tests scripts

.PHONY: format
format:                        ## Auto-format with ruff
	$(RUFF) format src tests scripts

.PHONY: typecheck
typecheck:                     ## Run mypy type checks
	$(MYPY) src

.PHONY: audit
audit:                         ## Check dependencies for known CVEs
	$(BIN)/pip-audit

.PHONY: check
check: lint typecheck audit    ## Run all quality checks

# ── Tests ──────────────────────────────────────────────────────────────────

.PHONY: test
test:                          ## Run the test suite
	$(PYTEST)

.PHONY: test-cov
test-cov:                      ## Run tests with coverage report
	$(PYTEST) --cov=tika_corpus --cov-report=term-missing --cov-report=html

# ── Pipeline ───────────────────────────────────────────────────────────────

BATCH ?= BATCH_001

.PHONY: ingest
ingest:                        ## Ingest the master Excel spreadsheet (set BATCH=)
	$(BIN)/python scripts/ingest_excel.py \
	  --xlsx "$(XLSX)" \
	  --batch $(BATCH) \
	  --stage all

.PHONY: ingest-dry
ingest-dry:                    ## Dry-run ingest (validate + build, no writes)
	$(BIN)/python scripts/ingest_excel.py \
	  --xlsx "$(XLSX)" \
	  --batch $(BATCH) \
	  --stage all \
	  --dry-run

.PHONY: setup-firestore
setup-firestore:               ## Bootstrap Firestore collections (set PROJECT=)
	$(BIN)/python scripts/setup_firestore.py --project $(PROJECT)

.PHONY: setup-firestore-dry
setup-firestore-dry:           ## Dry-run Firestore bootstrap
	$(BIN)/python scripts/setup_firestore.py --project $(PROJECT) --dry-run

.PHONY: deploy-indexes
deploy-indexes:                ## Deploy Firestore composite indexes via Firebase CLI
	firebase deploy --only firestore:indexes --project $(PROJECT)

# ── Pipeline — crawl ──────────────────────────────────────────────────────
# AoPS wiki (AMC 10 / AMC 12 / AIME — per-question HTML pages)
.PHONY: crawl-unmapped
crawl-unmapped:             ## [AoPS] Crawl unmapped AMC/AIME questions (set LIMIT= LEVEL= DELAY=)
	$(BIN)/python scripts/crawl_unmapped.py \
	  --limit $(or $(LIMIT),50) \
	  $(if $(LEVEL),--level "$(LEVEL)",) \
	  $(if $(DELAY),--delay $(DELAY),)

.PHONY: crawl-dry
crawl-dry:                  ## [AoPS] Preview the next AoPS crawl batch without fetching
	$(BIN)/python scripts/crawl_unmapped.py --limit 20 --dry-run

.PHONY: crawl-reparse
crawl-reparse:              ## [AoPS] Re-parse already-downloaded AoPS HTML (no network)
	$(BIN)/python scripts/crawl_unmapped.py --reparse --limit 9999

# Install Docling (heavy ML deps, ~2 GB — run outside VS Code sandbox if SSL fails)
.PHONY: install-docling
install-docling:            ## Install Docling for layout-aware PDF extraction
	$(PIP) install docling
	@echo "Docling installed. Re-process PDFs with: make docling-reprocess"

.PHONY: docling-reprocess
docling-reprocess:          ## Re-extract all PDFs through Docling (run after install-docling)
	@$(BIN)/python3 -c "import docling" 2>/dev/null || \
	  (echo "ERROR: Docling not installed. Run:  make install-docling" && exit 1)
	find data/crawl_pdf -name "index.json" -delete
	sqlite3 data/mathbank.db "UPDATE unparsed_papers SET question_index_status=NULL WHERE question_index_status='INDEXED';"
	$(MAKE) crawl-pdf LIMIT=9999

# PDF archive (HMMT / SMT / PUMaC / CMM / CHMMC / MPG — whole-paper PDFs)
.PHONY: crawl-pdf
crawl-pdf:                  ## [PDF] Crawl PDF competition papers (set COMPETITION= LIMIT= DELAY=)
	$(BIN)/python scripts/crawl_pdf_papers.py \
	  --limit $(or $(LIMIT),20) \
	  $(if $(COMPETITION),--competition "$(COMPETITION)",) \
	  $(if $(DELAY),--delay $(DELAY),)

.PHONY: crawl-pdf-dry
crawl-pdf-dry:              ## [PDF] Preview PDF crawl queue without fetching
	$(BIN)/python scripts/crawl_pdf_papers.py --dry-run --limit 20

.PHONY: crawl-all
crawl-all: crawl-unmapped crawl-pdf  ## Run both AoPS and PDF crawlers

.PHONY: classify
classify:                   ## Classify crawled questions with OpenAI (set LIMIT= LEVEL=)
	$(BIN)/python scripts/classify_crawled.py \
	  --limit $(or $(LIMIT),20) \
	  $(if $(LEVEL),--level "$(LEVEL)",)

.PHONY: classify-dry
classify-dry:               ## Preview classify queue without API calls
	$(BIN)/python scripts/classify_crawled.py --dry-run --limit 10

.PHONY: export-classifications
export-classifications:     ## Bridge SQLite classification results into the CSV corpus mirror (idempotent)
	$(BIN)/python scripts/export_classifications_to_csv.py

.PHONY: export-classifications-dry
export-classifications-dry: ## Preview the classification export without writing
	$(BIN)/python scripts/export_classifications_to_csv.py --dry-run

# ── Review (second-pass GPT-4o quality check with vision) ─────────────────────

.PHONY: review
review:                     ## Review classified questions with GPT-4o vision (set LIMIT= LEVEL= STATUS=)
	$(BIN)/python scripts/review_classified.py \
	  --limit $(or $(LIMIT),20) \
	  $(if $(LEVEL),--level "$(LEVEL)",) \
	  $(if $(STATUS),--status "$(STATUS)",)

.PHONY: review-dry
review-dry:                 ## Preview review queue without API calls
	$(BIN)/python scripts/review_classified.py --dry-run --limit 10

.PHONY: review-retry
review-retry:               ## Re-review NEEDS_HUMAN_REVIEW questions
	$(BIN)/python scripts/review_classified.py --retry-failed --limit $(or $(LIMIT),20)

.PHONY: db
db:                            ## Build / refresh the local SQLite corpus database
	$(BIN)/python scripts/build_sqlite.py

.PHONY: db-fresh
db-fresh:                      ## Drop and fully rebuild the SQLite database
	$(BIN)/python scripts/build_sqlite.py --fresh

.PHONY: split-pdf
split-pdf:                     ## Split PDF paper artifacts into per-question problem.md + solution.md
	$(BIN)/python scripts/split_pdf_artifacts.py \
	  $(if $(COMPETITION),--competition "$(COMPETITION)",) \
	  $(if $(PAPER),--paper "$(PAPER)",)

.PHONY: split-pdf-dry
split-pdf-dry:                 ## Preview what split-pdf would produce (no writes)
	$(BIN)/python scripts/split_pdf_artifacts.py --dry-run

# ── Maintenance ────────────────────────────────────────────────────────────

.PHONY: clean
clean:                         ## Remove build artefacts and caches
	rm -rf dist build *.egg-info .pytest_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

.PHONY: clean-venv
clean-venv: clean              ## Remove the virtual environment entirely
	rm -rf $(VENV)

# ── Help ───────────────────────────────────────────────────────────────────

.PHONY: help
help:                          ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
