.PHONY: install dev test lint format clean

install:
	pip install -e ".[dev]"

dev:
	openvort start

test:
	pytest -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
