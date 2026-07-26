import uuid
from collections.abc import Sequence
from typing import Any

import structlog
from arq import ArqRedis
from arq.connections import RedisSettings
from arq.cron import cron
from arq.typing import WorkerCoroutine
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError

from logica.ai.agents.config_service import is_agent_enabled
from logica.ai.agents.guide_writer import write_guide
from logica.ai.agents.models import AgentName
from logica.config import get_settings
from logica.db import get_session_factory
from logica.modules.content.models import TopicGroupStateValue
from logica.modules.content.repository import get_topic, list_topic_group_states_for_group
from logica.modules.content.service import enable_scheduled_topics
from logica.modules.guides import repository as guides_repository
from logica.modules.guides.models import Guide, GuideOrigin, GuideStatus
from logica.modules.observability import repository as observability_repository
from logica.modules.reports.service import generate_group_report

logger = structlog.get_logger()

# Fase 13 (RE-08 free tier): cuánto se conservan los logs antes de podarse.
# Auditoría dura más porque es un rastro de cumplimiento, no solo debugging.
ERROR_LOG_RETENTION_DAYS = 30
AUDIT_LOG_RETENTION_DAYS = 180

# Fase 16: tope de guías autogeneradas por corrida. Cada guía son N llamadas al
# modelo, y el tier gratuito de Groq limita peticiones por minuto — sin tope, un
# docente habilitando 30 temas de golpe agota la cuota y todo cae al respaldo de
# Gemini. Lo que no entra se genera en la corrida siguiente.
GUIDES_PER_CRON_RUN = 10


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


async def generate_guide_job(ctx: dict[str, Any], guide_id: str) -> None:
    """Fase 16: redacta el contenido de una `Guide` que quedó en `generating`.
    Encolado por `POST /ai/guides/generate` — nunca corre en el request path: son
    N llamadas al modelo (una por sección) con 30 s de timeout cada una.

    `guide_id` viaja como str porque arq serializa los argumentos del job."""
    session_factory = get_session_factory()
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        async with session_factory() as db:
            await write_guide(db, redis, guide_id=uuid.UUID(guide_id))
            await db.commit()
    finally:
        await redis.aclose()
    logger.info("guide_job_finished", guide_id=guide_id)


async def generate_guides_for_enabled_topics_job(ctx: dict[str, Any]) -> int:
    """Fase 16: redacta un borrador de guía cuando un docente habilita un tema
    para un grupo cuya carpeta tiene la autogeneración activada.

    Nunca decide por el docente: solo actúa sobre carpetas donde él eligió una
    plantilla (`auto_generate_template_id`), respeta el interruptor por grupo del
    agente, y lo que produce es un borrador que él publica o descarta."""
    session_factory = get_session_factory()
    arq_pool: ArqRedis = ctx["redis"]
    created: list[str] = []
    pending = 0

    async with session_factory() as db:
        for folder in await guides_repository.list_auto_generate_folders(db):
            if not await is_agent_enabled(db, folder.group_id, AgentName.guide_writer):
                continue

            # `list_auto_generate_folders` ya filtró los NULL; el guard es para
            # que mypy no tenga que confiar en eso.
            if folder.auto_generate_template_id is None:
                continue
            template = await guides_repository.get_template(
                db, folder.institution_id, folder.auto_generate_template_id
            )
            if template is None:
                logger.warning(
                    "guide_autogen_template_missing",
                    folder_id=str(folder.id),
                    template_id=str(folder.auto_generate_template_id),
                )
                continue

            states = await list_topic_group_states_for_group(db, folder.group_id)
            for state in states:
                if state.state != TopicGroupStateValue.enabled:
                    continue
                if await guides_repository.guide_exists_for_group_topic(
                    db, folder.institution_id, folder.group_id, state.topic_id
                ):
                    continue
                if len(created) >= GUIDES_PER_CRON_RUN:
                    pending += 1
                    continue

                topic = await get_topic(db, state.topic_id)
                if topic is None:
                    continue

                # SAVEPOINT por ítem (regla de CLAUDE.md): este bucle SÍ ejecuta
                # INSERTs, y en Postgres una sentencia fallida aborta toda la
                # transacción abierta — sin esto, una guía que choque con una FK
                # se llevaría todas las creadas antes en esta corrida.
                try:
                    async with db.begin_nested():
                        guide = Guide(
                            institution_id=folder.institution_id,
                            folder_id=folder.id,
                            template_id=template.id,
                            topic_id=topic.id,
                            created_by_id=folder.created_by_id,
                            title=f"{template.name} — {topic.name}",
                            content_md="",
                            origin=GuideOrigin.ai,
                            status=GuideStatus.generating,
                        )
                        db.add(guide)
                        await db.flush()
                        created.append(str(guide.id))
                except SQLAlchemyError:
                    logger.exception(
                        "guide_autogen_row_failed",
                        folder_id=str(folder.id),
                        topic_id=str(state.topic_id),
                    )

        await db.commit()

    # Encolar después del commit: si se encolara antes, el worker podría tomar el
    # job y no encontrar la fila todavía.
    for guide_id in created:
        await arq_pool.enqueue_job("generate_guide_job", guide_id)

    if created or pending:
        # `pending` explícito: un tope silencioso se lee como "cubrió todo". Estas
        # guías se generan en la corrida siguiente.
        logger.info("guides_autogenerated", created=len(created), pending=pending)
    return len(created)


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
    generate_guide_job,
    generate_guides_for_enabled_topics_job,
    record_error_log_job,
    prune_observability_logs_job,
]

# Runs every 5 minutes — frequent enough that a scheduled topic doesn't lag
# far behind class time, cheap enough to not matter at this scale.
cron_jobs = [
    cron(enable_scheduled_topics_job, minute=set(range(0, 60, 5))),
    # Desfasado de `enable_scheduled_topics_job` (que corre cada 5 min): en los
    # minutos 7 y 37 la habilitación programada de :05 y :35 ya ocurrió, así que
    # el tema existe como `enabled` antes de que este job lo busque. Dos veces
    # por hora alcanza — la guía es material de preparación, no algo que el
    # estudiante esté esperando en ese minuto.
    cron(generate_guides_for_enabled_topics_job, minute={7, 37}),
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
