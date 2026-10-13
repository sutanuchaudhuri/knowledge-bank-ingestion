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
test:                           ## Run the test suite (live-LLM test opt-in only)
	$(PYTEST) -v

.PHONY: test-live-llm
test-live-llm:                  ## Also run the opt-in live-OpenAI agent test (costs a real API call)
	AGENT_DEMO_LIVE_LLM=1 $(PYTEST) tests/test_agent_demo.py -v

.PHONY: run
run:                            ## Run the MCP server over stdio (for MCP host configs)
	$(BIN)/python -m mathbank_mcp_competitions

.PHONY: access
access:                         ## Show how to point an MCP host at this server
	@printf '  %-20s %s\n' 'Transport' 'stdio (default) — no fixed port' \
	  'MCP host command' '$(CURDIR)/.venv/bin/python -m mathbank_mcp_competitions' \
	  'Try it' 'make demo'

.PHONY: demo
demo:                           ## Run the bundled OpenAI agent demo with a sample question
	$(BIN)/python -m agent_demo.agent "Find a real AMC10 geometry problem about triangle area and tell me its canonical code and official answer."

.PHONY: clean
clean:                          ## Remove build artifacts and caches
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null; \
	rm -rf .pytest_cache *.egg-info src/*.egg-info
