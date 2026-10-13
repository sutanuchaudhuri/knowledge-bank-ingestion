PYTHON_VERSION ?= 3.11
VENV      := .venv
BIN       := $(VENV)/bin
PYTEST    := $(BIN)/pytest

.DEFAULT_GOAL := help

.PHONY: help
help:                            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*##"}; {printf "  %-20s %s\n", $$1, $$2}'

.PHONY: venv
venv:                            ## Create the virtual environment
	python3 -m venv $(VENV)

.PHONY: install
install: venv                   ## Install runtime + dev dependencies
	$(BIN)/pip install -e ".[dev]"

.PHONY: test
test:                           ## Run the unit test suite (no network/LLM calls)
	$(PYTEST) -v

.PHONY: run
run:                            ## Run the FastAPI app locally (needs mathbank-rest already running)
	AWS_PROFILE=$${AWS_PROFILE:-aws-sutanu-admin} AWS_DEFAULT_REGION=$${AWS_DEFAULT_REGION:-us-east-2} \
		$(BIN)/uvicorn mathbank_exam_agent.main:app --app-dir src --reload --port 8030
