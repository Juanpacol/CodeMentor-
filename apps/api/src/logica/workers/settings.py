from typing import Any

from arq.connections import RedisSettings

from logica.config import get_settings


async def ping(ctx: dict[str, Any]) -> str:
    """Trivial job kept registered so the worker has at least one task while
    real jobs (habilitación programada, reportes, rankings, ingesta RAG...) are
    added incrementally in later phases."""
    return "pong"


# Task functions are registered here incrementally as each phase introduces
# background jobs (scheduled topic enablement, reports, rankings, RAG ingestion...).
functions: list[object] = [ping]


async def startup(ctx: dict[str, Any]) -> None:
    pass


async def shutdown(ctx: dict[str, Any]) -> None:
    pass


class WorkerSettings:
    functions = functions
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
