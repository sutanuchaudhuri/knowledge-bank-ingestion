PYTHON_VERSION ?= 3.11
BIN := .venv/bin

.PHONY: install test lint gallery eval-paid
install:
	uv venv .venv --python $(PYTHON_VERSION)
	uv pip install --python $(BIN)/python -e ".[dev,agent]"
test:
	$(BIN)/pytest tests -q
lint:
	$(BIN)/ruff check src tests
	$(BIN)/mypy src --ignore-missing-imports
gallery:
	$(BIN)/python -m geometry_scene.gallery --fixtures fixtures --output output/gallery
eval-paid:
	$(BIN)/python -m geometry_scene.evaluation --fixtures fixtures --output output/agent-eval --paid
