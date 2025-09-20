SHELL = /bin/sh

.DEFAULT_GOAL:=help

.PHONY: shell
shell: ## Activate poetry shell.
	poetry shell

.PHONY: install
install: ## Install dependencies using poetry.
	@command -v poetry &>/dev/null || echo "ERROR: missing software required (pip install poetry)" && poetry install

.PHONY: run-uvicorn
run-uvicorn: ## Run uvicorn server.
	poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000