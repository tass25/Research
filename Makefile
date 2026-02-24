# ─── Grammar Enforcement Pipeline ─────────────────────────────────────
# SEAMS 2026 — Makefile for common tasks
# ──────────────────────────────────────────────────────────────────────

.PHONY: install test test-cov lint typecheck run run-all clean help

PYTHON  ?= python
VENV    ?= venv
PIP     ?= $(VENV)/Scripts/pip
PY      ?= $(VENV)/Scripts/python

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install all dependencies (including dev)
	$(PIP) install -r requirements.txt
	$(PIP) install mypy ruff

test:  ## Run test suite
	$(PY) -m pytest tests/ -v --tb=short

test-cov:  ## Run tests with coverage report
	$(PY) -m pytest tests/ --cov=core --cov=parsers --cov=validators --cov=semantic --cov=minimality --cov=data --cov=shared --cov=rule_inference --cov=rule_validation --cov=cbf_data --cov-report=term-missing --cov-report=html

lint:  ## Run ruff linter
	$(PY) -m ruff check .

typecheck:  ## Run mypy type checker
	$(PY) -m mypy core/ parsers/ validators/ semantic/ minimality/ data/ shared/ rule_inference/ rule_validation/ cbf_data/

run:  ## Run pipeline for a single system (use SYSTEM= CONTROLLER=)
	$(PY) run_pipeline.py --system $(SYSTEM) --controller $(CONTROLLER)

run-all:  ## Run pipeline for all system/controller combinations
	$(PY) run_pipeline.py

run-verbose:  ## Run pipeline with debug logging
	$(PY) run_pipeline.py --verbose --log-file pipeline.log

examples:  ## Run all example scripts
	$(PY) -m examples.paper_examples
	$(PY) -m examples.semantic_examples
	$(PY) -m examples.minimality_examples

clean:  ## Remove generated files
	rm -rf output/ __pycache__/ .pytest_cache/ htmlcov/ .coverage .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
