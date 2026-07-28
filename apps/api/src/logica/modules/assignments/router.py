import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.permissions import require_role
from logica.core.security import get_current_user
from logica.db import get_db
from logica.modules.assignments import service
from logica.modules.assignments.models import Assignment
from logica.modules.assignments.schemas import (
    AssignmentCreateRequest,
    AssignmentOut,
    AssignmentUpdateRequest,
    StudentAssignmentOut,
)
from logica.modules.users.models import User

router = APIRouter(tags=["assignments"])

RequireTeacher = require_role("teacher", "admin")


@router.post("/groups/{group_id}/assignments", response_model=AssignmentOut, status_code=201)
async def create_assignment(
    group_id: uuid.UUID,
    payload: AssignmentCreateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> Assignment:
    assignment = await service.create_assignment(
        db,
        user,
        group_id=group_id,
        title=payload.title,
        topic_id=payload.topic_id,
        exercise_id=payload.exercise_id,
        due_at=payload.due_at,
    )
    await db.commit()
    return assignment


@router.get("/groups/{group_id}/assignments", response_model=list[AssignmentOut])
async def list_assignments(
    group_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> list[Assignment]:
    return await service.list_assignments(db, user, group_id)


@router.patch("/assignments/{assignment_id}", response_model=AssignmentOut)
async def update_assignment(
    assignment_id: uuid.UUID,
    payload: AssignmentUpdateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> Assignment:
    assignment = await service.update_assignment(
        db, user, assignment_id, title=payload.title, due_at=payload.due_at
    )
    await db.commit()
    return assignment


@router.delete("/assignments/{assignment_id}", status_code=204)
async def delete_assignment(
    assignment_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_assignment(db, user, assignment_id)
    await db.commit()


@router.get("/assignments/me", response_model=list[StudentAssignmentOut])
async def list_my_assignments(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StudentAssignmentOut]:
    """Lo que le falta al estudiante, de todos sus grupos, ordenado por fecha.

    Sin `require_role("student")`: un docente que abre su propio panel no debe
    recibir un 403 — simplemente no tiene matrículas y ve una lista vacía.
    """
    return await service.list_my_assignments(db, user)
