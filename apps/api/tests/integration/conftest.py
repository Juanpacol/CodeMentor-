import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select, text

from logica.config import get_settings
from logica.db import get_engine, get_session_factory
from logica.modules.users.models import Institution, User

_TABLES = (
    "audit_logs",
    "ai_interactions",
    "rag_chunks",
    "rag_documents",
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
    """Truncates domain tables and flushes the dedicated test Redis database
    before every integration test for isolation. Runs against DATABASE_URL/
    REDIS_URL as set by `make test` (test DB / Redis db 1), never dev data.

    Disposing the engine on teardown is required, not just tidy: pytest-
    asyncio hands each test function its own event loop, but `get_engine()`
    caches a single AsyncEngine at module scope. Tests that go through the
    `client` fixture get this disposal for free (its ASGI lifespan shutdown
    calls it), but a test that only touches the DB/Redis directly never
    triggers that lifespan — without disposing here too, its connections
    stay bound to a loop that's about to close, and the *next* test's fresh
    loop then fails with "Event loop is closed" / "attached to a different
    loop" the moment it tries to reuse the pool."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {', '.join(_TABLES)} RESTART IDENTITY CASCADE"))

    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()

    yield

    await engine.dispose()


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


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


async def get_user_by_email(email: str) -> User:
    session_factory = get_session_factory()
    async with session_factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one()


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
