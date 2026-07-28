import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.security import get_current_user
from logica.db import get_db
from logica.modules.notifications import service
from logica.modules.notifications.schemas import NotificationOut, NotificationPageOut
from logica.modules.users.models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPageOut)
async def list_notifications(
    tz: str = Query(default="UTC", max_length=64),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPageOut:
    notifications, unread_count = await service.list_notifications_for_student(db, user, tz_name=tz)
    await db.commit()
    return NotificationPageOut(
        items=[NotificationOut.model_validate(n) for n in notifications],
        unread_count=unread_count,
    )


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationOut:
    notification = await service.mark_read(db, user, notification_id)
    await db.commit()
    return NotificationOut.model_validate(notification)


@router.post("/read-all", status_code=204)
async def mark_all_notifications_read(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await service.mark_all_read(db, user)
    await db.commit()
