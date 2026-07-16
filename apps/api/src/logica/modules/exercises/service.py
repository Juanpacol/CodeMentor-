import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from logica.modules.content.repository import get_topic
from logica.modules.exercises.models import Exercise, ExerciseStatus, ExerciseType, TopicExercise
from logica.modules.exercises.repository import (
    get_exercise,
    get_topic_exercise_link,
)
from logica.modules.users.models import Role, User


def _ensure_teacher(user: User) -> None:
    if user.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("Solo un docente o administrador puede gestionar ejercicios")


async def create_exercise(
    db: AsyncSession,
    user: User,
    language_id: uuid.UUID,
    title: str,
    exercise_type: ExerciseType,
    content: dict[str, Any],
    status: ExerciseStatus,
) -> Exercise:
    _ensure_teacher(user)
    exercise = Exercise(
        institution_id=user.institution_id,
        language_id=language_id,
        created_by_id=user.id,
        title=title,
        type=exercise_type,
        content=content,
        status=status,
    )
    db.add(exercise)
    await db.flush()
    await db.refresh(exercise)
    return exercise


async def _get_exercise_in_institution(
    db: AsyncSession, user: User, exercise_id: uuid.UUID
) -> Exercise:
    exercise = await get_exercise(db, exercise_id)
    if exercise is None or exercise.institution_id != user.institution_id:
        raise NotFoundError("Ejercicio no encontrado")
    return exercise


async def update_exercise(
    db: AsyncSession,
    user: User,
    exercise_id: uuid.UUID,
    title: str | None,
    content: dict[str, Any] | None,
    status: ExerciseStatus | None,
) -> Exercise:
    _ensure_teacher(user)
    exercise = await _get_exercise_in_institution(db, user, exercise_id)

    changed = False
    if title:
        exercise.title = title
        changed = True
    if content is not None:
        exercise.content = content
        changed = True
    if status:
        exercise.status = status

    if changed:
        exercise.version += 1

    await db.flush()
    await db.refresh(exercise)
    return exercise


async def attach_exercise_to_topic(
    db: AsyncSession, user: User, topic_id: uuid.UUID, exercise_id: uuid.UUID
) -> TopicExercise:
    _ensure_teacher(user)
    topic = await get_topic(db, topic_id)
    if topic is None or topic.institution_id != user.institution_id:
        raise NotFoundError("Tema no encontrado")
    exercise = await _get_exercise_in_institution(db, user, exercise_id)

    existing = await get_topic_exercise_link(db, topic.id, exercise.id)
    if existing is not None:
        raise ConflictError("El ejercicio ya está asociado a este tema")

    link = TopicExercise(topic_id=topic.id, exercise_id=exercise.id)
    db.add(link)
    await db.flush()
    return link
