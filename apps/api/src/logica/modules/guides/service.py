"""Servicio de guías (Fase 16). El corte con `ai/agents/guide_writer.py` es el
mismo que ya usa el repo entre `modules/exercises` y el generador de ejercicios:
acá vive el CRUD y las reglas de negocio, allá la llamada al modelo.

La generación NO corre en el request path: son N llamadas al modelo (una por
sección) con timeout de 30 s cada una, y se pasaría del límite de la petición
HTTP en producción. `request_guide_generation` crea la fila en `generating` y
encola un job de arq, igual que `reports/service.py::request_group_report` — la
diferencia es que acá el poll target es la propia `Guide`, no una tabla de jobs
aparte, porque el producto de la generación ES esa fila."""

import uuid
from datetime import UTC, datetime

import structlog
from arq import ArqRedis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.cancellation import request_cancel
from logica.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationDomainError,
)
from logica.modules.content.models import TopicLevel
from logica.modules.content.repository import get_topic
from logica.modules.groups.service import get_group_with_access
from logica.modules.guides import repository
from logica.modules.guides.models import (
    Guide,
    GuideOrigin,
    GuidesFolder,
    GuideStatus,
    GuideTemplate,
)
from logica.modules.guides.schemas import GuideSectionSpec
from logica.modules.users.models import Role, User

logger = structlog.get_logger()


def _ensure_teacher(user: User) -> None:
    if user.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("Solo un docente o administrador puede gestionar guías")


async def _teacher_folder(db: AsyncSession, user: User, folder_id: uuid.UUID) -> GuidesFolder:
    """Toda autorización sobre una guía pasa por su carpeta: la carpeta es la que
    conoce el grupo, y `get_group_with_access` es la que sabe si este docente lo
    administra."""
    folder = await repository.get_folder(db, user.institution_id, folder_id)
    if folder is None:
        raise NotFoundError("Carpeta de guías no encontrada")
    _, is_teacher_view = await get_group_with_access(db, user, folder.group_id)
    if not is_teacher_view:
        raise PermissionDeniedError("Solo un docente o administrador puede gestionar guías")
    return folder


async def create_folder(
    db: AsyncSession, user: User, group_id: uuid.UUID, name: str, description: str | None
) -> GuidesFolder:
    _ensure_teacher(user)
    _, is_teacher_view = await get_group_with_access(db, user, group_id)
    if not is_teacher_view:
        raise PermissionDeniedError("No administras este grupo")

    existing = await repository.list_folders_for_group(db, user.institution_id, group_id)
    if any(f.name == name for f in existing):
        raise ConflictError("Ya existe una carpeta con ese nombre en este grupo")

    folder = await repository.create_folder(
        db,
        institution_id=user.institution_id,
        group_id=group_id,
        created_by_id=user.id,
        name=name,
        description=description,
    )
    await db.flush()
    await db.refresh(folder)
    return folder


async def list_folders(db: AsyncSession, user: User, group_id: uuid.UUID) -> list[GuidesFolder]:
    _, is_teacher_view = await get_group_with_access(db, user, group_id)
    if not is_teacher_view:
        raise PermissionDeniedError("Solo un docente o administrador puede ver las carpetas")
    return await repository.list_folders_for_group(db, user.institution_id, group_id)


async def set_folder_auto_generate(
    db: AsyncSession, user: User, folder_id: uuid.UUID, *, template_id: uuid.UUID | None
) -> GuidesFolder:
    """Activa o apaga la autogeneración de una carpeta (`None` la apaga). Es el
    interruptor que el cron consulta: sin plantilla elegida acá, no genera nada
    para esta carpeta."""
    folder = await _teacher_folder(db, user, folder_id)

    if template_id is None:
        folder.auto_generate_template_id = None
    else:
        template = await repository.get_template(db, user.institution_id, template_id)
        if template is None:
            raise NotFoundError("Plantilla de guía no encontrada")
        folder.auto_generate_template_id = template.id

    await db.flush()
    await db.refresh(folder)
    logger.info(
        "guide_folder_auto_generate_set",
        folder_id=str(folder_id),
        template_id=str(folder.auto_generate_template_id),
    )
    return folder


async def save_template(
    db: AsyncSession,
    user: User,
    *,
    name: str,
    sections: list[GuideSectionSpec],
    tone: str,
    target_level: TopicLevel,
) -> GuideTemplate:
    """Crear y "editar" son la misma operación: una plantilla publicada nunca se
    muta, se agrega la versión N+1 (misma convención que los prompts `.vN.j2`).
    Así una guía vieja sigue explicándose contra la plantilla exacta que la
    produjo, en vez de apuntar a un texto que ya cambió."""
    _ensure_teacher(user)
    next_version = await repository.max_template_version(db, user.institution_id, name) + 1
    template = await repository.create_template(
        db,
        institution_id=user.institution_id,
        created_by_id=user.id,
        name=name,
        sections=[s.model_dump() for s in sections],
        tone=tone,
        target_level=target_level,
        version=next_version,
    )
    await db.flush()
    await db.refresh(template)
    logger.info(
        "guide_template_saved",
        template_id=str(template.id),
        name=name,
        version=next_version,
        sections=len(sections),
    )
    return template


async def list_templates(db: AsyncSession, user: User) -> list[GuideTemplate]:
    _ensure_teacher(user)
    return await repository.list_templates(db, user.institution_id)


