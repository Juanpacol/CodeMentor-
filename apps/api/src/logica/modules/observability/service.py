import uuid
from datetime import date

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.audit import AuditLog
from logica.core.errors import PermissionDeniedError
from logica.core.security import decode_token
from logica.modules.observability import repository
from logica.modules.observability.models import ErrorLog
from logica.modules.observability.repository import Page
from logica.modules.users.models import Role, User


def best_effort_actor(request: Request) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Intenta identificar quién hizo la petición que rompió, sin arriesgar
    romper también el manejador de errores: cualquier fallo al decodificar
    el token (vencido, ausente, inválido) resulta en (None, None) en vez de
    propagar — el error original sigue siendo lo importante."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None, None
    try:
        payload = decode_token(auth.split(" ", 1)[1], expected_type="access")
    except Exception:
        return None, None
    return payload.sub, payload.institution_id


def _ensure_teacher(user: User) -> None:
    if user.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("Solo un docente o administrador puede ver esta sección")


def redact_stacktrace_for_role(entry: ErrorLog, user: User) -> ErrorLog:
    """El stacktrace completo puede contener fragmentos de SQL o datos de
    otros usuarios — solo un admin lo ve; a un docente se le oculta."""
    if user.role != Role.admin:
        entry.stacktrace = None
    return entry


async def list_error_logs_for_user(
    db: AsyncSession,
    user: User,
    *,
    date_from: date | None,
    date_to: date | None,
    status_code: int | None,
    path: str | None,
    page: int,
    page_size: int,
) -> tuple[list[ErrorLog], Page]:
    _ensure_teacher(user)
    entries, page_info = await repository.list_error_logs(
        db,
        user.institution_id,
        date_from=date_from,
        date_to=date_to,
        status_code=status_code,
        path=path,
        page=page,
        page_size=page_size,
    )
    return [redact_stacktrace_for_role(e, user) for e in entries], page_info


async def list_audit_logs_for_user(
    db: AsyncSession,
    user: User,
    *,
    action: str | None,
    actor_user_id: uuid.UUID | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
) -> tuple[list[AuditLog], Page]:
    _ensure_teacher(user)
    return await repository.list_audit_logs(
        db,
        user.institution_id,
        action=action,
        actor_user_id=actor_user_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
