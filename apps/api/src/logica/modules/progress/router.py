import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.permissions import require_role
from logica.core.security import get_current_user
from logica.db import get_db
from logica.modules.progress import service
from logica.modules.progress.schemas import (
    AcademicPeriodCreateRequest,
    AcademicPeriodOut,
    LaggingStudentOut,
    StudentActivityOut,
    StudentProgressOut,
)
from logica.modules.users.models import User

router = APIRouter(tags=["progress"])

RequireTeacher = require_role("teacher", "admin")


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


@router.get("/groups/{group_id}/progress/lagging", response_model=list[LaggingStudentOut])
async def get_lagging_students(
    group_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LaggingStudentOut]:
    return await service.get_lagging_students(db, user, group_id)


@router.post("/academic-periods", response_model=AcademicPeriodOut, status_code=201)
async def create_academic_period(
    payload: AcademicPeriodCreateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> AcademicPeriodOut:
    period = await service.create_academic_period(
        db, user, payload.name, payload.start_date, payload.end_date
    )
    await db.commit()
    return AcademicPeriodOut.model_validate(period)


@router.get("/academic-periods", response_model=list[AcademicPeriodOut])
async def list_academic_periods(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[AcademicPeriodOut]:
    periods = await service.list_academic_periods(db, user)
    return [AcademicPeriodOut.model_validate(p) for p in periods]
