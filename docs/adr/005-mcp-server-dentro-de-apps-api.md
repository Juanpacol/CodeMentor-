# ADR-005: El servidor MCP vive en `apps/api/src/logica/mcp`, no en `apps/mcp_server/`

## Estado

Aceptado — 2026-07-16.

## Contexto

El plan original de arquitectura (Fase 7, §9.2) ubicaba el servidor MCP en un directorio propio, `apps/mcp_server/`, como si fuera un paquete Python separado de la API — el mismo patrón que ya se había planeado (y luego revisado) para el sandbox en la Fase 4 (ver ADR-002, decisión 1).

El servidor MCP no reexpone lógica nueva: sus 4 tools y 2 resources son wrappers delgados sobre funciones que ya existen en `logica.modules.sandbox`, `logica.ai.agents` y `logica.modules.content` — la validación de PSeInt, la ejecución en Piston, la generación de ejercicios y el resumen de grupo. El único código genuinamente nuevo es la resolución de identidad (`mcp/auth.py`, que decodifica el mismo JWT de `/auth/login`) y el cableado de `@mcp.tool()`/`@mcp.resource()`.

## Decisión

El servidor MCP vive en `apps/api/src/logica/mcp/`, como un módulo más dentro del paquete `logica`, en vez de en un directorio `apps/mcp_server/` separado.

Razones, en la misma línea que ADR-002:

1. **Mismo entorno de dependencias.** El servidor MCP importa directamente `logica.ai.agents.exercise_generator`, `logica.ai.agents.learning_analytics`, `logica.modules.sandbox.piston_client` y `logica.modules.content.service` — funciones async que a su vez dependen de SQLAlchemy, Redis, el harness de IA, etc. Un paquete hermano (`apps/mcp_server/`) necesitaría declarar `apps/api` como dependencia local (vía `path = "../api"` en su propio `pyproject.toml`) solo para reexportar exactamente el mismo código; no habría ninguna frontera real que ese segundo paquete estuviera protegiendo.
2. **Un solo `uv sync`, un solo lockfile.** Mantener dos `pyproject.toml` sincronizados para un servidor que no tiene ninguna dependencia que la API no tenga ya (el SDK `mcp` es la única añadida) es complejidad sin beneficio — mismo argumento que ya aplicó al worker de arq (`logica.workers`, un proceso separado pero **el mismo paquete**).
3. **El precedente ya existe.** El worker de arq (`workers/settings.py`) es exactamente este patrón: un proceso independiente (`uv run arq logica.workers.settings.WorkerSettings`) que vive dentro del mismo paquete `logica`. El servidor MCP sigue la misma convención: `uv run python -m logica.mcp.server` es un proceso aparte del servidor HTTP de FastAPI, pero comparte package, dependencias y `pyproject.toml`.
4. **Autenticación reutilizada, no un sistema nuevo.** `mcp/auth.py` no crea un mecanismo de credenciales aparte para MCP — decodifica el mismo `access_token` JWT que ya emite `/auth/login` (§9.2 "autenticación por token de docente"). Tenerlo en el mismo paquete hace ese acoplamiento explícito en el código, no solo en la documentación.

`apps/mcp_server/` tal como aparecía en el plan original no se creó como directorio separado; su rol quedó cubierto por `apps/api/src/logica/mcp/` (auth + servidor FastMCP) exactamente como `apps/sandbox/` quedó cubierto por `apps/api/src/logica/modules/sandbox/` en la Fase 4.

## Consecuencias

- Desplegar el servidor MCP como un proceso propio (por ejemplo, para que Claude Desktop se conecte por stdio, o un cliente remoto por `streamable-http`) sigue siendo posible sin cambiar nada de esta decisión: es un entrypoint (`logica.mcp.server:main`) dentro del mismo contenedor/imagen que ya construye `apps/api/Dockerfile`, no un contenedor nuevo.
- Si en el futuro el servidor MCP necesitara escalar o desplegarse de forma independiente del API HTTP (por ejemplo, con su propio ciclo de release), el camino de migración es el mismo que se documentó para Piston en ADR-002: extraerlo a un proceso realmente externo solo si aparece una razón de aislamiento o escalado que lo justifique — no por syntonía con la estructura de carpetas del plan original.
- Cualquier tool/resource nuevo que se añada al servidor MCP debe seguir resolviendo identidad vía `mcp.auth.resolve_teacher()` y nunca llamar a un proveedor LLM directamente — las mismas invariantes de ADR-003 (harness como única puerta de entrada a un LLM) y ADR-004 (agentes como funciones planas sobre el harness) aplican sin excepción a este nuevo consumidor.
