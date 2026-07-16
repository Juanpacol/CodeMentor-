# Guía de despliegue

## Desarrollo local (Docker Compose)

Requisitos: Docker y Docker Compose. Todo el stack corre en contenedores; no se necesita Python ni Node instalados en la máquina para levantar el sistema (sí para desarrollo activo con `uv`/`npm`).

```bash
cp .env.example .env          # ajustar secretos/API keys si se van a usar agentes de IA
make up                       # postgres + redis + api + worker
make migrate                  # aplica migraciones
make seed                     # datos demo
```

API disponible en `http://localhost:8000`, documentación OpenAPI en `http://localhost:8000/docs`.

Perfiles opcionales:

```bash
make up-ai        # + Ollama (fallback local) + Langfuse (observabilidad)
make up-sandbox   # + Piston (ejecución aislada de código)
```

## Producción (tiers gratuitos)

Definido en detalle en la Fase 10 del plan de implementación. Resumen:

| Componente | Proveedor gratuito |
|---|---|
| API + worker | Fly.io o Render (free tier) |
| PostgreSQL + pgvector | Supabase (free tier) |
| Redis | Upstash (free tier) |
| Frontend | Vercel (free tier) |
| Observabilidad LLM | Langfuse Cloud (free tier) |
| Sandbox / Ollama | Solo local — los tiers gratuitos de hosting no soportan contenedores privilegiados de larga duración; la demo pública usa Groq/Gemini para IA y deja el sandbox documentado para ejecución local. |

CI/CD: GitHub Actions ejecuta lint + tests + evals en cada PR; el despliegue a producción ocurre en merge a `main` (Fase 10).
