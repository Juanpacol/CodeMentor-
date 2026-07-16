import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from logica.modules.content.models import (
    Language,
    Topic,
    TopicGroupState,
    TopicGroupStateValue,
    TopicLevel,
)
from logica.modules.content.repository import (
    get_language_by_slug,
    get_topic,
    get_topic_group_state,
    list_due_scheduled_states,
    list_topic_group_states_for_group,
    list_topics,
)
from logica.modules.content.schemas import CurriculumTopicOut, TopicOut
from logica.modules.groups.models import Group
from logica.modules.groups.repository import get_group, get_membership
from logica.modules.users.models import Role, User


def _ensure_teacher(user: User) -> None:
    if user.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("Solo un docente o administrador puede gestionar contenidos")


async def create_language(
    db: AsyncSession, user: User, name: str, slug: str, syntax_mode: str
) -> Language:
    _ensure_teacher(user)
    existing = await get_language_by_slug(db, user.institution_id, slug)
    if existing is not None:
        raise ConflictError("Ya existe un lenguaje con ese identificador")

    language = Language(
        institution_id=user.institution_id, name=name, slug=slug, syntax_mode=syntax_mode
    )
    db.add(language)
    await db.flush()
    await db.refresh(language)
    return language


async def create_topic(
    db: AsyncSession,
    user: User,
    language_id: uuid.UUID,
    name: str,
    level: TopicLevel,
    order_index: int,
) -> Topic:
    _ensure_teacher(user)
    topic = Topic(
        institution_id=user.institution_id,
        language_id=language_id,
        created_by_id=user.id,
        name=name,
        level=level,
        order_index=order_index,
    )
    db.add(topic)
    await db.flush()
    await db.refresh(topic)
    return topic


async def _get_topic_in_institution(db: AsyncSession, user: User, topic_id: uuid.UUID) -> Topic:
    topic = await get_topic(db, topic_id)
    if topic is None or topic.institution_id != user.institution_id:
        raise NotFoundError("Tema no encontrado")
    return topic


async def update_topic(
    db: AsyncSession,
    user: User,
    topic_id: uuid.UUID,
    name: str | None,
    level: TopicLevel | None,
    order_index: int | None,
) -> Topic:
    _ensure_teacher(user)
    topic = await _get_topic_in_institution(db, user, topic_id)

    changed = False
    if name:
        topic.name = name
        changed = True
    if level:
        topic.level = level
        changed = True
    if order_index is not None:
        topic.order_index = order_index
        changed = True
    if changed:
        topic.version += 1

    await db.flush()
    await db.refresh(topic)
    return topic


async def _get_group_with_access(
    db: AsyncSession, user: User, group_id: uuid.UUID
) -> tuple[Group, bool]:
    """Returns (group, is_teacher_view). Raises if the user has no access at all."""
    group = await get_group(db, group_id)
    if group is None or group.institution_id != user.institution_id:
        raise NotFoundError("Grupo no encontrado")

    if user.role in (Role.teacher, Role.admin):
        if user.role != Role.admin and group.teacher_id != user.id:
            raise PermissionDeniedError("No administras este grupo")
        return group, True

    membership = await get_membership(db, group_id, user.id)
    if membership is None:
        raise PermissionDeniedError("No perteneces a este grupo")
    return group, False


async def enable_topic_for_group(
    db: AsyncSession, user: User, group_id: uuid.UUID, topic_id: uuid.UUID
) -> TopicGroupState:
    group, _ = await _get_group_with_access(db, user, group_id)
    await _get_topic_in_institution(db, user, topic_id)

    state = await get_topic_group_state(db, topic_id, group_id)
    if state is None:
        state = TopicGroupState(topic_id=topic_id, group_id=group_id)
        db.add(state)

    state.state = TopicGroupStateValue.enabled
    state.enabled_at = datetime.now(UTC)
    state.scheduled_enable_at = None
    await db.flush()
    await db.refresh(state)
    return state


async def disable_topic_for_group(
    db: AsyncSession, user: User, group_id: uuid.UUID, topic_id: uuid.UUID
) -> TopicGroupState:
    await _get_group_with_access(db, user, group_id)
    await _get_topic_in_institution(db, user, topic_id)

    state = await get_topic_group_state(db, topic_id, group_id)
    if state is None:
        state = TopicGroupState(topic_id=topic_id, group_id=group_id)
        db.add(state)

    state.state = TopicGroupStateValue.locked
    state.enabled_at = None
    state.scheduled_enable_at = None
    await db.flush()
    await db.refresh(state)
    return state


async def schedule_topic_for_group(
    db: AsyncSession, user: User, group_id: uuid.UUID, topic_id: uuid.UUID, enable_at: datetime
) -> TopicGroupState:
    await _get_group_with_access(db, user, group_id)
    await _get_topic_in_institution(db, user, topic_id)

    state = await get_topic_group_state(db, topic_id, group_id)
    if state is None:
        state = TopicGroupState(topic_id=topic_id, group_id=group_id)
        db.add(state)

    state.state = TopicGroupStateValue.locked
    state.scheduled_enable_at = enable_at
    await db.flush()
    await db.refresh(state)
    return state


async def get_curriculum_for_group(
    db: AsyncSession, user: User, group_id: uuid.UUID
) -> list[CurriculumTopicOut]:
    group, is_teacher_view = await _get_group_with_access(db, user, group_id)

    topics = await list_topics(db, user.institution_id)
    states_by_topic = {s.topic_id: s for s in await list_topic_group_states_for_group(db, group_id)}

    result: list[CurriculumTopicOut] = []
    for topic in topics:
        state = states_by_topic.get(topic.id)
        state_value = state.state if state else TopicGroupStateValue.locked

        if (
            not is_teacher_view
            and state_value != TopicGroupStateValue.enabled
            and group.hide_locked_topics
        ):
            continue

        result.append(
            CurriculumTopicOut(
                topic=TopicOut.model_validate(topic),
                state=state_value,
                enabled_at=state.enabled_at if state else None,
                scheduled_enable_at=state.scheduled_enable_at if state else None,
            )
        )
    return result


async def enable_scheduled_topics(db: AsyncSession) -> int:
    """Flips due `scheduled_enable_at` topics to enabled (RF-24). Runs as a
    periodic worker job (see logica.workers.settings), never on a request path."""
    due = await list_due_scheduled_states(db, datetime.now(UTC))
    for state in due:
        state.state = TopicGroupStateValue.enabled
        state.enabled_at = datetime.now(UTC)
        state.scheduled_enable_at = None
    await db.flush()
    return len(due)
