import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.security import get_current_user
from logica.db import get_db
from logica.modules.progress import service
from logica.modules.progress.schemas import (
    LaggingStudentOut,
    StudentActivityOut,
    StudentProgressOut,
    TimelineEventOut,
    TodaySummaryOut,
)
from logica.modules.users.models import User

router = APIRouter(tags=["progress"])


@router.get("/progress/me", response_model=StudentProgressOut)
async def get_my_progress(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> StudentProgressOut:
    return await service.get_student_progress(db, user)


@router.get("/progress/me/activity", response_model=StudentActivityOut)
async def get_my_activity(
    days: int = Query(default=365, ge=1, le=730),
    tz: str = Query(default="UTC", max_length=64),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudentActivityOut:
    """Serie diaria de práctica, rachas y conexiones — el mapa de actividad.

    `tz` lo manda el navegador (`Intl.DateTimeFormat().resolvedOptions()`): sin
    él, agrupar en UTC partiría cada día en dos para cualquiera al oeste de
    Greenwich y las rachas se romperían a media tarde.
    """
    return await service.get_student_activity(db, user, days=days, tz_name=tz)


@router.get("/progress/me/today", response_model=TodaySummaryOut)
async def get_my_today_summary(
    tz: str = Query(default="UTC", max_length=64),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TodaySummaryOut:
    return await service.get_today_summary(db, user, tz_name=tz)


@router.get("/progress/me/timeline", response_model=list[TimelineEventOut])
async def get_my_timeline(
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TimelineEventOut]:
    return await service.get_student_timeline(db, user, limit=limit)


@router.get("/groups/{group_id}/progress/lagging", response_model=list[LaggingStudentOut])
async def get_lagging_students(
    group_id: uuid.UUID,
    topic_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LaggingStudentOut]:
    return await service.get_lagging_students(db, user, group_id, topic_id=topic_id)
