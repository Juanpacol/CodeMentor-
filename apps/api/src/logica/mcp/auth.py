"""Authentication for the MCP server (§9.2 "servidor MCP... con
autenticación por token de docente"): every tool/resource takes the same
JWT access token a teacher already gets from `/auth/login`, so there is no
second credential system to manage — just the existing one, reused."""

from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.errors import PermissionDeniedError
from logica.core.security import decode_token
from logica.modules.users.models import Role, User
from logica.modules.users.repository import get_user_by_id


async def resolve_teacher(db: AsyncSession, access_token: str) -> User:
    """Decodes the token, loads the user, and requires a teacher/admin role
    — the MCP server is a docente-facing tool by design (§9.2), never a
    student-facing surface."""
    payload = decode_token(access_token, expected_type="access")
    user = await get_user_by_id(db, payload.sub)
    if user is None or not user.is_active:
        raise PermissionDeniedError("Token inválido o usuario inactivo")
    if user.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("El servidor MCP solo está disponible para docentes")
    return user
