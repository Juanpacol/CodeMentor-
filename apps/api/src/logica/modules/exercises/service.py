import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from logica.modules.content.repository import get_topic
from logica.modules.exercises.models import (
    Exercise,
    ExerciseStatus,
    ExerciseType,
    ExerciseVersion,
    TopicExercise,
)
from logica.modules.exercises.repository import (
    create_exercise_version,
    get_exercise,
    get_exercise_version,
    get_topic_exercise_link,
    list_exercise_versions,
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

    changed = bool(title) or content is not None
    # Snapshot del contenido *anterior* solo si ya estaba publicado — un
    # draft en progreso no genera ruido de historial (ítem 5).
    if changed and exercise.status == ExerciseStatus.published:
        await create_exercise_version(db, exercise, created_by_id=user.id)

    if title:
        exercise.title = title
    if content is not None:
        exercise.content = content
    if status:
        exercise.status = status

    if changed:
        exercise.version += 1

    await db.flush()
    await db.refresh(exercise)
    return exercise


async def list_versions(
    db: AsyncSession, user: User, exercise_id: uuid.UUID
) -> list[ExerciseVersion]:
    _ensure_teacher(user)
    await _get_exercise_in_institution(db, user, exercise_id)
    return await list_exercise_versions(db, exercise_id)


async def restore_version(
    db: AsyncSession, user: User, exercise_id: uuid.UUID, version_id: uuid.UUID
) -> Exercise:
    """Restaurar también pasa por `update_exercise` (via el mismo camino de
    snapshot-antes-de-mutar), así queda en el historial y es a su vez
    reversible — no es un caso especial."""
    _ensure_teacher(user)
    exercise = await _get_exercise_in_institution(db, user, exercise_id)
    version = await get_exercise_version(db, version_id)
    if version is None or version.exercise_id != exercise.id:
        raise NotFoundError("Versión no encontrada")

    return await update_exercise(
        db, user, exercise_id, title=version.title, content=version.content, status=None
    )


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
