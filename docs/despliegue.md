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

## Frontend (Fase 9)

SPA en React + TypeScript + Vite (`apps/web`) — modo nocturno único estilo Notion, Tailwind v4, TanStack Query, `motion` para animaciones. Ver `apps/web/README.md` para el detalle completo; resumen aquí:

```bash
make web-install   # o: cd apps/web && npm install --legacy-peer-deps
make web-dev        # servidor de desarrollo en http://localhost:5173
```

Requiere la API corriendo (`make up`) — `http://localhost:5173` ya está permitido en CORS por defecto. El cliente TypeScript (`apps/web/src/lib/api/schema.d.ts`) se genera desde el OpenAPI real con `./scripts/gen_openapi_client.sh` y se commitea, así que el build del frontend no depende de tener la API levantada.

**Tests**: `make web-test` (vitest, componentes/hooks) corre en CI en cada push (job `web`). `make e2e` (Playwright, 3 flujos contra el stack Docker real) es **local-only** — no corre en CI porque requeriría levantar todo el stack en Actions; se reevaluará en esta misma Fase 10 junto con el deploy.

### Hardening (Fase 10, RE-08)

- **Cabeceras de seguridad** (`core/security_headers.py`): toda respuesta incluye `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin` y `Permissions-Policy` restrictivo. `Strict-Transport-Security` solo se envía con `ENV=prod` — en dev/local la API corre sobre HTTP plano y un HSTS prematuro dejaría el navegador forzando HTTPS en `localhost`.
- **Límites de tasa** (`core/rate_limit.py`, vía `slowapi` + el mismo Redis del resto de la app): `POST /auth/register` (10/hora), `/auth/login` (10/min), `/auth/refresh` (60/min), `/auth/password-reset/request` (5/hora) y `/password-reset/confirm` (10/hora) por IP. También solo se activan con `ENV=prod` — en dev/test decenas de flujos y tests golpean `/auth/login` repetidamente y un límite real produciría `429` sin relación con lo que se está probando. `ENV=prod` es, por lo tanto, una variable requerida en el despliegue real (ver tabla de abajo).
- **CORS**: `CORS_ORIGINS` sigue siendo una lista explícita (por defecto solo `http://localhost:5173`); en producción debe incluir la URL real del frontend desplegado (Vercel).
- **Escaneo estático** (job `security` en CI, `apps/api`): `bandit -r src` (análisis AST de patrones inseguros) y `pip-audit` (CVEs conocidas en dependencias) corren en cada push/PR, además de los `select = ["E","F","I","UP","B","SIM","ASYNC","S"]` de ruff que ya cubren buena parte de OWASP en cada commit.

## Producción (tiers gratuitos)

| Componente | Proveedor gratuito | Notas |
|---|---|---|
| API + worker | Render (free tier, `render.yaml`) | Un solo web service; el worker de arq corre en el mismo proceso (`RUN_WORKER_IN_PROCESS=true`) — el free tier de Render no incluye background workers como servicio aparte (esos empiezan en $7/mes). Se duerme tras 15 min sin tráfico y tarda ~1 min en despertar en la siguiente petición. |
| PostgreSQL + pgvector | Supabase (free tier) | Incluye la extensión `pgvector` ya habilitada. |
| Redis | Upstash (free tier) | Compartido entre cachés (RE-02), colas de arq y el limiter de `slowapi`. |
| Frontend | Vercel (free tier, `apps/web/vercel.json`) | El rewrite a `index.html` es necesario para que las rutas de `react-router-dom` no den 404 al refrescar. |
| Observabilidad LLM | Langfuse Cloud (free tier) | Opcional — sin las keys, el tracing no-opera silenciosamente (§9.4). |
| Sandbox / Ollama | Solo local | Los tiers gratuitos de hosting no soportan contenedores privilegiados de larga duración; la demo pública usa Groq/Gemini para IA y deja el sandbox documentado para ejecución local. |

> **Nota sobre Fly.io**: el plan original consideraba Fly.io como alternativa a Render, pero desde 2024 ya no ofrece un tier verdaderamente gratuito (pide tarjeta desde el registro; solo da un *free trial* de 2 horas de VM o 7 días). Render sí sigue sin pedir tarjeta para su free tier, así que es la opción usada aquí.

### Pasos de configuración

1. **Supabase** (Postgres): crear un proyecto gratuito → `Database > Connection string` (modo `Transaction pooler`, puerto 6543) → habilitar la extensión `vector` desde `Database > Extensions` → aplicar migraciones apuntando `DATABASE_URL` a esa cadena: `cd apps/api && DATABASE_URL=... uv run alembic upgrade head`.
2. **Upstash** (Redis): crear una base gratuita → copiar la `UPSTASH_REDIS_URL` (formato `rediss://...`, con TLS) como `REDIS_URL`.
3. **Render** (API + worker in-process): "New > Blueprint", apuntar a este repo (detecta `render.yaml` en la raíz automáticamente) → completar en el dashboard las env vars marcadas `sync: false` en el blueprint (`DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS` con la URL real de Vercel, y opcionalmente `GROQ_API_KEY`/`GEMINI_API_KEY`/`LANGFUSE_*`) → Render hace auto-deploy en cada push a `main` sin necesidad de un workflow de GitHub Actions.
4. **Vercel** (frontend): "Add New > Project", importar este repo con *root directory* `apps/web` → variable de entorno `VITE_API_URL` apuntando a la URL pública de Render → auto-deploy en cada push a `main`, igual que Render.
5. **Langfuse Cloud** (opcional): crear proyecto gratuito → `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` en Render, `LANGFUSE_HOST=https://cloud.langfuse.com`.

### Variables de entorno requeridas en producción (Render)

| Variable | Valor |
|---|---|
| `ENV` | `prod` (activa rate limiting, HSTS y el worker in-process — ver "Hardening" arriba) |
| `RUN_WORKER_IN_PROCESS` | `true` |
| `DATABASE_URL` | cadena de conexión de Supabase |
| `REDIS_URL` | cadena de conexión de Upstash (`rediss://`) |
| `JWT_SECRET` | generado automáticamente por Render (`generateValue: true` en el blueprint) |
| `CORS_ORIGINS` | `["https://<tu-app>.vercel.app"]` |
| `GROQ_API_KEY` / `GEMINI_API_KEY` | opcionales — sin ellas, el harness de IA responde 503 con degradación amable (§9.4) en vez de romper el resto de la app |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | opcionales |

CI/CD: GitHub Actions (`ci.yml`) ejecuta lint + tests + evals + security en cada push/PR; Render y Vercel hacen el despliegue real por su propia integración nativa con GitHub al hacer merge a `main` — no hace falta un workflow de CD separado.
