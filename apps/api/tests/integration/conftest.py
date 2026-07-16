import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from logica.db import get_engine, get_session_factory
from logica.modules.users.models import Institution

_TABLES = (
    "audit_logs",
    "group_memberships",
    "groups",
    "password_reset_tokens",
    "users",
    "institutions",
)


@pytest.fixture(autouse=True)
async def _clean_db() -> AsyncIterator[None]:
    """Truncates domain tables before every integration test for isolation.
    Runs against the dedicated test database (DATABASE_URL in CI/make test),
    never the dev database."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {', '.join(_TABLES)} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
async def institution() -> Institution:
    domain = f"colegio-{uuid.uuid4().hex[:8]}.edu.co"
    session_factory = get_session_factory()
    async with session_factory() as db:
        inst = Institution(name="Colegio de prueba", email_domains=[domain])
        db.add(inst)
        await db.commit()
        await db.refresh(inst)
        return inst


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def register_and_login(
    client: AsyncClient,
    *,
    email: str,
    password: str = "Sup3rSecreta!",
    full_name: str = "Usuaria de Prueba",
    role: str = "student",
    student_code: str | None = None,
) -> tuple[str, str]:
    """Registers a user and returns (access_token, refresh_token)."""
    payload = {
        "email": email,
        "password": password,
        "full_name": full_name,
        "role": role,
    }
    if student_code:
        payload["student_code"] = student_code

    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 201, resp.text

    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    tokens = resp.json()
    return tokens["access_token"], tokens["refresh_token"]
