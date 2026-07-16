# Lógica>_

Plataforma web de lógica de programación (PSeInt y Python) para el **INEM José Félix de Restrepo** (Medellín) — y, a la vez, un proyecto de referencia de **AI Engineering**: harness de modelos con enrutamiento y fallback, RAG pedagógico, agentes con supervisión humana obligatoria, skills reutilizables expuestas también vía **MCP**, evals y observabilidad de IA. Construido 100% con herramientas gratuitas u open-source.

> Estado: en construcción activa siguiendo el plan de implementación por fases. Ver progreso en la sección [Fases](#fases-de-implementación).

## Por qué este proyecto

Nace del [documento de requerimientos](docs/requerimientos.md) real de una institución educativa pública, y se implementa como un sistema profesional completo: no solo CRUD y autenticación, sino el ciclo completo de **AI Engineering** aplicado a un dominio con restricciones reales (menores de edad, cero presupuesto, conectividad intermitente, el docente siempre al mando del contenido).

## Arquitectura

Monolito modular stateless en FastAPI + PostgreSQL/pgvector + Redis, con el sandbox de ejecución de código y el servidor MCP como procesos aislados desde el día 1. Ver [`docs/arquitectura.md`](docs/arquitectura.md) para el diagrama de componentes completo y [ADR-001](docs/adr/001-monolito-modular.md) para la justificación de esta decisión.

**Stack**: Python 3.12 · FastAPI · SQLAlchemy 2 (async) · Alembic · PostgreSQL 16 + pgvector · Redis + arq · LiteLLM (Groq / Gemini / Ollama con fallback) · Pydantic AI · sentence-transformers · Piston (sandbox) · Langfuse · MCP SDK · React + Vite + TypeScript (Fase 9).

## Empezar

```bash
cp .env.example .env
make up          # postgres + redis + api + worker
make migrate
make seed
```

API en `http://localhost:8000/docs`. Guía completa en [`docs/despliegue.md`](docs/despliegue.md).

```bash
make lint        # ruff
make typecheck   # mypy strict
make test         # pytest
make evals        # suite de evaluaciones de IA
```

## Fases de implementación

| Fase | Contenido |
|---|---|
| 0 | Fundaciones: esqueleto, Docker, CI/CD, docs |
| 1 | Usuarios, roles, grupos |
| 2 | Contenidos, lenguajes, alcance curricular |
| 3 | Motor de ejercicios (plugins) + evaluaciones + calificación |
| 4 | Sandbox de ejecución de código |
| 5 | Harness de IA + RAG |
| 6 | Skills + 5 agentes de IA |
| 7 | Servidor MCP + evals + observabilidad |
| 8 | Seguimiento, reportes, escalabilidad |
| 9 | Frontend React |
| 10 | Hardening, deploy gratuito, portafolio |

## Licencia

Proyecto educativo. Ver el documento de requerimientos para el contexto institucional completo.
