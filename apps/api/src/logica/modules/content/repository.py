import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.modules.content.models import Language, Topic, TopicGroupState, TopicGroupStateValue


async def get_language(db: AsyncSession, language_id: uuid.UUID) -> Language | None:
    return await db.get(Language, language_id)


async def get_language_by_slug(
    db: AsyncSession, institution_id: uuid.UUID, slug: str
) -> Language | None:
    stmt = select(Language).where(Language.institution_id == institution_id, Language.slug == slug)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_languages(db: AsyncSession, institution_id: uuid.UUID) -> list[Language]:
    stmt = (
        select(Language)
        .where(Language.institution_id == institution_id, Language.is_active.is_(True))
        .order_by(Language.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_topic(db: AsyncSession, topic_id: uuid.UUID) -> Topic | None:
    return await db.get(Topic, topic_id)


async def list_topics(
    db: AsyncSession, institution_id: uuid.UUID, language_id: uuid.UUID | None = None
) -> list[Topic]:
    stmt = select(Topic).where(Topic.institution_id == institution_id)
    if language_id is not None:
        stmt = stmt.where(Topic.language_id == language_id)
    stmt = stmt.order_by(Topic.order_index)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_topic_group_state(
    db: AsyncSession, topic_id: uuid.UUID, group_id: uuid.UUID
) -> TopicGroupState | None:
    stmt = select(TopicGroupState).where(
        TopicGroupState.topic_id == topic_id, TopicGroupState.group_id == group_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_topic_group_states_for_group(
    db: AsyncSession, group_id: uuid.UUID
) -> list[TopicGroupState]:
    stmt = select(TopicGroupState).where(TopicGroupState.group_id == group_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_due_scheduled_states(db: AsyncSession, now: datetime) -> list[TopicGroupState]:
    stmt = select(TopicGroupState).where(
        TopicGroupState.scheduled_enable_at.is_not(None),
        TopicGroupState.scheduled_enable_at <= now,
        TopicGroupState.state == TopicGroupStateValue.locked,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
