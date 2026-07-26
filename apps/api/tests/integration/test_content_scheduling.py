from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient

from logica.db import get_session_factory
from logica.modules.content.service import enable_scheduled_topics
from logica.modules.users.models import Institution
from tests.integration.conftest import (
    auth_headers,
    create_language,
    create_topic,
    register_and_login,
)


async def test_schedule_topic_stays_locked_until_due(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = (
        await client.post("/groups", json={"name": "10-1"}, headers=auth_headers(teacher_access))
    ).json()

    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    scheduled = await client.post(
        f"/groups/{group['id']}/topics/{topic_id}/schedule",
        json={"enable_at": future},
        headers=auth_headers(teacher_access),
    )
    assert scheduled.status_code == 200

    session_factory = get_session_factory()
    async with session_factory() as db:
        flipped = await enable_scheduled_topics(db)
        await db.commit()
    assert flipped == 0

    curriculum = await client.get(
        f"/groups/{group['id']}/curriculum", headers=auth_headers(teacher_access)
    )
    assert curriculum.json()[0]["state"] == "locked"
    assert curriculum.json()[0]["scheduled_enable_at"] is not None


async def test_scheduled_topic_enables_once_due(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = (
        await client.post("/groups", json={"name": "10-1"}, headers=auth_headers(teacher_access))
    ).json()

    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    await client.post(
        f"/groups/{group['id']}/topics/{topic_id}/schedule",
        json={"enable_at": past},
        headers=auth_headers(teacher_access),
    )

    session_factory = get_session_factory()
    async with session_factory() as db:
        flipped = await enable_scheduled_topics(db)
        await db.commit()
    assert flipped == 1

    curriculum = await client.get(
        f"/groups/{group['id']}/curriculum", headers=auth_headers(teacher_access)
    )
    assert curriculum.json()[0]["state"] == "enabled"
    assert curriculum.json()[0]["scheduled_enable_at"] is None


async def test_scheduled_topic_enable_isolates_bad_row(
    client: AsyncClient, institution: Institution, monkeypatch: Any
) -> None:
    """A failing row must not abort the whole tick (§ pipeline robustness):
    each row runs in its own SAVEPOINT, so one bad row stays `locked` for the
    next tick while the rest of the due rows still get enabled."""
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id_bad = await create_topic(client, teacher_access, language_id, order_index=1)
    topic_id_good = await create_topic(client, teacher_access, language_id, order_index=2)
    group = (
        await client.post("/groups", json={"name": "10-1"}, headers=auth_headers(teacher_access))
    ).json()

    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    for topic_id in (topic_id_bad, topic_id_good):
        scheduled = await client.post(
            f"/groups/{group['id']}/topics/{topic_id}/schedule",
            json={"enable_at": past},
            headers=auth_headers(teacher_access),
        )
        assert scheduled.status_code == 200

    session_factory = get_session_factory()
    async with session_factory() as db:
        original_flush = db.flush
        call_count = 0

        async def flaky_flush(*args: Any, **kwargs: Any) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated failure on the first row")
            await original_flush(*args, **kwargs)

        monkeypatch.setattr(db, "flush", flaky_flush)
        flipped = await enable_scheduled_topics(db)
        await db.commit()

    assert flipped == 1

    curriculum = await client.get(
        f"/groups/{group['id']}/curriculum", headers=auth_headers(teacher_access)
    )
    states = {row["topic"]["id"]: row["state"] for row in curriculum.json()}
    assert states[topic_id_bad] == "locked"
    assert states[topic_id_good] == "enabled"
