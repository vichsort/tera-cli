.PHONY: demo test typecheck lint validate clean install

VENV ?= .venv
BIN = $(VENV)/bin
PYTHON = $(BIN)/python
PYTEST = $(BIN)/pytest
PYRIGHT = $(BIN)/pyright
TERA = $(BIN)/tera

demo:
	@PATH="$(BIN):$$PATH" ./examples/demo.sh

test:
	$(PYTEST) -v

typecheck:
	$(PYRIGHT)

lint:
	$(TERA) lint docs.yaml

validate:
	$(TERA) validate docs.yaml

check: typecheck test lint validate

clean:
	rm -rf dist/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
