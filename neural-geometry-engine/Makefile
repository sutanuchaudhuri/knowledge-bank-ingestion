PYTHON_VERSION ?= 3.11
BIN := .venv/bin

.PHONY: install test lint gallery
install:
	uv venv .venv --python $(PYTHON_VERSION)
	uv pip install --python $(BIN)/python -e ../geometry-scene-engine -e ".[dev]"
test:
	$(BIN)/pytest tests -q
lint:
	$(BIN)/ruff check src tests
	$(BIN)/mypy src --ignore-missing-imports
gallery:
	$(BIN)/python -m neural_geometry.cli gallery --output output/gallery
