import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.modules.notifications.models import Notification, NotificationKind


async def find_recent(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    kind: NotificationKind,
    related_id: uuid.UUID | None,
    since: datetime,
) -> Notification | None:
    """Para el dedupe: si ya existe una notificación de este tipo+objetivo
    creada después de `since`, no se genera otra — evita repetir "tu tarea
    vence mañana" en cada carga de la página."""
    related_id_filter = (
        Notification.related_id.is_(None)
        if related_id is None
        else Notification.related_id == related_id
    )
    stmt = select(Notification).where(
        Notification.user_id == user_id,
        Notification.kind == kind,
        related_id_filter,
        Notification.created_at >= since,
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def create(
    db: AsyncSession,
    *,
    institution_id: uuid.UUID,
    user_id: uuid.UUID,
    kind: NotificationKind,
    title: str,
    body: str,
    related_id: uuid.UUID | None,
) -> Notification:
    notification = Notification(
        institution_id=institution_id,
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        related_id=related_id,
    )
    db.add(notification)
    await db.flush()
    return notification


async def list_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_unread(db: AsyncSession, user_id: uuid.UUID) -> int:
    stmt = select(func.count(Notification.id)).where(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    )
    result = await db.execute(stmt)
    return int(result.scalar_one())


async def get_for_user(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification | None:
    stmt = select(Notification).where(
        Notification.id == notification_id, Notification.user_id == user_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID, *, now: datetime) -> None:
    stmt = select(Notification).where(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    )
    result = await db.execute(stmt)
    for notification in result.scalars().all():
        notification.read_at = now
