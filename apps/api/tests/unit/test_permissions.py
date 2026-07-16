import uuid

import pytest

from logica.core.errors import PermissionDeniedError
from logica.core.permissions import ensure_same_institution, require_role
from logica.modules.users.models import Role, User


def _make_user(role: Role) -> User:
    return User(
        id=uuid.uuid4(),
        institution_id=uuid.uuid4(),
        email="alguien@example.com",
        full_name="Alguien",
        hashed_password="irrelevant",
        role=role,
        is_active=True,
    )


async def test_require_role_allows_matching_role() -> None:
    dependency = require_role("teacher", "admin")
    teacher = _make_user(Role.teacher)
    result = await dependency(user=teacher)
    assert result is teacher


async def test_require_role_rejects_non_matching_role() -> None:
    dependency = require_role("teacher", "admin")
    student = _make_user(Role.student)
    with pytest.raises(PermissionDeniedError):
        await dependency(user=student)


def test_ensure_same_institution_passes_when_equal() -> None:
    user = _make_user(Role.teacher)
    ensure_same_institution(user, user.institution_id)


def test_ensure_same_institution_raises_when_different() -> None:
    user = _make_user(Role.teacher)
    with pytest.raises(PermissionDeniedError):
        ensure_same_institution(user, uuid.uuid4())
