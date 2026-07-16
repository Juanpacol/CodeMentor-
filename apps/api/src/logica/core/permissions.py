from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from fastapi import Depends

from logica.core.errors import PermissionDeniedError
from logica.core.security import get_current_user

if TYPE_CHECKING:
    from logica.modules.users.models import User


def require_role(*allowed_roles: str) -> Callable[..., Coroutine[Any, Any, "User"]]:
    """Dependency factory enforcing role-based access (§6 mínimo privilegio)."""

    async def dependency(user: "User" = Depends(get_current_user)) -> "User":
        if user.role.value not in allowed_roles:
            raise PermissionDeniedError("No tienes permisos para esta acción")
        return user

    return dependency


def ensure_same_institution(user: "User", institution_id: object) -> None:
    if user.institution_id != institution_id:
        raise PermissionDeniedError("Recurso de otra institución")
