import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.permissions import require_role
from logica.core.security import get_current_user
from logica.db import get_db
from logica.modules.guides import service
from logica.modules.guides.models import Guide, GuidesFolder, GuideTemplate
from logica.modules.guides.schemas import (
    GuideOut,
    GuidesFolderCreateRequest,
    GuidesFolderOut,
    GuidesFolderUpdateRequest,
    GuideTemplateCreateRequest,
    GuideTemplateOut,
    GuideUpdateRequest,
)
from logica.modules.users.models import User

router = APIRouter(tags=["guides"])

RequireTeacher = require_role("teacher", "admin")


@router.post("/groups/{group_id}/guide-folders", response_model=GuidesFolderOut, status_code=201)
async def create_guide_folder(
    group_id: uuid.UUID,
    payload: GuidesFolderCreateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> GuidesFolder:
    folder = await service.create_folder(db, user, group_id, payload.name, payload.description)
    await db.commit()
    return folder


@router.get("/groups/{group_id}/guide-folders", response_model=list[GuidesFolderOut])
async def list_guide_folders(
    group_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> list[GuidesFolder]:
    return await service.list_folders(db, user, group_id)


@router.patch("/guide-folders/{folder_id}", response_model=GuidesFolderOut)
async def update_guide_folder(
    folder_id: uuid.UUID,
    payload: GuidesFolderUpdateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> GuidesFolder:
    """Activa/apaga la autogeneración de la carpeta (lo que el cron consulta)."""
    folder = await service.set_folder_auto_generate(
        db, user, folder_id, template_id=payload.auto_generate_template_id
    )
    await db.commit()
    return folder


@router.post("/guide-templates", response_model=GuideTemplateOut, status_code=201)
async def save_guide_template(
    payload: GuideTemplateCreateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> GuideTemplate:
    """POST y no PUT también para editar: guardar una plantilla con un nombre que
    ya existe crea la versión N+1 en vez de mutar la anterior (ver
    `service.save_template`), así que siempre es una creación."""
    template = await service.save_template(
        db,
        user,
        name=payload.name,
        sections=payload.sections,
        tone=payload.tone,
        target_level=payload.target_level,
    )
    await db.commit()
    return template


@router.get("/guide-templates", response_model=list[GuideTemplateOut])
async def list_guide_templates(
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> list[GuideTemplate]:
    return await service.list_templates(db, user)


@router.get("/guide-folders/{folder_id}/guides", response_model=list[GuideOut])
async def list_guides_in_folder(
    folder_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> list[Guide]:
    return await service.list_guides_in_folder(db, user, folder_id)


@router.get("/groups/{group_id}/guides", response_model=list[GuideOut])
async def list_published_guides(
    group_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Guide]:
    """Vista del estudiante: `get_current_user` y no `RequireTeacher`. Solo
    devuelve `published` — un borrador de IA no existe para el estudiante."""
    return await service.list_published_guides(db, user, group_id)


@router.get("/guides/{guide_id}", response_model=GuideOut)
async def get_guide(
    guide_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> Guide:
    """También es el poll target mientras `status=generating` — la fila es su
    propio job, no hay tabla de jobs aparte."""
    return await service.get_guide_for_teacher(db, user, guide_id)


@router.patch("/guides/{guide_id}", response_model=GuideOut)
async def update_guide(
    guide_id: uuid.UUID,
    payload: GuideUpdateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> Guide:
    guide = await service.update_guide(
        db, user, guide_id, title=payload.title, content_md=payload.content_md
    )
    await db.commit()
    return guide


@router.post("/guides/{guide_id}/publish", response_model=GuideOut)
async def publish_guide(
    guide_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> Guide:
    guide = await service.publish_guide(db, user, guide_id)
    await db.commit()
    return guide


@router.post("/guides/{guide_id}/archive", response_model=GuideOut)
async def archive_guide(
    guide_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> Guide:
    guide = await service.archive_guide(db, user, guide_id)
    await db.commit()
    return guide
