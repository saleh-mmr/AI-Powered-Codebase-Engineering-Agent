.PHONY: up down logs check
up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f backend frontend

check:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest
	cd frontend && pnpm check && pnpm test && pnpm build
