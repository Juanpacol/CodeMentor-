from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis
from sqlalchemy import text

from logica.ai.agents.router import router as ai_agents_router
from logica.config import get_settings
from logica.core.errors import LogicaError
from logica.db import get_engine
from logica.modules.content.router import router as content_router
from logica.modules.evaluations.router import router as evaluations_router
from logica.modules.exercises.router import router as exercises_router
from logica.modules.groups.router import router as groups_router
from logica.modules.sandbox.router import router as sandbox_router
from logica.modules.users.router import auth_router, users_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("app_startup", env=settings.env)
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await get_engine().dispose()
        logger.info("app_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Lógica>_ API",
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

    # General HTTP metrics (§4.4/§9.4 "observabilidad"): request count/latency
    # by route, method, status — separate from the AI-specific metrics in
    # ai.harness.metrics, exposed on the same /metrics endpoint for Prometheus.
    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    @app.exception_handler(LogicaError)
    async def handle_logica_error(request: Request, exc: LogicaError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

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

    return app


app = create_app()
