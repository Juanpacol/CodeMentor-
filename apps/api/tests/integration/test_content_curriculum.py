from httpx import AsyncClient

from logica.modules.users.models import Institution
from tests.integration.conftest import (
    auth_headers,
    create_language,
    create_topic,
    register_and_login,
)


async def test_student_cannot_create_topic(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)

    resp = await client.post(
        "/topics",
        json={"language_id": language_id, "name": "Ciclos", "level": "basico", "order_index": 1},
        headers=auth_headers(student_access),
    )
    assert resp.status_code == 403


async def test_topic_locked_by_default_in_curriculum(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    await create_topic(client, teacher_access, language_id)

    group = await client.post(
        "/groups", json={"name": "10-1"}, headers=auth_headers(teacher_access)
    )
    group_id = group.json()["id"]
    invite_code = group.json()["invite_code"]
    await client.post(
        "/groups/join", json={"invite_code": invite_code}, headers=auth_headers(student_access)
    )

    curriculum = await client.get(
        f"/groups/{group_id}/curriculum", headers=auth_headers(student_access)
    )
    assert curriculum.status_code == 200
    items = curriculum.json()
    assert len(items) == 1
    assert items[0]["state"] == "locked"


async def test_enable_topic_makes_it_visible_only_to_that_group(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_a, _ = await register_and_login(client, email=f"est-a@{domain}", role="student")
    student_b, _ = await register_and_login(client, email=f"est-b@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)

    group_a = (
        await client.post("/groups", json={"name": "10-1"}, headers=auth_headers(teacher_access))
    ).json()
    group_b = (
        await client.post("/groups", json={"name": "10-2"}, headers=auth_headers(teacher_access))
    ).json()

    await client.post(
        "/groups/join",
        json={"invite_code": group_a["invite_code"]},
        headers=auth_headers(student_a),
    )
    await client.post(
        "/groups/join",
        json={"invite_code": group_b["invite_code"]},
        headers=auth_headers(student_b),
    )

    enable_resp = await client.post(
        f"/groups/{group_a['id']}/topics/{topic_id}/enable", headers=auth_headers(teacher_access)
    )
    assert enable_resp.status_code == 200

    curriculum_a = await client.get(
        f"/groups/{group_a['id']}/curriculum", headers=auth_headers(student_a)
    )
    assert curriculum_a.json()[0]["state"] == "enabled"
    assert curriculum_a.json()[0]["enabled_at"] is not None

    curriculum_b = await client.get(
        f"/groups/{group_b['id']}/curriculum", headers=auth_headers(student_b)
    )
    assert curriculum_b.json()[0]["state"] == "locked"


async def test_disable_topic_locks_it_again(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = (
        await client.post("/groups", json={"name": "10-1"}, headers=auth_headers(teacher_access))
    ).json()

    await client.post(
        f"/groups/{group['id']}/topics/{topic_id}/enable", headers=auth_headers(teacher_access)
    )
    disable_resp = await client.post(
        f"/groups/{group['id']}/topics/{topic_id}/disable", headers=auth_headers(teacher_access)
    )
    assert disable_resp.status_code == 200

    curriculum = await client.get(
        f"/groups/{group['id']}/curriculum", headers=auth_headers(teacher_access)
    )
    assert curriculum.json()[0]["state"] == "locked"
    assert curriculum.json()[0]["enabled_at"] is None


async def test_hide_locked_topics_removes_them_from_student_view(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    await create_topic(client, teacher_access, language_id, name="Tema oculto")

    group = (
        await client.post("/groups", json={"name": "10-1"}, headers=auth_headers(teacher_access))
    ).json()
    await client.post(
        "/groups/join",
        json={"invite_code": group["invite_code"]},
        headers=auth_headers(student_access),
    )
    await client.patch(
        f"/groups/{group['id']}",
        json={"grade_or_shift": None},
        headers=auth_headers(teacher_access),
    )

    # Teacher still sees the locked topic (management view).
    teacher_view = await client.get(
        f"/groups/{group['id']}/curriculum", headers=auth_headers(teacher_access)
    )
    assert len(teacher_view.json()) == 1


async def test_topic_update_increments_version(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)

    updated = await client.patch(
        f"/topics/{topic_id}",
        json={"name": "Nuevo nombre"},
        headers=auth_headers(teacher_access),
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    unchanged = await client.patch(
        f"/topics/{topic_id}", json={}, headers=auth_headers(teacher_access)
    )
    assert unchanged.json()["version"] == 2


async def test_curriculum_ordered_by_order_index(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    await create_topic(client, teacher_access, language_id, name="Unidad 2", order_index=2)
    await create_topic(client, teacher_access, language_id, name="Unidad 1", order_index=1)

    group = (
        await client.post("/groups", json={"name": "10-1"}, headers=auth_headers(teacher_access))
    ).json()

    curriculum = await client.get(
        f"/groups/{group['id']}/curriculum", headers=auth_headers(teacher_access)
    )
    names = [item["topic"]["name"] for item in curriculum.json()]
    assert names == ["Unidad 1", "Unidad 2"]
