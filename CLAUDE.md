# CLAUDE.md

Guía para trabajar en este repo con Claude Code. Contexto de producto y arquitectura
completo vive en `README.md` y `docs/` (MkDocs) — esto es solo lo operativo y las
convenciones que no son obvias leyendo el código.

## Estructura

Monorepo: `apps/api` (FastAPI, monolito modular) + `apps/web` (React 19 + Vite + TS).
Ver `docs/arquitectura.md` y los ADRs en `docs/adr/` para las decisiones de diseño.

## Comandos

Todos los comandos canónicos están en el `Makefile` de la raíz — úsalo en vez de invocar
`uv`/`npm` directo salvo que necesites flags que el target no expone:

```
make up / make down       # postgres+redis+api+worker en Docker
make lint / make typecheck / make test / make evals   # backend (apps/api)
make web-install / make web-dev / make web-test / make e2e   # frontend (apps/web)
make migrate / make migration m="mensaje"
make seed                 # institución + docente + 2 estudiantes + ejercicios demo
```

`make help` lista todo con su descripción.

## Puertos de desarrollo (no son los default)

Postgres en **5434** (no 5432), Redis en **6381** (no 6379) — `docker-compose.yml` los
remapea para no chocar con otros proyectos locales. Para correr `pytest`/`alembic` fuera
de Docker:

```bash
export DATABASE_URL="postgresql+asyncpg://logica:logica@localhost:5434/logica"
export REDIS_URL="redis://localhost:6381/0"
```

## Convenciones de código

- **Backend**: `ruff` (incluye el ruleset `S` de flake8-bandit) + `mypy --strict` +
  `structlog` (`logger = structlog.get_logger()` a nivel de módulo) + jerarquía de errores
  en `core/errors.py` (`NotFoundError`/`PermissionDeniedError`/`ConflictError`/
  `ValidationDomainError`/`ServiceUnavailableError`). Multi-tenencia es **100% a nivel de
  aplicación** (`WHERE institution_id == ...` explícito en cada query, sin RLS de Postgres
  — ver `docs/adr/006-multitenencia-sin-rls.md`): todo repositorio/query nuevo que toque
  una tabla con `TenantMixin` necesita ese filtro.
- **Frontend**: Tailwind v4 vía `@theme` en `src/styles/theme.css` (no hay
  `tailwind.config.js`). **Nunca uses `@theme inline`** — hornea los valores en build y
  rompe el theming en runtime (modo claro/oscuro); usa `@theme static`.
- **No crear módulos de abstracción compartida nuevos** cuando exista un idioma hermano
  reutilizable en el propio archivo o en un módulo vecino. Prefiere ~3 líneas duplicadas a
  una abstracción genérica prematura.
- **Aislamiento de fallos por ítem en loops que escriben a la DB**: en Postgres, una
  sentencia fallida aborta toda la transacción abierta — un `try/except` sin
  `async with db.begin_nested()` (SAVEPOINT) no aísla nada. Ver
  `content/service.py::enable_scheduled_topics` o `groups/service.py::bulk_enroll_csv`
  como referencia.
- **Gráficos** (`components/ui/Stat.tsx`, `BarList.tsx`, `ChartCard.tsx`): hand-rolled SVG
  con los tokens `--color-chart-*`, no una librería externa (ver razones en el historial de
  PRs). Todo gráfico lleva **etiquetas de valor visibles y una tabla `<details>Ver
  datos</details>` de respaldo** — el modo claro de la paleta categórica tiene contraste
  WARN en 3 de 6 slots, así que esa tabla no es opcional, es el canal de relevo.
- **Prompts de IA** (`ai/harness/prompts/templates/*.vN.j2`): un prompt publicado **nunca
  se edita in-situ**. Un cambio de contenido agrega `<tarea>.vN+1.j2` y actualiza
  `ACTIVE_PROMPT_VERSIONS` en `prompts/__init__.py`, para que las evals de regresión puedan
  seguir comparando ambas versiones.

## Git / commits

Solo crear commits cuando se pida explícitamente. Seguir el formato de
`.github/PULL_REQUEST_TEMPLATE.md` al abrir PRs.
