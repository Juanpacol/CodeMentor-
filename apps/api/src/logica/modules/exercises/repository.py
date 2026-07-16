import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.modules.exercises.models import Exercise, TopicExercise


async def get_exercise(db: AsyncSession, exercise_id: uuid.UUID) -> Exercise | None:
    return await db.get(Exercise, exercise_id)


async def list_exercises(
    db: AsyncSession,
    institution_id: uuid.UUID,
    language_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
) -> list[Exercise]:
    stmt = select(Exercise).where(Exercise.institution_id == institution_id)
    if language_id is not None:
        stmt = stmt.where(Exercise.language_id == language_id)
    if topic_id is not None:
        stmt = stmt.join(TopicExercise, TopicExercise.exercise_id == Exercise.id).where(
            TopicExercise.topic_id == topic_id
        )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_topic_exercise_link(
    db: AsyncSession, topic_id: uuid.UUID, exercise_id: uuid.UUID
) -> TopicExercise | None:
    stmt = select(TopicExercise).where(
        TopicExercise.topic_id == topic_id, TopicExercise.exercise_id == exercise_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_topic_ids_for_exercise(db: AsyncSession, exercise_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = select(TopicExercise.topic_id).where(TopicExercise.exercise_id == exercise_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
