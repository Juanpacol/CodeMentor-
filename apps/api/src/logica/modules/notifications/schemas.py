import uuid
from datetime import datetime

from pydantic import BaseModel

from logica.modules.notifications.models import NotificationKind


class NotificationOut(BaseModel):
    id: uuid.UUID
    kind: NotificationKind
    title: str
    body: str
    related_id: uuid.UUID | None
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationPageOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int
