# Convenience wrappers only. Every target calls a script, so `make` is optional:
# the same commands run with plain `bash scripts/<name>.sh` (Windows Git Bash included).

.PHONY: up down db-reset dev openapi verify

up: ## Start PostgreSQL and Mailpit and wait for their healthchecks
	docker compose up -d --wait postgres mailpit

down: ## Stop the Compose services
	docker compose down

db-reset: ## Drop the local database volume, start PostgreSQL, migrate to head
	docker compose down -v
	docker compose up -d --wait postgres mailpit
	cd backend && uv run alembic upgrade head

dev: ## Run the API (8000) and the web app (3000) in development mode
	bash scripts/dev.sh

openapi: ## Regenerate frontend/src/lib/api/types.gen.ts from the backend
	bash scripts/export-openapi.sh

verify: ## The skeleton verification command (all CI checks locally)
	bash scripts/verify.sh
