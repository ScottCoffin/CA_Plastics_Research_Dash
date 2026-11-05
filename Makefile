PYTHON ?= python

.PHONY: setup test lint build all

setup:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

build:
	$(PYTHON) -m compileall -q src

all: lint test build

