import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.permissions import require_role
from logica.db import get_db
from logica.modules.exercises import service
from logica.modules.exercises.models import Exercise
from logica.modules.exercises.repository import list_exercises
from logica.modules.exercises.schemas import (
    ExerciseCreateRequest,
    ExerciseOut,
    ExerciseUpdateRequest,
)
from logica.modules.users.models import User

router = APIRouter(prefix="/exercises", tags=["exercises"])

RequireTeacher = require_role("teacher", "admin")


@router.post("", response_model=ExerciseOut, status_code=201)
async def create_exercise(
    payload: ExerciseCreateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> Exercise:
    exercise = await service.create_exercise(
        db,
        user,
        payload.language_id,
        payload.title,
        payload.type,
        payload.content,
        payload.status,
    )
    await db.commit()
    return exercise


@router.get("", response_model=list[ExerciseOut])
async def list_bank(
    language_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> list[Exercise]:
    return await list_exercises(db, user.institution_id, language_id, topic_id)


@router.patch("/{exercise_id}", response_model=ExerciseOut)
async def update_exercise(
    exercise_id: uuid.UUID,
    payload: ExerciseUpdateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> Exercise:
    exercise = await service.update_exercise(
        db, user, exercise_id, payload.title, payload.content, payload.status
    )
    await db.commit()
    return exercise


@router.post("/{exercise_id}/topics/{topic_id}", status_code=201)
async def attach_to_topic(
    exercise_id: uuid.UUID,
    topic_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await service.attach_exercise_to_topic(db, user, topic_id, exercise_id)
    await db.commit()
    return {"detail": "Ejercicio asociado al tema"}
