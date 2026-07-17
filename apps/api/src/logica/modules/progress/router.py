import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.permissions import require_role
from logica.core.security import get_current_user
from logica.db import get_db
from logica.modules.progress import service
from logica.modules.progress.schemas import (
    AcademicPeriodCreateRequest,
    AcademicPeriodOut,
    LaggingStudentOut,
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
