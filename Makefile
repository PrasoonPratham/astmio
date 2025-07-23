.PHONY: format lint test install-dev clean pre-commit-install

install-dev:
	pip install -e ".[dev]"

pre-commit-install:
	pre-commit install

format:
	black astmio tests
	ruff format astmio tests

lint:
	ruff check astmio tests

lint-fix:
	ruff check --fix astmio tests

test:
	pytest tests/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

all: format lint test
