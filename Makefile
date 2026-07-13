.PHONY: check test lint fmt

check: lint test

test:
	python3 -m pytest -q

lint:
	python3 -m ruff check lab tests
	python3 -m ruff format --check lab tests

fmt:
	python3 -m ruff format lab tests
