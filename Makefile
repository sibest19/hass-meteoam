.PHONY: setup lint format test ha ha-stop ha-restart ha-logs clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Install dev dependencies and pre-commit hooks
	@scripts/setup

lint: ## Run ruff linter
	uv run ruff check custom_components/ tests/

format: ## Format code with ruff
	uv run ruff format custom_components/ tests/
	uv run ruff check --fix custom_components/ tests/

test: ## Run tests with pytest
	uv run pytest

ha: ## Start Home Assistant via docker compose
	docker compose up -d
	@echo "Home Assistant starting at http://localhost:8123"

ha-stop: ## Stop Home Assistant container
	docker compose down

ha-restart: ## Restart Home Assistant container (picks up code changes)
	docker compose restart homeassistant
	@echo "Home Assistant restarting..."

ha-logs: ## Follow Home Assistant logs
	docker compose logs -f homeassistant

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov .coverage
