# mathbank-widgets — shared React widget/composer package used by mathbank-web and mathbank-live.
#
# Not a service: no port, nothing to start. Distributed by file-copy (consumers run
# `make sync-widgets`), not an npm registry publish — see this project's README "Deployment
# strategy" for why.
#
# Quick start:
#   make install
#   make test

.DEFAULT_GOAL := help

.PHONY: help
help:                           ## List targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  %-14s %s\n", $$1, $$2}'

.PHONY: install
install:                        ## npm install (peer dependency: react, provided by the consumer)
	npm install

.PHONY: test
test:                           ## Run the node --test suite (format/speech/server)
	npm test

.PHONY: lint
lint:                           ## Syntax-check plain JS/MJS sources (no bundler/linter configured yet)
	@for f in src/*.js src/*.mjs; do node --check "$$f" || exit 1; done
	@echo "All .js/.mjs source files parse cleanly (.jsx files need a consumer's JSX transform to check)."
