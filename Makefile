.PHONY: help up up-ai up-sandbox down logs api-shell lint fmt typecheck test test-sandbox test-pdf evals evals-compare migrate migrate-test migration seed sandbox-install-python web-install web-dev web-test e2e load

API_DIR := apps/api
WEB_DIR := apps/web

-include .env
export

POSTGRES_USER ?= logica
POSTGRES_PASSWORD ?= logica
POSTGRES_DB ?= logica
POSTGRES_HOST_PORT ?= 5434
REDIS_HOST_PORT ?= 6381
JWT_SECRET ?= change-me-in-env-please-use-a-long-random-value

# DATABASE_URL/REDIS_URL for commands run on the host (outside Docker) against
# the containers' published ports — distinct from the in-container URLs
# (service DNS names) used by api/worker themselves via docker-compose.yml.
HOST_DATABASE_URL := postgresql+asyncpg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_HOST_PORT)/$(POSTGRES_DB)
HOST_TEST_DATABASE_URL := postgresql+asyncpg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_HOST_PORT)/logica_test
HOST_REDIS_URL := redis://localhost:$(REDIS_HOST_PORT)/0
HOST_TEST_REDIS_URL := redis://localhost:$(REDIS_HOST_PORT)/1
PISTON_HOST_PORT ?= 2000
HOST_SANDBOX_URL := http://localhost:$(PISTON_HOST_PORT)
API_HOST_PORT ?= 8000
HOST_API_URL := http://localhost:$(API_HOST_PORT)

help:
	@echo "make up            - levantar api+worker+postgres+redis"
	@echo "make up-ai         - además levantar ollama+langfuse (profile ai)"
	@echo "make up-sandbox    - además levantar piston (profile sandbox)"
	@echo "make down          - detener y remover contenedores"
	@echo "make logs          - seguir logs de todos los servicios"
	@echo "make lint          - ruff check + format --check"
	@echo "make fmt           - ruff format (aplica cambios)"
	@echo "make typecheck     - mypy strict"
	@echo "make test          - pytest contra logica_test (unit+integration)"
	@echo "make test-sandbox  - pytest incluyendo pruebas reales contra Piston (requiere up-sandbox)"
	@echo "make test-pdf      - pytest de exportación a PDF (requiere libs de sistema de WeasyPrint)"
	@echo "make sandbox-install-python - instala el runtime de Python en Piston"
	@echo "make evals         - suite de evaluaciones de IA (modo mock por defecto)"
	@echo "make migrate       - aplicar migraciones alembic (DB de desarrollo)"
	@echo "make migrate-test  - aplicar migraciones alembic (DB de test)"
	@echo "make migration m=\"mensaje\" - crear migración autogenerada"
	@echo "make seed          - poblar datos demo"
	@echo "make web-install   - instalar dependencias del frontend"
	@echo "make web-dev       - levantar el frontend en modo desarrollo (puerto 5173)"
	@echo "make web-test      - vitest del frontend"
	@echo "make web-api-types - regenerar src/lib/api/schema.d.ts desde el OpenAPI del backend"
	@echo "make e2e           - Playwright (requiere make up + web-dev corriendo, o los levanta solo)"

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
	cd $(API_DIR) && \
	DATABASE_URL="$(HOST_TEST_DATABASE_URL)" REDIS_URL="$(HOST_TEST_REDIS_URL)" \
	uv run pytest -m "not sandbox and not live and not pdf" --cov=logica --cov-report=term-missing

test-sandbox:
	cd $(API_DIR) && \
	DATABASE_URL="$(HOST_TEST_DATABASE_URL)" REDIS_URL="$(HOST_TEST_REDIS_URL)" SANDBOX_URL="$(HOST_SANDBOX_URL)" \
	uv run pytest -m "sandbox"

test-pdf:
	cd $(API_DIR) && \
	DATABASE_URL="$(HOST_TEST_DATABASE_URL)" REDIS_URL="$(HOST_TEST_REDIS_URL)" \
	uv run pytest -m "pdf"

