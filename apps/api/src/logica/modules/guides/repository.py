"""Acceso a datos de guías. Cada consulta filtra por `institution_id`
explícitamente (ADR-006: la multi-tenencia es 100% a nivel de aplicación, no hay
RLS de Postgres que sirva de red).

A diferencia de `content/repository.py`, acá incluso los `get_*` de una sola fila
reciben `institution_id` en vez de usar `db.get()` y dejar la validación al
llamador: son tres tablas nuevas y el filtro en el borde es más difícil de
olvidar que una comprobación repetida en cada servicio."""

import uuid
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.modules.content.models import TopicLevel
from logica.modules.guides.models import (
    Guide,
    GuideOrigin,
    GuidesFolder,
    GuideStatus,
    GuideTemplate,
)


async def create_folder(
    db: AsyncSession,
    *,
    institution_id: uuid.UUID,
    group_id: uuid.UUID,
    created_by_id: uuid.UUID,
    name: str,
    description: str | None,
) -> GuidesFolder:
    folder = GuidesFolder(
        institution_id=institution_id,
        group_id=group_id,
        created_by_id=created_by_id,
        name=name,
        description=description,
    )
    db.add(folder)
    return folder


async def get_folder(
    db: AsyncSession, institution_id: uuid.UUID, folder_id: uuid.UUID
) -> GuidesFolder | None:
    stmt = select(GuidesFolder).where(
        GuidesFolder.id == folder_id, GuidesFolder.institution_id == institution_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_folders_for_group(
    db: AsyncSession, institution_id: uuid.UUID, group_id: uuid.UUID
) -> list[GuidesFolder]:
    stmt = (
        select(GuidesFolder)
        .where(
            GuidesFolder.institution_id == institution_id,
            GuidesFolder.group_id == group_id,
        )
        .order_by(GuidesFolder.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_template(
    db: AsyncSession,
    *,
    institution_id: uuid.UUID,
    created_by_id: uuid.UUID,
    name: str,
    sections: list[dict[str, str]],
    tone: str,
    target_level: TopicLevel,
    version: int,
) -> GuideTemplate:
    template = GuideTemplate(
        institution_id=institution_id,
        created_by_id=created_by_id,
        name=name,
        sections=sections,
        tone=tone,
        target_level=target_level,
        version=version,
    )
    db.add(template)
    return template


async def get_template(
    db: AsyncSession, institution_id: uuid.UUID, template_id: uuid.UUID
) -> GuideTemplate | None:
    stmt = select(GuideTemplate).where(
        GuideTemplate.id == template_id, GuideTemplate.institution_id == institution_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def max_template_version(db: AsyncSession, institution_id: uuid.UUID, name: str) -> int:
    """0 si el nombre no existe todavía — así el llamador siempre suma 1 sin
    ramificar entre "crear" y "versionar"."""
    stmt = select(func.max(GuideTemplate.version)).where(
        GuideTemplate.institution_id == institution_id, GuideTemplate.name == name
    )
    result = await db.execute(stmt)
    return result.scalar_one() or 0


async def list_templates(
    db: AsyncSession, institution_id: uuid.UUID, *, only_active: bool = True
) -> list[GuideTemplate]:
    stmt = select(GuideTemplate).where(GuideTemplate.institution_id == institution_id)
    if only_active:
        stmt = stmt.where(GuideTemplate.is_active.is_(True))
    stmt = stmt.order_by(GuideTemplate.name, GuideTemplate.version.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_guide(
    db: AsyncSession, institution_id: uuid.UUID, guide_id: uuid.UUID
) -> Guide | None:
    stmt = select(Guide).where(Guide.id == guide_id, Guide.institution_id == institution_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def mark_guide_drafted(
    db: AsyncSession, guide: Guide, *, content_md: str, sources: list[str], prompt_version: int
) -> None:
    """`draft`, no `published`: §9.2 — la plataforma nunca publica contenido de
    IA sola, el docente lo hace explícitamente."""
    guide.content_md = content_md
    guide.sources = sources
    guide.prompt_version = prompt_version
    guide.status = GuideStatus.draft
    guide.error_message = None


async def mark_guide_failed(
    db: AsyncSession,
    guide: Guide,
    error_message: str,
    *,
    error_code: str | None = None,
    error_details: dict[str, Any] | None = None,
) -> None:
    guide.status = GuideStatus.failed
    guide.error_message = error_message
    # Ver `Guide.error_code`: el mensaje es para leer, esto es para diagnosticar.
    guide.error_code = error_code
    guide.error_details = error_details


async def mark_guide_cancelled(db: AsyncSession, guide: Guide) -> None:
    """Sin `error_message`: cancelar es una decisión, no un fallo."""
    guide.status = GuideStatus.cancelled


async def list_guides_for_folder(
    db: AsyncSession, institution_id: uuid.UUID, folder_id: uuid.UUID
) -> list[Guide]:
    stmt = (
        select(Guide)
        .where(Guide.institution_id == institution_id, Guide.folder_id == folder_id)
        .order_by(Guide.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _guides_of_group(institution_id: uuid.UUID, group_id: uuid.UUID) -> Select[tuple[Guide]]:
    """El grupo de una guía se deriva por su carpeta (`Guide` no duplica
    `group_id`), así que cualquier consulta "por grupo" pasa por este join."""
    return (
        select(Guide)
        .join(GuidesFolder, GuidesFolder.id == Guide.folder_id)
        .where(Guide.institution_id == institution_id, GuidesFolder.group_id == group_id)
    )


async def list_published_guides_for_group(
    db: AsyncSession, institution_id: uuid.UUID, group_id: uuid.UUID
) -> list[Guide]:
    """Vista del estudiante: solo lo publicado. Los borradores de IA y las guías
    archivadas no existen para él."""
    stmt = (
        _guides_of_group(institution_id, group_id)
        .where(Guide.status == GuideStatus.published)
        .order_by(Guide.published_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def guide_exists_for_group_topic(
    db: AsyncSession, institution_id: uuid.UUID, group_id: uuid.UUID, topic_id: uuid.UUID
) -> bool:
    """La verificación de "ya hay guía" del cron (`workers/settings.py`). Cuenta
    `failed` como inexistente: si el intento anterior murió, hay que reintentar.
    Cuenta `archived` como existente: el docente la descartó a propósito y
    regenerarla sola sería desobedecerlo."""
    stmt = (
        _guides_of_group(institution_id, group_id)
        .where(Guide.topic_id == topic_id, Guide.status != GuideStatus.failed)
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def list_auto_generate_folders(db: AsyncSession) -> list[GuidesFolder]:
    """Carpetas con la autogeneración activada, de TODAS las instituciones — la
    única query del módulo sin filtro por `institution_id`, porque el llamador es
    el cron del worker y no una petición de un usuario. La tenencia se preserva
    igual: cada carpeta lleva su `institution_id` y todo lo que el cron crea a
    partir de ella lo hereda."""
    stmt = select(GuidesFolder).where(GuidesFolder.auto_generate_template_id.is_not(None))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_ai_draft_guides(db: AsyncSession, institution_id: uuid.UUID) -> list[Guide]:
    """Bandeja de aprobaciones pendientes (`ai/agents/pending_approvals.py`)."""
    stmt = (
        select(Guide)
        .where(
            Guide.institution_id == institution_id,
            Guide.origin == GuideOrigin.ai,
            Guide.status == GuideStatus.draft,
        )
        .order_by(Guide.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
