from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from fastapi import Depends

from logica.core.errors import PermissionDeniedError
from logica.core.security import get_current_user
from logica.modules.users.models import Role

if TYPE_CHECKING:
    from logica.modules.users.models import User


def require_role(*allowed_roles: str) -> Callable[..., Coroutine[Any, Any, "User"]]:
    """Dependency factory enforcing role-based access (§6 mínimo privilegio)."""

    async def dependency(user: "User" = Depends(get_current_user)) -> "User":
        if user.role.value not in allowed_roles:
            raise PermissionDeniedError("No tienes permisos para esta acción")
        return user

    return dependency


# Capabilities por rol. `admin` conserva acceso total ("*") — para distinguir
# acciones dentro de un mismo rol (p.ej. student/teacher) sin agregar una tabla
# de permisos nueva.
PERMISSIONS: dict[Role, set[str]] = {
    Role.student: {
        "progress:view_own",
        "sandbox:use",
        "evaluations:view_own",
        "assignments:view_own",
    },
    Role.teacher: {
        "rubrics:manage",
        "guides:manage",
        "assignments:manage",
        "reports:view",
        "groups:manage",
        "progress:view_own",
        "evaluations:view_own",
    },
    Role.admin: {"*"},
}


def require_permission(*perms: str) -> Callable[..., Coroutine[Any, Any, "User"]]:
    """Dependency factory enforcing capability-based access.

    Complementa a `require_role`: mientras ese chequea el rol plano, este
    permite distinguir acciones dentro de un mismo rol vía `PERMISSIONS`.
    """

    async def dependency(user: "User" = Depends(get_current_user)) -> "User":
        granted = PERMISSIONS.get(user.role, set())
        if "*" not in granted and not set(perms) & granted:
            raise PermissionDeniedError("No tienes permisos para esta acción")
        return user

    return dependency


def ensure_same_institution(user: "User", institution_id: object) -> None:
    if user.institution_id != institution_id:
        raise PermissionDeniedError("Recurso de otra institución")