sandbox-install-python:
	curl -s -X POST http://localhost:$${PISTON_HOST_PORT:-2000}/api/v2/packages \
		-H "Content-Type: application/json" \
		-d '{"language": "python", "version": "3.10.0"}'

# DATABASE_URL/REDIS_URL explícitos por la misma razón que `test`: sin esto,
# el `.env` de la raíz (hostnames internos de docker-compose, `postgres`/
# `redis`, no resolubles desde el host) pisa lo que el shell exportó,
# rompiendo la corrida siempre — no solo quisquilloso, un `make evals` a
# secas nunca funciona sin esta línea.
evals:
	cd $(API_DIR) && \
	DATABASE_URL="$(HOST_TEST_DATABASE_URL)" REDIS_URL="$(HOST_TEST_REDIS_URL)" \
	uv run pytest tests/evals -m "not live"

# Ítem 15: corre el dataset de una tarea contra varias versiones de su
# plantilla a la vez, para comparar side-by-side antes de promover una
# versión nueva a activa. Ej: make evals-compare TASK=progressive_hint V=1,2
evals-compare:
	cd $(API_DIR) && \
	DATABASE_URL="$(HOST_TEST_DATABASE_URL)" REDIS_URL="$(HOST_TEST_REDIS_URL)" \
	PROMPT_VERSIONS=$$(python3 -c "print(','.join(f'$(TASK)={v}' for v in '$(V)'.split(',')))") \
	uv run pytest tests/evals -k $(TASK) -v -m "not live"

migrate:
	cd $(API_DIR) && DATABASE_URL="$(HOST_DATABASE_URL)" uv run alembic upgrade head

migrate-test:
	cd $(API_DIR) && DATABASE_URL="$(HOST_TEST_DATABASE_URL)" uv run alembic upgrade head

migration:
	cd $(API_DIR) && DATABASE_URL="$(HOST_DATABASE_URL)" uv run alembic revision --autogenerate -m "$(m)"

seed:
	cd $(API_DIR) && DATABASE_URL="$(HOST_DATABASE_URL)" uv run python -m scripts.seed

web-install:
	cd $(WEB_DIR) && npm install --legacy-peer-deps

web-dev:
	cd $(WEB_DIR) && npm run dev

web-test:
	cd $(WEB_DIR) && npm run test -- --run

# Regenera el cliente tipado del frontend (src/lib/api/schema.d.ts) desde el
# OpenAPI del backend. Volca el esquema importando la app en vez de pedírselo a
# un servidor: así no hace falta `make up`, y sobre todo no se corre el riesgo de
# generar tipos contra un contenedor con código viejo.
web-api-types:
	cd $(API_DIR) && uv run python -c "import json; from logica.main import create_app; print(json.dumps(create_app().openapi()))" > /tmp/codementor-openapi.json
	cd $(WEB_DIR) && npx openapi-typescript /tmp/codementor-openapi.json -o src/lib/api/schema.d.ts

# Requiere el stack de Docker arriba (make up) — Playwright levanta el
# servidor de Vite por su cuenta si no está ya corriendo (ver
# playwright.config.ts, reuseExistingServer).
e2e:
	cd $(WEB_DIR) && npm run e2e

# Ítem 17: k6 sobre el flujo de evaluación cronometrada. Requiere `make up` +
# `make seed` corridos antes (usa la institución/docente demo) y k6 instalado
# localmente (`brew install k6`). Local-only, como `e2e` — no corre en CI.
# Ej: make load VUS=50 QUESTIONS=25 DURATION=30s
load:
	k6 run $(API_DIR)/tests/load/evaluation_flow.js \
		--env BASE_URL=$(HOST_API_URL) \
		--env VUS=$(VUS) --env QUESTIONS=$(QUESTIONS) --env DURATION=$(DURATION)
