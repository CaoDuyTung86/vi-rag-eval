.PHONY: install test lint eval baseline

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

lint:
	python -m ruff check .

eval:
	python -m eval.harness

baseline:
	python -m eval.harness --json > baseline.json
