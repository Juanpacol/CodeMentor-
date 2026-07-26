import uuid
from datetime import datetime
from typing import Literal

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


# --- Ítem 14: dashboard de costo de IA ---


class AiUsageRowOut(BaseModel):
    key: str
    interactions: int
    prompt_tokens: int
    completion_tokens: int
    # float, no Decimal: Pydantic v2 serializa Decimal como string por
    # defecto — se fija a float en la salida, Numeric se queda en la BD.
    cost_usd: float
    cache_hits: int
    blocked: int


class AiBudgetStatusOut(BaseModel):
    month_to_date_usd: float
    monthly_limit_usd: float
    pct_used: float
    level: Literal["ok", "warning", "critical"]


class AiUsageOut(BaseModel):
    items: list[AiUsageRowOut]
    budget: AiBudgetStatusOut
