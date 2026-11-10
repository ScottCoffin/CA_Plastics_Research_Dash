PYTHON ?= python

.PHONY: setup test lint build qc all reproduce

setup:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

build:
	$(PYTHON) -m compileall -q src

qc:
	$(PYTHON) scripts/normalize_openalex.py

reproduce:
	$(PYTHON) scripts/rebuild_from_fixtures.py

all: lint test build
