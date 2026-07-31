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
    ExerciseVersionOut,
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


@router.get("/{exercise_id}/versions", response_model=list[ExerciseVersionOut])
async def list_exercise_versions(
    exercise_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> list[ExerciseVersionOut]:
    versions = await service.list_versions(db, user, exercise_id)
    return [ExerciseVersionOut.model_validate(v) for v in versions]


@router.post("/{exercise_id}/versions/{version_id}/restore", response_model=ExerciseOut)
async def restore_exercise_version(
    exercise_id: uuid.UUID,
    version_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> Exercise:
    exercise = await service.restore_version(db, user, exercise_id, version_id)
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
