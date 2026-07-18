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
from logica.config import get_settings
from logica.core.errors import LogicaError
from logica.core.rate_limit import limiter
from logica.core.security_headers import SecurityHeadersMiddleware
from logica.db import get_engine
from logica.modules.content.router import router as content_router
from logica.modules.evaluations.router import router as evaluations_router
from logica.modules.exercises.router import router as exercises_router
from logica.modules.groups.router import router as groups_router
from logica.modules.observability.models import truncate_message, truncate_stacktrace
from logica.modules.observability.router import router as observability_router
from logica.modules.observability.service import best_effort_actor
from logica.modules.progress.router import router as progress_router
from logica.modules.reports.router import router as reports_router
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
    # ver core/rate_limit.py). El handler propio mantiene el mismo formato
    # {"detail": "..."} que el resto de errores de la API.
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": "Demasiados intentos. Intenta de nuevo en unos minutos."},
        )

    # General HTTP metrics (§4.4/§9.4 "observabilidad"): request count/latency
    # by route, method, status — separate from the AI-specific metrics in
    # ai.harness.metrics, exposed on the same /metrics endpoint for Prometheus.
    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    @app.exception_handler(LogicaError)
    async def handle_logica_error(request: Request, exc: LogicaError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

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
        user_id, institution_id = best_effort_actor(request)
        payload = {
            "institution_id": str(institution_id) if institution_id else None,
            "user_id": str(user_id) if user_id else None,
            "path": request.url.path,
            "method": request.method,
            "status_code": 500,
            "exception_type": type(exc).__name__,
            "message": truncate_message(str(exc)),
            "stacktrace": truncate_stacktrace(traceback.format_exc()),
        }
        try:
            await request.app.state.arq_pool.enqueue_job("record_error_log_job", payload)
        except Exception:
            logger.exception("error_log_enqueue_failed")
        return JSONResponse(status_code=500, content={"detail": "Error interno del servidor."})

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
    app.include_router(exercises_router)
    app.include_router(evaluations_router)
    app.include_router(sandbox_router)
    app.include_router(ai_agents_router)
    app.include_router(progress_router)
    app.include_router(reports_router)
    app.include_router(observability_router)

    return app


app = create_app()
