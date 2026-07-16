import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.permissions import require_role
from logica.core.security import get_current_user
from logica.db import get_db
from logica.modules.content import service
from logica.modules.content.models import Language, Topic
from logica.modules.content.repository import list_languages, list_topics
from logica.modules.content.schemas import (
    CurriculumTopicOut,
    LanguageCreateRequest,
    LanguageOut,
    ScheduleEnableRequest,
    TopicCreateRequest,
    TopicOut,
    TopicUpdateRequest,
)
from logica.modules.users.models import User

router = APIRouter(tags=["content"])

RequireTeacher = require_role("teacher", "admin")


@router.post("/languages", response_model=LanguageOut, status_code=201)
async def create_language(
    payload: LanguageCreateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> Language:
    language = await service.create_language(
        db, user, payload.name, payload.slug, payload.syntax_mode
    )
    await db.commit()
    return language


@router.get("/languages", response_model=list[LanguageOut])
async def list_active_languages(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Language]:
    return await list_languages(db, user.institution_id)


@router.post("/topics", response_model=TopicOut, status_code=201)
async def create_topic(
    payload: TopicCreateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> Topic:
    topic = await service.create_topic(
        db, user, payload.language_id, payload.name, payload.level, payload.order_index
    )
    await db.commit()
    return topic


@router.get("/topics", response_model=list[TopicOut])
async def list_all_topics(
    language_id: uuid.UUID | None = None,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> list[Topic]:
    return await list_topics(db, user.institution_id, language_id)


@router.patch("/topics/{topic_id}", response_model=TopicOut)
async def update_topic(
    topic_id: uuid.UUID,
    payload: TopicUpdateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> Topic:
    topic = await service.update_topic(
        db, user, topic_id, payload.name, payload.level, payload.order_index
    )
    await db.commit()
    return topic


@router.post("/groups/{group_id}/topics/{topic_id}/enable")
async def enable_topic(
    group_id: uuid.UUID,
    topic_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await service.enable_topic_for_group(db, user, group_id, topic_id)
    await db.commit()
    return {"detail": "Tema habilitado"}


@router.post("/groups/{group_id}/topics/{topic_id}/disable")
async def disable_topic(
    group_id: uuid.UUID,
    topic_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await service.disable_topic_for_group(db, user, group_id, topic_id)
    await db.commit()
    return {"detail": "Tema deshabilitado"}


@router.post("/groups/{group_id}/topics/{topic_id}/schedule")
async def schedule_topic(
    group_id: uuid.UUID,
    topic_id: uuid.UUID,
    payload: ScheduleEnableRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await service.schedule_topic_for_group(db, user, group_id, topic_id, payload.enable_at)
    await db.commit()
    return {"detail": "Habilitación programada"}


@router.get("/groups/{group_id}/curriculum", response_model=list[CurriculumTopicOut])
async def get_curriculum(
    group_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CurriculumTopicOut]:
    return await service.get_curriculum_for_group(db, user, group_id)
