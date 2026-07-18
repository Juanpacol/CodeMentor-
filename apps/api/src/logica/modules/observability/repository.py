import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.audit import AuditLog
from logica.modules.observability.models import ErrorLog


@dataclass(frozen=True)
class Page:
    total: int
    page: int
    page_size: int


async def create_error_log(
    db: AsyncSession,
    *,
    institution_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    path: str,
    method: str,
    status_code: int,
    exception_type: str,
    message: str,
    stacktrace: str | None,
) -> ErrorLog:
    entry = ErrorLog(
        institution_id=institution_id,
        user_id=user_id,
        path=path,
        method=method,
        status_code=status_code,
        exception_type=exception_type,
        message=message,
        stacktrace=stacktrace,
    )
    db.add(entry)
    await db.flush()
    return entry


async def list_error_logs(
    db: AsyncSession,
    institution_id: uuid.UUID,
    *,
    date_from: date | None,
    date_to: date | None,
    status_code: int | None,
    path: str | None,
    page: int,
    page_size: int,
) -> tuple[list[ErrorLog], Page]:
    stmt = select(ErrorLog).where(ErrorLog.institution_id == institution_id)
    if date_from is not None:
        stmt = stmt.where(ErrorLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(ErrorLog.created_at <= date_to)
    if status_code is not None:
        stmt = stmt.where(ErrorLog.status_code == status_code)
    if path is not None:
        stmt = stmt.where(ErrorLog.path.ilike(f"%{path}%"))

    total = (
        await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()

    rows_stmt = (
        stmt.order_by(ErrorLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    rows = list((await db.execute(rows_stmt)).scalars().all())
    return rows, Page(total=total, page=page, page_size=page_size)


async def list_audit_logs(
    db: AsyncSession,
    institution_id: uuid.UUID,
    *,
    action: str | None,
    actor_user_id: uuid.UUID | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
) -> tuple[list[AuditLog], Page]:
    stmt = select(AuditLog).where(AuditLog.institution_id == institution_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if date_from is not None:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.created_at <= date_to)

    total = (
        await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()

    rows_stmt = (
        stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    rows = list((await db.execute(rows_stmt)).scalars().all())
    return rows, Page(total=total, page=page, page_size=page_size)


async def prune_old_logs(
    db: AsyncSession, *, error_log_retention_days: int, audit_log_retention_days: int
) -> tuple[int, int]:
    """Retención (RE-08 free tier): borra filas más viejas que el umbral para
    no crecer sin límite en el almacenamiento gratuito de Supabase."""
    error_cutoff = datetime.now(UTC) - timedelta(days=error_log_retention_days)
    audit_cutoff = datetime.now(UTC) - timedelta(days=audit_log_retention_days)

    error_result = await db.execute(delete(ErrorLog).where(ErrorLog.created_at < error_cutoff))
    audit_result = await db.execute(delete(AuditLog).where(AuditLog.created_at < audit_cutoff))
    # CursorResult.rowcount exists at runtime for a DELETE, but the generic
    # `Result[Any]` static type from AsyncSession.execute() doesn't declare it.
    return error_result.rowcount, audit_result.rowcount  # type: ignore[attr-defined]
