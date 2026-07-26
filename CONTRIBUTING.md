# Contribuir a CodeMentor

Gracias por tu interés en el proyecto. Esta guía es corta a propósito — el detalle técnico
vive en `CLAUDE.md` y `docs/`.

## Antes de empezar

1. Lee `README.md` (arquitectura, stack, cómo levantar el entorno) y `CLAUDE.md`
   (convenciones, puertos de desarrollo, comandos).
2. Para cambios grandes o de diseño, abre un issue primero — evita trabajo duplicado o una
   PR que no encaje con una decisión ya tomada (revisa `docs/adr/` antes de proponer una
   alternativa a algo ya documentado ahí).

## Entorno de desarrollo

```bash
cp .env.example .env
make up && make migrate && make seed
make web-install && make web-dev
```

Detalle completo, incluido despliegue, en `docs/despliegue.md`.

## Antes de abrir una PR

```bash
make lint && make typecheck && make test     # backend
make web-test                                 # frontend (cd apps/web && npm run lint && npx tsc -b)
```

Instala los hooks de pre-commit una vez (`ruff`, `ruff-format`, `mypy`, y validaciones
genéricas): `pre-commit install`.

- **Backend**: `ruff` (incluye `S`/flake8-bandit), `mypy --strict`. Sin excepciones de tipo
  sin justificar (`# type: ignore[código]` con motivo, no un `ignore` desnudo).
- **Frontend**: `oxlint`, `tsc -b`. Sin `any` nuevo sin justificar.
- Tests para todo cambio de comportamiento — no solo para que pase CI, sino porque son la
  única documentación ejecutable de qué garantiza el código.
- Migraciones de Alembic: probar `upgrade head` y `downgrade -1` localmente antes de subir.

## Convenciones de commit y PR

- Mensajes de commit en imperativo, explicando el *por qué* más que el *qué* (el diff ya
  dice qué cambió).
- Usa la plantilla de PR (`.github/PULL_REQUEST_TEMPLATE.md`) — no la vacíes.
- Una PR, un propósito. Si terminas tocando algo no relacionado, sepáralo.

## Reportar bugs / proponer features

Usa las plantillas de issue (`.github/ISSUE_TEMPLATE/`).
