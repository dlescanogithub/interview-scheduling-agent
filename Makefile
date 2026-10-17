PYTHON ?= python3
PKG = scheduling_agent

.PHONY: setup lint format test eval eval-regression secretscan demo live

setup:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

test:
	$(PYTHON) -m pytest

eval:
	$(PYTHON) -m $(PKG) eval

# Expected to exit 1: the broken provider must fail the invariant gate.
eval-regression:
	$(PYTHON) -m $(PKG) eval --regression

secretscan:
	$(PYTHON) -m $(PKG).secretscan

demo:
	$(PYTHON) -m $(PKG) demo

live:
	$(PYTHON) -m $(PKG) live --scenario happy_path --max-turns 12
