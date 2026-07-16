import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from logica.db import get_engine, get_session_factory
from logica.modules.users.models import Institution

_TABLES = (
    "audit_logs",
    "evaluation_answers",
    "evaluation_attempts",
    "evaluation_exercises",
    "evaluations",
    "practice_submissions",
    "topic_group_states",
    "topic_exercises",
    "exercises",
    "topics",
    "languages",
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


async def create_language(client: AsyncClient, teacher_access: str, slug: str = "python") -> str:
    resp = await client.post(
        "/languages",
        json={"name": "Python", "slug": slug, "syntax_mode": "python"},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 201, resp.text
    language_id: str = resp.json()["id"]
    return language_id


async def create_topic(
    client: AsyncClient,
    teacher_access: str,
    language_id: str,
    name: str = "Estructuras condicionales",
    level: str = "basico",
    order_index: int = 1,
) -> str:
    resp = await client.post(
        "/topics",
        json={
            "language_id": language_id,
            "name": name,
            "level": level,
            "order_index": order_index,
        },
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 201, resp.text
    topic_id: str = resp.json()["id"]
    return topic_id


async def create_group(client: AsyncClient, teacher_access: str, name: str = "10-1") -> dict:
    resp = await client.post("/groups", json={"name": name}, headers=auth_headers(teacher_access))
    assert resp.status_code == 201, resp.text
    group: dict = resp.json()
    return group


async def create_exercise(
    client: AsyncClient,
    teacher_access: str,
    language_id: str,
    exercise_type: str = "true_false",
    content: dict | None = None,
    title: str = "Ejercicio",
) -> dict:
    resp = await client.post(
        "/exercises",
        json={
            "language_id": language_id,
            "title": title,
            "type": exercise_type,
            "content": content or {"statement": "2+2=4", "answer": True},
        },
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 201, resp.text
    exercise: dict = resp.json()
    return exercise


async def attach_exercise(
    client: AsyncClient, teacher_access: str, exercise_id: str, topic_id: str
) -> None:
    resp = await client.post(
        f"/exercises/{exercise_id}/topics/{topic_id}", headers=auth_headers(teacher_access)
    )
    assert resp.status_code == 201, resp.text


async def enable_topic(
    client: AsyncClient, teacher_access: str, group_id: str, topic_id: str
) -> None:
    resp = await client.post(
        f"/groups/{group_id}/topics/{topic_id}/enable", headers=auth_headers(teacher_access)
    )
    assert resp.status_code == 200, resp.text


async def join_group(client: AsyncClient, student_access: str, invite_code: str) -> None:
    resp = await client.post(
        "/groups/join", json={"invite_code": invite_code}, headers=auth_headers(student_access)
    )
    assert resp.status_code == 201, resp.text
