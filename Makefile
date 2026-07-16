.PHONY: help up up-ai up-sandbox down logs api-shell lint fmt typecheck test evals migrate migration seed sandbox-up

API_DIR := apps/api

help:
	@echo "make up            - levantar api+worker+postgres+redis"
	@echo "make up-ai         - además levantar ollama+langfuse (profile ai)"
	@echo "make up-sandbox    - además levantar piston (profile sandbox)"
	@echo "make down          - detener y remover contenedores"
	@echo "make logs          - seguir logs de todos los servicios"
	@echo "make lint          - ruff check + format --check"
	@echo "make fmt           - ruff format (aplica cambios)"
	@echo "make typecheck     - mypy strict"
	@echo "make test          - pytest (unit+integration)"
	@echo "make evals         - suite de evaluaciones de IA (modo mock por defecto)"
	@echo "make migrate       - aplicar migraciones alembic"
	@echo "make migration m=\"mensaje\" - crear migración autogenerada"
	@echo "make seed          - poblar datos demo"

up:
	docker compose up --build -d postgres redis api worker

up-ai:
	docker compose --profile ai up --build -d

up-sandbox:
	docker compose --profile sandbox up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

api-shell:
	docker compose exec api bash

lint:
	cd $(API_DIR) && uv run ruff check . && uv run ruff format --check .

fmt:
	cd $(API_DIR) && uv run ruff format . && uv run ruff check --fix .

typecheck:
	cd $(API_DIR) && uv run mypy src

test:
	cd $(API_DIR) && uv run pytest -m "not sandbox and not live" --cov=logica --cov-report=term-missing

evals:
	cd $(API_DIR) && uv run pytest tests/evals -m "not live"

migrate:
	cd $(API_DIR) && uv run alembic upgrade head

migration:
	cd $(API_DIR) && uv run alembic revision --autogenerate -m "$(m)"

seed:
	cd $(API_DIR) && uv run python -m scripts.seed
