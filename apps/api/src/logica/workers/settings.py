import uuid
from typing import Any

import structlog
from arq.connections import RedisSettings
from arq.cron import cron

from logica.config import get_settings
from logica.db import get_session_factory
from logica.modules.content.service import enable_scheduled_topics
from logica.modules.reports.service import generate_group_report

logger = structlog.get_logger()


async def ping(ctx: dict[str, Any]) -> str:
    """Trivial job kept registered so the worker has at least one task while
    real jobs (habilitación programada, reportes, rankings, ingesta RAG...) are
    added incrementally in later phases."""
    return "pong"


async def enable_scheduled_topics_job(ctx: dict[str, Any]) -> int:
    """Flips topics whose `scheduled_enable_at` is due (RF-24). The platform
    never advances content on its own — this only executes a date a teacher
    explicitly chose in advance."""
    session_factory = get_session_factory()
    async with session_factory() as db:
        count = await enable_scheduled_topics(db)
        await db.commit()
    if count:
        logger.info("scheduled_topics_enabled", count=count)
    return count


async def generate_group_report_job(ctx: dict[str, Any], report_job_id: str) -> None:
    """RF-16/RE-03: builds the actual export file. Enqueued by
    `POST /groups/{id}/reports` — never runs on the request path."""
    session_factory = get_session_factory()
    async with session_factory() as db:
        await generate_group_report(db, uuid.UUID(report_job_id))
    logger.info("report_generated", report_job_id=report_job_id)


# Task functions are registered here incrementally as each phase introduces
# background jobs (reportes, rankings, ingesta RAG...).
functions: list[object] = [ping, generate_group_report_job]

# Runs every 5 minutes — frequent enough that a scheduled topic doesn't lag
# far behind class time, cheap enough to not matter at this scale.
cron_jobs = [cron(enable_scheduled_topics_job, minute=set(range(0, 60, 5)))]


async def startup(ctx: dict[str, Any]) -> None:
    pass


async def shutdown(ctx: dict[str, Any]) -> None:
    pass


class WorkerSettings:
    functions = functions
    cron_jobs = cron_jobs
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