async def request_guide_generation(
    db: AsyncSession,
    arq_pool: ArqRedis,
    user: User,
    *,
    folder_id: uuid.UUID,
    template_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> Guide:
    _ensure_teacher(user)
    folder = await _teacher_folder(db, user, folder_id)

    template = await repository.get_template(db, user.institution_id, template_id)
    if template is None:
        raise NotFoundError("Plantilla de guía no encontrada")

    topic = await get_topic(db, topic_id)
    if topic is None or topic.institution_id != user.institution_id:
        raise NotFoundError("Tema no encontrado")

    guide = Guide(
        institution_id=user.institution_id,
        folder_id=folder.id,
        template_id=template.id,
        topic_id=topic.id,
        created_by_id=user.id,
        title=f"{template.name} — {topic.name}",
        content_md="",
        origin=GuideOrigin.ai,
        status=GuideStatus.generating,
    )
    db.add(guide)
    await db.flush()
    await db.refresh(guide)
    await arq_pool.enqueue_job("generate_guide_job", str(guide.id))
    logger.info(
        "guide_generation_requested",
        guide_id=str(guide.id),
        group_id=str(folder.group_id),
        topic_id=str(topic_id),
    )
    return guide


async def get_guide_for_teacher(db: AsyncSession, user: User, guide_id: uuid.UUID) -> Guide:
    guide = await repository.get_guide(db, user.institution_id, guide_id)
    if guide is None:
        raise NotFoundError("Guía no encontrada")
    await _teacher_folder(db, user, guide.folder_id)
    return guide


async def list_guides_in_folder(db: AsyncSession, user: User, folder_id: uuid.UUID) -> list[Guide]:
    await _teacher_folder(db, user, folder_id)
    return await repository.list_guides_for_folder(db, user.institution_id, folder_id)


async def list_published_guides(db: AsyncSession, user: User, group_id: uuid.UUID) -> list[Guide]:
    """Vista del estudiante. `get_group_with_access` ya rechaza a quien no
    pertenece al grupo; el filtro a `published` vive en el repositorio para que no
    haya forma de pedir esta lista y recibir un borrador."""
    await get_group_with_access(db, user, group_id)
    return await repository.list_published_guides_for_group(db, user.institution_id, group_id)


async def update_guide(
    db: AsyncSession,
    user: User,
    guide_id: uuid.UUID,
    *,
    title: str | None,
    content_md: str | None,
) -> Guide:
    guide = await get_guide_for_teacher(db, user, guide_id)
    if guide.status == GuideStatus.generating:
        raise ConflictError("La guía todavía se está generando; espera a que termine")

    if title is not None:
        guide.title = title
    if content_md is not None:
        guide.content_md = content_md
    await db.flush()
    await db.refresh(guide)
    return guide


async def publish_guide(db: AsyncSession, user: User, guide_id: uuid.UUID) -> Guide:
    """§9.2: el único camino de `draft` a `published` es un docente pidiéndolo
    explícitamente — ni el agente ni el cron pueden llegar acá."""
    guide = await get_guide_for_teacher(db, user, guide_id)
    if guide.status == GuideStatus.published:
        raise ConflictError("La guía ya está publicada")
    if guide.status != GuideStatus.draft:
        raise ConflictError("Solo se puede publicar una guía en estado borrador")
    if not guide.content_md.strip():
        raise ValidationDomainError("No se puede publicar una guía sin contenido")

    guide.status = GuideStatus.published
    guide.published_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(guide)
    logger.info("guide_published", guide_id=str(guide_id))
    return guide


async def cancel_guide(db: AsyncSession, redis: Redis, user: User, guide_id: uuid.UUID) -> Guide:
    """Detiene una guía que se está generando.

    Antes no existía: una guía cuya generación se atascaba se quedaba en
    `generating` para siempre, sin forma de archivarla (`archive_guide` lo
    prohíbe justamente en ese estado) ni de reintentarla.

    El estado se escribe acá y no se espera al worker: si el job murió sin
    avisar, esperar su confirmación dejaría la fila colgada igual que antes.
    Cuando el worker sí está vivo, la señal de Redis lo hace salir entre
    secciones y él conserva lo ya redactado.
    """
    guide = await get_guide_for_teacher(db, user, guide_id)
    if guide.status != GuideStatus.generating:
        raise ConflictError("Solo se puede cancelar una guía que se está generando")

    await request_cancel(redis, "guide", guide_id)
    guide.status = GuideStatus.cancelled
    await db.flush()
    await db.refresh(guide)
    logger.info("guide_cancelled", guide_id=str(guide_id))
    return guide


async def archive_guide(db: AsyncSession, user: User, guide_id: uuid.UUID) -> Guide:
    guide = await get_guide_for_teacher(db, user, guide_id)
    if guide.status == GuideStatus.generating:
        raise ConflictError("La guía todavía se está generando; espera a que termine")

    guide.status = GuideStatus.archived
    guide.published_at = None
    await db.flush()
    await db.refresh(guide)
    return guide


async def delete_guide(db: AsyncSession, user: User, guide_id: uuid.UUID) -> None:
    """Borrado en duro, solo para guías que ningún estudiante pudo haber visto
    (`draft`/`failed`/`cancelled`; `generating` también se descarta, no tiene
    contenido todavía). Una guía `published` o `archived` se archiva, nunca se
    borra — mismo criterio que `§9.2` para cualquier contenido que ya circuló:
    desaparecer en silencio sería peor que dejarla marcada como archivada."""
    guide = await get_guide_for_teacher(db, user, guide_id)
    if guide.status in (GuideStatus.published, GuideStatus.archived):
        raise ConflictError(
            "No se puede borrar una guía publicada o archivada",
            hint="Si ya no la quieres visible, dejarla archivada tiene el mismo efecto.",
        )

    await db.delete(guide)
    await db.flush()
    logger.info("guide_deleted", guide_id=str(guide_id))
