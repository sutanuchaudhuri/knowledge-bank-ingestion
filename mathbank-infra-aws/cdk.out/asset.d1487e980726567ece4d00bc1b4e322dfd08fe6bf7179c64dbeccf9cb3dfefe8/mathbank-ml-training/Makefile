PYTHON_VERSION ?= 3.11
VENV      := .venv
BIN       := $(VENV)/bin

.DEFAULT_GOAL := help

.PHONY: help
help:                            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*##"}; {printf "  %-20s %s\n", $$1, $$2}'

.PHONY: venv
venv:                            ## Create the virtual environment
	python3 -m venv $(VENV)

.PHONY: install
install: venv                   ## Install runtime + dev dependencies (notebooks, offline pipeline stubs)
	$(BIN)/pip install -e ".[dev]"

.PHONY: notebook
notebook:                        ## Launch Jupyter Lab over notebooks/ (SageMaker-style offline pipeline, requirements/55)
	$(BIN)/pip show jupyterlab >/dev/null 2>&1 || $(BIN)/pip install jupyterlab
	$(BIN)/jupyter lab notebooks

.PHONY: lint
lint:                           ## Run ruff linter
	$(BIN)/ruff check src tests

# TODO: add `test` target once the typed stubs in src/ have real implementations
# (requirements/55 — scaffolded only for now; every function currently raises
# NotImplementedError, so a test suite would have nothing real to assert against).

.PHONY: clean
clean:                          ## Remove build artifacts and caches
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null; \
	rm -rf .pytest_cache *.egg-info src/*.egg-info
