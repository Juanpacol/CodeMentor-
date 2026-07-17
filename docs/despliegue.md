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

### Sandbox de ejecución de código (Piston)

Piston self-hosted arranca sin lenguajes instalados. Tras `make up-sandbox`, instalar el runtime necesario (Python es el único requerido para RF-09..13 hoy; C/C++/Java/PHP se agregan igual cuando se necesiten, RE-06):

```bash
make sandbox-install-python
```

Los ejercicios de tipo `live_code` (§4.2, "reto de código en vivo") se prueban contra un Piston real:

```bash
make test-sandbox   # requiere up-sandbox + sandbox-install-python
```

Estas pruebas están marcadas `@pytest.mark.sandbox` y quedan excluidas de `make test`/CI por defecto, ya que dependen de infraestructura que CI no levanta. El intérprete propio de PSeInt (validación de sintaxis y trazado de variables, RF-26) no depende de Piston — corre embebido en la API y sus pruebas sí forman parte de `make test`.

### Harness de IA (Groq / Gemini / Ollama + Langfuse)

El harness (`ai/harness/`, §9.1) enruta cada tarea a una cadena de modelos con respaldo. Para usarlo con proveedores reales, completar en `.env`:

```bash
GROQ_API_KEY=...      # https://console.groq.com/keys — free tier
GEMINI_API_KEY=...    # https://aistudio.google.com/apikey — free tier
```

Ollama (`make up-ai`) sirve como último respaldo local, sin API key. Sin ninguna key configurada, el harness sigue funcionando en pruebas (la función `_completion_fn` se sustituye por un doble en los tests); en uso real, si los tres proveedores de la cadena fallan, la petición responde `503` con un mensaje claro en español (`AllProvidersFailedError`, §9.4 "plan de contingencia sin IA") — nunca un 500 crudo, y la funcionalidad no relacionada con IA sigue intacta.

Langfuse (perfil `ai`, `make up-ai`) traza cada llamada (modelo, tokens, si vino de caché) automáticamente en cuanto `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` estén configurados; sin ellos, el tracing no-opera silenciosamente (nunca rompe una petición). El panel de Langfuse queda disponible en `http://localhost:3010` tras `make up-ai`.

### Ingesta de material para el RAG pedagógico

El Agente Tutor (Fase 6) fundamenta sus pistas en material real del curso, ingerido con:

```bash
uv run python -m scripts.ingest_rag --institution <uuid-institución> --title "Referencia PSeInt" material.md
```

Esto trocea el documento, calcula embeddings locales (`intfloat/multilingual-e5-small`, gratis, sin llamada externa) y los guarda en `pgvector`. La recuperación (`ai/rag/retriever.py`) combina similitud vectorial con búsqueda de texto completo en español — ver `docs/adr/003-harness-como-fachada-unica.md`.

### Servidor MCP (Fase 7, §9.2)

El servidor MCP (`logica.mcp.server`, ver `docs/adr/005-mcp-server-dentro-de-apps-api.md`) reexpone 4 tools (`validate_pseint`, `run_code`, `generate_exercise_draft`, `get_group_summary`) y 2 resources (`curriculum://`, `stats://`) a cualquier cliente MCP — pensado como demo de portafolio conectándolo a Claude Desktop o Claude Code. Todo tool/resource requiere el mismo `access_token` JWT que devuelve `POST /auth/login`, y solo lo acepta si pertenece a un docente o administrador (§9.2 "nunca para estudiantes").

Para conectarlo a **Claude Desktop**, agregar a su `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "logica": {
      "command": "uv",
      "args": ["run", "--project", "/ruta/a/CodeMentor/apps/api", "python", "-m", "logica.mcp.server"]
    }
  }
}
```

Esto arranca el servidor en transporte `stdio` (el modo por defecto). Cada llamada a una tool pide el `access_token` como primer argumento — pégalo desde una sesión de login real (por ejemplo, la respuesta de `POST /auth/login` en la documentación OpenAPI en `/docs`).

Para exponerlo por red en vez de como subproceso local:

```bash
uv run python -m logica.mcp.server --http   # transporte streamable-http
```

### Observabilidad: `/metrics` (Prometheus)

Además del tracing de Langfuse (por llamada de IA), la API expone métricas Prometheus en `GET /metrics` (montado por `prometheus-fastapi-instrumentator`, sin autenticación — pensado para scraping interno, no para exponer públicamente sin un proxy que lo proteja). Incluye:

- Métricas HTTP generales (latencia, tasa de error, conteo de requests por ruta) — automáticas.
- Métricas propias del harness de IA (`ai/harness/metrics.py`): `ai_requests_total` (por tarea/modelo/si vino de caché), `ai_errors_total` (por tarea/tipo de error), `ai_request_latency_seconds`, `ai_tokens_total` (por tarea).

Para un dashboard local rápido, apuntar un Prometheus local a `http://localhost:8000/metrics` (ajustar el puerto según `API_HOST_PORT`) — no forma parte de `docker-compose.yml` por defecto para mantener el stack liviano; Grafana/Prometheus quedan como algo que cualquier desplegador puede añadir apuntando a ese endpoint ya expuesto.

### Reportes exportables (Fase 8, RF-16, RE-03)

`POST /groups/{id}/reports` (`{"format": "xlsx"|"pdf", "period_id": "..."}` opcional) encola un job de arq y responde `202` de inmediato con el job en estado `pending` — la generación real (consultas + `openpyxl`/`weasyprint`) corre en el worker, nunca bloquea la API. `GET /reports/{job_id}` permite hacer polling del estado; `GET /reports/{job_id}/download` transmite el archivo una vez `status == "done"`.

El archivo generado se escribe en `settings.reports_dir` (`REPORTS_DIR`, por defecto `/app/reports` en Docker) — un volumen (`reports_data`) compartido entre `api` y `worker` en `docker-compose.yml`, para que ambos procesos vean el mismo archivo sin necesitar almacenamiento de objetos (S3/similar) y mantener el despliegue 100% gratuito.

La exportación a PDF depende de las mismas librerías de sistema de WeasyPrint que ya instala `apps/api/Dockerfile` (Pango/GdkPixbuf) — si se corre la API fuera de Docker en una máquina que no las tiene, la exportación a Excel sigue funcionando, pero la de PDF falla; los tests que ejercitan ese camino están marcados `@pytest.mark.pdf` y se excluyen de `make test` por la misma razón que los de sandbox.

### Caché de lecturas calientes (RE-02)

El temario de una institución (`GET /topics`, `GET /groups/{id}/curriculum`) se cachea en Redis con `cache-aside` (clave `topics:{institution_id}`, TTL 5 minutos) e invalidación explícita cuando un docente crea o edita un tema — el mismo patrón que ya usaba la tabla de posiciones de evaluaciones (Fase 3) para rankings. No requiere configuración adicional.

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
