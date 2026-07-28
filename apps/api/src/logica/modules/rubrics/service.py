"""Servicio de rúbricas (Fase 17). El corte con `workers/rubric_runner.py` es el
mismo que ya usa el repo entre `modules/guides` y `ai/agents/guide_writer`: acá
viven la validación, la autorización y el encolado; allá la ejecución larga.

La corrida no puede vivir en el request path por mucho margen: son N temas × (M
secciones de guía + K ejercicios) llamadas al modelo, minutos de reloj.
"""

import uuid
from datetime import UTC, datetime

import structlog
from arq import ArqRedis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.cancellation import request_cancel
from logica.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from logica.modules.content.repository import get_language
from logica.modules.groups.service import get_group_with_access
from logica.modules.guides import repository as guides_repository
from logica.modules.guides import service as guides_service
from logica.modules.rubrics import repository
from logica.modules.rubrics.models import (
    RubricItem,
    RubricItemStatus,
    RubricRun,
    RubricRunStatus,
)
from logica.modules.rubrics.schemas import RubricItemSpec
from logica.modules.users.models import Role, User

logger = structlog.get_logger()

# Tope por corrida. Cada tema son ~4 llamadas de guía + ~3 de ejercicios: 15
# temas son ~105 llamadas y unos 160k tokens, contra el presupuesto diario de
# 200k del docente (`ai_daily_token_budget_per_teacher`). Cabe, pero justo — por
# eso el tope es parte del contrato de la API y no un detalle del worker.
MAX_ITEMS_PER_RUN = 15

_TERMINAL_STATUSES = (
    RubricRunStatus.done,
    RubricRunStatus.partial,
    RubricRunStatus.failed,
    RubricRunStatus.cancelled,
)


def _ensure_teacher(user: User) -> None:
    if user.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("Solo un docente o administrador puede gestionar rúbricas")


async def _ensure_folder(
    db: AsyncSession, user: User, group_id: uuid.UUID, folder_name: str
) -> uuid.UUID:
    """Crea la carpeta de guías o reusa la que ya tenga ese nombre.

    Reusar y no fallar con 409 es deliberado: volver a correr una rúbrica sobre
    la misma carpeta para agregar temas nuevos es el caso normal, y obligar al
    docente a inventar "Temario 10-A (2)" solo fragmentaría su dashboard.
    """
    existing = await guides_repository.list_folders_for_group(db, user.institution_id, group_id)
    for folder in existing:
        if folder.name == folder_name:
            return folder.id

    folder = await guides_service.create_folder(db, user, group_id, folder_name, None)
    return folder.id


async def request_rubric_run(
    db: AsyncSession,
    arq_pool: ArqRedis,
    user: User,
    *,
    group_id: uuid.UUID,
    language_id: uuid.UUID,
    template_id: uuid.UUID,
    folder_name: str,
    name: str,
    items: list[RubricItemSpec],
    exercise_types: list[str],
    acquire_content: bool,
) -> RubricRun:
    _ensure_teacher(user)
    _, is_teacher_view = await get_group_with_access(db, user, group_id)
    if not is_teacher_view:
        raise PermissionDeniedError("No administras este grupo")

    if len(items) > MAX_ITEMS_PER_RUN:
        raise ConflictError(
            f"Una rúbrica admite máximo {MAX_ITEMS_PER_RUN} temas por corrida; "
            "divide el temario en varias."
        )

    language = await get_language(db, language_id)
    if language is None or language.institution_id != user.institution_id:
        raise NotFoundError("Lenguaje no encontrado")

    template = await guides_repository.get_template(db, user.institution_id, template_id)
    if template is None:
        raise NotFoundError("Plantilla de guía no encontrada")

    folder_id = await _ensure_folder(db, user, group_id, folder_name)

    run = RubricRun(
        institution_id=user.institution_id,
        group_id=group_id,
        folder_id=folder_id,
        template_id=template.id,
        language_id=language.id,
        requested_by_id=user.id,
        name=name,
        exercise_types=exercise_types,
        acquire_content=acquire_content,
        status=RubricRunStatus.pending,
    )
    db.add(run)
    await db.flush()

    for index, spec in enumerate(items):
        db.add(
            RubricItem(
                run_id=run.id,
                topic_name=spec.topic_name,
                level=spec.level,
                order_index=index,
                extra_urls=list(spec.extra_urls) or None,
                status=RubricItemStatus.pending,
            )
        )
    await db.flush()
    await db.refresh(run)

    await arq_pool.enqueue_job("run_rubric_job", str(run.id))
    logger.info(
        "rubric_run_requested",
        run_id=str(run.id),
        group_id=str(group_id),
        items=len(items),
        acquire_content=acquire_content,
    )
    return run


async def get_run(db: AsyncSession, user: User, run_id: uuid.UUID) -> RubricRun:
    _ensure_teacher(user)
    run = await repository.get_run(db, user.institution_id, run_id)
    if run is None:
        raise NotFoundError("Corrida de rúbrica no encontrada")
    _, is_teacher_view = await get_group_with_access(db, user, run.group_id)
    if not is_teacher_view:
        raise PermissionDeniedError("No administras este grupo")
    return run


async def list_runs(db: AsyncSession, user: User, group_id: uuid.UUID) -> list[RubricRun]:
    _ensure_teacher(user)
    _, is_teacher_view = await get_group_with_access(db, user, group_id)
    if not is_teacher_view:
        raise PermissionDeniedError("No administras este grupo")
    return await repository.list_runs_for_group(db, user.institution_id, group_id)


async def list_items(db: AsyncSession, user: User, run_id: uuid.UUID) -> list[RubricItem]:
    run = await get_run(db, user, run_id)
    return await repository.list_items(db, run.id)


async def cancel_run(db: AsyncSession, redis: Redis, user: User, run_id: uuid.UUID) -> RubricRun:
    """Marca la corrida como cancelada y avisa al worker por Redis.

    Antes esto solo escribía el estado en la BD, y el orquestador lo consultaba
    únicamente **entre temas**: como un tema son ~7 llamadas al modelo, cancelar
    tardaba minutos en surtir efecto y parecía no funcionar. La señal de
    `core.cancellation` se consulta también entre las etapas de un tema y entre
    las secciones de una guía, así que ahora se detiene en segundos.

    Lo ya generado (temas, guías, ejercicios) se queda: son borradores que el
    docente puede archivar uno por uno, y borrarlos automáticamente destruiría
    trabajo que quizá sí quería.
    """
    run = await get_run(db, user, run_id)
    if run.status in _TERMINAL_STATUSES:
        raise ConflictError("La corrida ya terminó")

    # Primero la señal: si el commit de abajo fallara, un worker que ya la leyó
    # se detiene igual — el error opuesto (worker corriendo con la fila en
    # `cancelled`) le mentiría al docente.
    await request_cancel(redis, "rubric_run", run_id)

    run.status = RubricRunStatus.cancelled
    run.error_message = "Cancelada por el docente"
    run.completed_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(run)
    logger.info("rubric_run_cancelled", run_id=str(run_id))
    return run
