import uuid
from collections.abc import Sequence
from typing import Any

import structlog
from arq.connections import RedisSettings
from arq.cron import cron
from arq.typing import WorkerCoroutine

from logica.config import get_settings
from logica.db import get_session_factory
from logica.modules.content.service import enable_scheduled_topics
from logica.modules.observability import repository as observability_repository
from logica.modules.reports.service import generate_group_report

logger = structlog.get_logger()

# Fase 13 (RE-08 free tier): cuánto se conservan los logs antes de podarse.
# Auditoría dura más porque es un rastro de cumplimiento, no solo debugging.
ERROR_LOG_RETENTION_DAYS = 30
AUDIT_LOG_RETENTION_DAYS = 180


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


async def record_error_log_job(ctx: dict[str, Any], payload: dict[str, Any]) -> None:
    """Fase 13: persiste un incidente técnico capturado por el manejador
    global de excepciones en `main.py`. Corre en el worker (nunca en la
    misma request que falló) porque la causa más probable de un 500 es
    justo una sesión de DB rota — escribir ahí fallaría cuando más importa.
    `institution_id`/`user_id` viajan como str (o None) porque arq serializa
    los argumentos del job — se reconstruyen a UUID aquí."""
    session_factory = get_session_factory()
    async with session_factory() as db:
        await observability_repository.create_error_log(
            db,
            institution_id=uuid.UUID(payload["institution_id"])
            if payload["institution_id"]
            else None,
            user_id=uuid.UUID(payload["user_id"]) if payload["user_id"] else None,
            path=payload["path"],
            method=payload["method"],
            status_code=payload["status_code"],
            exception_type=payload["exception_type"],
            message=payload["message"],
            stacktrace=payload["stacktrace"],
        )
        await db.commit()


async def prune_observability_logs_job(ctx: dict[str, Any]) -> dict[str, int]:
    """Retención diaria (RE-08 free tier): evita que error_logs/audit_logs
    crezcan sin límite en el almacenamiento gratuito de Supabase."""
    session_factory = get_session_factory()
    async with session_factory() as db:
        errors_deleted, audit_deleted = await observability_repository.prune_old_logs(
            db,
            error_log_retention_days=ERROR_LOG_RETENTION_DAYS,
            audit_log_retention_days=AUDIT_LOG_RETENTION_DAYS,
        )
        await db.commit()
    if errors_deleted or audit_deleted:
        logger.info(
            "observability_logs_pruned", errors_deleted=errors_deleted, audit_deleted=audit_deleted
        )
    return {"errors_deleted": errors_deleted, "audit_deleted": audit_deleted}


# Task functions are registered here incrementally as each phase introduces
# background jobs (reportes, rankings, ingesta RAG...).
functions: Sequence[WorkerCoroutine] = [
    ping,
    generate_group_report_job,
    record_error_log_job,
    prune_observability_logs_job,
]

# Runs every 5 minutes — frequent enough that a scheduled topic doesn't lag
# far behind class time, cheap enough to not matter at this scale.
cron_jobs = [
    cron(enable_scheduled_topics_job, minute=set(range(0, 60, 5))),
    cron(prune_observability_logs_job, hour={3}, minute={0}),
]


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
