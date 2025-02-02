.PHONY: install test lint format clean build deploy-dev deploy-prod

PYTHON=python3.12
VENV=.venv
BIN=$(VENV)/bin

install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -r src/layers/common_layer/requirements.txt
	$(BIN)/pip install -r requirements-dev.txt

test:
	$(BIN)/pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	$(BIN)/black src/ tests/
	$(BIN)/isort src/ tests/
	$(BIN)/flake8 src/ tests/
	$(BIN)/mypy src/ tests/

format:
	$(BIN)/black src/ tests/
	$(BIN)/isort src/ tests/

clean:
	rm -rf $(VENV)
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf .mypy_cache
	rm -rf .aws-sam
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

build:
	sam build

deploy-dev:
	sam deploy --config-env dev

deploy-prod:
	sam deploy --config-env prod 