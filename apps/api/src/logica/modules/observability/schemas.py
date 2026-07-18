import uuid
from datetime import datetime

from pydantic import BaseModel


class ErrorLogOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID | None
    user_id: uuid.UUID | None
    path: str
    method: str
    status_code: int
    exception_type: str
    message: str
    stacktrace: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str
    details: dict[str, object]
    created_at: datetime

    model_config = {"from_attributes": True}


class ErrorLogPageOut(BaseModel):
    items: list[ErrorLogOut]
    total: int
    page: int
    page_size: int


class AuditLogPageOut(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int
