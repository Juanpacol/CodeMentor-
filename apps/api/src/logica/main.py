import asyncio
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from logica.ai.agents.router import router as ai_agents_router
from logica.ai.rag.router import router as rag_router
from logica.config import get_settings
from logica.core.errors import LogicaError
from logica.core.logging import configure_logging
from logica.core.rate_limit import limiter
from logica.core.request_id import RequestIdMiddleware
from logica.core.security_headers import SecurityHeadersMiddleware
from logica.db import get_engine
from logica.modules.assignments.router import router as assignments_router
from logica.modules.content.router import router as content_router
from logica.modules.evaluations.router import router as evaluations_router
from logica.modules.exercises.router import router as exercises_router
from logica.modules.groups.router import router as groups_router
from logica.modules.guides.router import router as guides_router
from logica.modules.notifications.router import router as notifications_router
from logica.modules.observability.models import truncate_message, truncate_stacktrace
from logica.modules.observability.router import router as observability_router
from logica.modules.observability.service import best_effort_actor
from logica.modules.progress.router import router as progress_router
from logica.modules.reports.router import router as reports_router
from logica.modules.rubrics.router import router as rubrics_router
from logica.modules.sandbox.router import router as sandbox_router
from logica.modules.users.router import auth_router, users_router
from logica.workers.inprocess import build_in_process_worker

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    # RF-16/RE-03: the API only ever enqueues report jobs, never builds the
    # file itself — the arq worker (same Redis queue as the scheduled-topics
    # cron) does the actual work off the request path.
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))

    # Despliegue gratuito (Fase 10, RUN_WORKER_IN_PROCESS): sin un segundo
    # servicio de pago para el worker, el mismo proceso uvicorn también
    # consume la cola de arq. En Docker Compose local esto se queda
    # desactivado — el worker sigue siendo su propio contenedor.
    in_process_worker = None
    in_process_worker_task: asyncio.Task[None] | None = None
    if settings.run_worker_in_process:
        in_process_worker = build_in_process_worker()
        in_process_worker_task = asyncio.create_task(in_process_worker.async_run())
        logger.info("in_process_worker_started")

    logger.info("app_startup", env=settings.env)
    try:
        yield
    finally:
        if in_process_worker_task is not None:
            in_process_worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await in_process_worker_task
        if in_process_worker is not None:
            await in_process_worker.close()
        await app.state.redis.aclose()
        await app.state.arq_pool.aclose()
        await get_engine().dispose()
        logger.info("app_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(log_level=settings.log_level)
    app = FastAPI(
        title="CodeMentor API",
        description=(
            "Plataforma de lógica de programación (PSeInt y Python) — INEM José Félix de Restrepo"
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)

    # RE-08 hardening: límites de tasa en endpoints de auth (solo ENV=prod,
    # ver core/rate_limit.py).
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    # Añadido último para quedar como middleware más externo (Starlette envuelve
    # en orden inverso de registro): el request_id debe existir antes que
    # cualquier otro middleware/handler pueda necesitarlo.
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "code": "rate_limited",
                "message": "Demasiados intentos. Intenta de nuevo en unos minutos.",
                "hint": None,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    # General HTTP metrics (§4.4/§9.4 "observabilidad"): request count/latency
    # by route, method, status — separate from the AI-specific metrics in
    # ai.harness.metrics, exposed on the same /metrics endpoint for Prometheus.
    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    async def _record_incident(
        request: Request, exc: Exception, *, status_code: int, stacktrace: str
    ) -> None:
        """Persiste un incidente en `error_logs` vía arq — nunca en la misma
        request que falló: si la causa fue una sesión de DB rota, escribir ahí
        fallaría justo cuando más importa."""
        user_id, institution_id = best_effort_actor(request)
        payload = {
            "institution_id": str(institution_id) if institution_id else None,
            "user_id": str(user_id) if user_id else None,
            "path": request.url.path,
            "method": request.method,
            "status_code": status_code,
            "exception_type": type(exc).__name__,
            "message": truncate_message(str(exc)),
            "stacktrace": truncate_stacktrace(stacktrace),
            "request_id": getattr(request.state, "request_id", None),
        }
        try:
            await request.app.state.arq_pool.enqueue_job("record_error_log_job", payload)
        except Exception:
            logger.exception("error_log_enqueue_failed")

    @app.exception_handler(LogicaError)
    async def handle_logica_error(request: Request, exc: LogicaError) -> JSONResponse:
        # Un 503 no es un error de dominio del usuario: es una dependencia caída
        # (§9.4 — todos los proveedores de IA, el sandbox...). El estudiante ve la
        # degradación amable igual, pero sin esto nadie más se enteraba: el handler
        # de `Exception` de abajo no lo alcanza (FastAPI despacha por especificidad
        # de clase) y `ai_errors_total` solo vive en /metrics, que este despliegue
        # gratuito no raspa. Así el incidente aparece en el mismo `error_logs` que
        # ya lee el ErrorLogTab de la Fase 13.
        #
        # Solo los 503: un estudiante que agota su cupo diario o pide algo sin
        # permiso son 4xx esperados, no incidentes — registrarlos ahogaría en ruido
        # justo la señal que esto quiere hacer visible.
        if exc.status_code == 503:
            # `errors` lo trae AllProvidersFailedError con el detalle por proveedor
            # ("groq/...: 429", "gemini/...: ..."), que es lo único accionable acá
            # — el traceback de un 503 solo apunta al harness. `getattr` y no un
            # import de ai.harness.router para no acoplar main.py a ese módulo.
            provider_errors = getattr(exc, "errors", None)
            await _record_incident(
                request,
                exc,
                status_code=503,
                stacktrace="\n".join(provider_errors)
                if provider_errors
                else traceback.format_exc(),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code.value,
                "message": exc.message,
                "hint": exc.hint,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    # Fase 13: los LogicaError arriba son errores de dominio esperados y ya
    # tienen su propio manejador — FastAPI despacha por especificidad de
    # clase, así que este handler más genérico solo atrapa lo que de verdad
    # es un bug (excepciones no controladas / 500 reales), nunca les pisa el
    # handler específico. Nunca se filtra el texto crudo de la excepción al
    # cliente; el incidente se persiste vía arq (nunca en la misma request
    # que falló — si la causa fue una sesión de DB rota, escribir ahí
    # fallaría justo cuando más importa).
    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        await _record_incident(request, exc, status_code=500, stacktrace=traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "Error interno del servidor.",
                "hint": None,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/db", tags=["health"])
    async def health_db() -> dict[str, str]:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.get("/health/redis", tags=["health"])
    async def health_redis(request: Request) -> dict[str, str]:
        await request.app.state.redis.ping()
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(groups_router)
    app.include_router(content_router)
    app.include_router(guides_router)
    app.include_router(exercises_router)
    app.include_router(evaluations_router)
    app.include_router(sandbox_router)
    app.include_router(ai_agents_router)
    app.include_router(rag_router)
    app.include_router(progress_router)
    app.include_router(reports_router)
    app.include_router(rubrics_router)
    app.include_router(assignments_router)
    app.include_router(observability_router)
    app.include_router(notifications_router)

    return app


app = create_app()
