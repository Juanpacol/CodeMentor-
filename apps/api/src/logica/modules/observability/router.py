import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.permissions import require_role
from logica.db import get_db
from logica.modules.observability import service
from logica.modules.observability.schemas import (
    AiUsageOut,
    AiUsageRowOut,
    AuditLogOut,
    AuditLogPageOut,
    ErrorLogOut,
    ErrorLogPageOut,
    ErrorSummaryRowOut,
)
from logica.modules.users.models import User

router = APIRouter(prefix="/observability", tags=["observability"])

RequireTeacher = require_role("teacher", "admin")


@router.get("/errors", response_model=ErrorLogPageOut)
async def list_errors(
    date_from: date | None = None,
    date_to: date | None = None,
    status_code: int | None = None,
    path: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> ErrorLogPageOut:
    entries, page_info = await service.list_error_logs_for_user(
        db,
        user,
        date_from=date_from,
        date_to=date_to,
        status_code=status_code,
        path=path,
        page=page,
        page_size=page_size,
    )
    return ErrorLogPageOut(
        items=[ErrorLogOut.model_validate(e) for e in entries],
        total=page_info.total,
        page=page_info.page,
        page_size=page_info.page_size,
    )


@router.get("/errors/summary", response_model=list[ErrorSummaryRowOut])
async def summarize_errors(
    date_from: date | None = None,
    date_to: date | None = None,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> list[ErrorSummaryRowOut]:
    rows = await service.summarize_errors_for_user(db, user, date_from=date_from, date_to=date_to)
    return [ErrorSummaryRowOut.model_validate(row, from_attributes=True) for row in rows]


@router.get("/audit", response_model=AuditLogPageOut)
async def list_audit(
    action: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> AuditLogPageOut:
    entries, page_info = await service.list_audit_logs_for_user(
        db,
        user,
        action=action,
        actor_user_id=actor_user_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return AuditLogPageOut(
        items=[AuditLogOut.model_validate(e) for e in entries],
        total=page_info.total,
        page=page_info.page,
        page_size=page_info.page_size,
    )


@router.get("/ai/usage", response_model=AiUsageOut)
async def get_ai_usage(
    date_from: date | None = None,
    date_to: date | None = None,
    group_by: Literal["task", "model", "day"] = "task",
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> AiUsageOut:
    rows, budget = await service.summarize_ai_usage_for_user(
        db, user, date_from=date_from, date_to=date_to, group_by=group_by
    )
    return AiUsageOut(
        items=[
            AiUsageRowOut(
                key=row.key,
                interactions=row.interactions,
                prompt_tokens=row.prompt_tokens,
                completion_tokens=row.completion_tokens,
                cost_usd=float(row.cost_usd),
                cache_hits=row.cache_hits,
                blocked=row.blocked,
            )
            for row in rows
        ],
        budget=budget,
    )
