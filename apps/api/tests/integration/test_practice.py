from httpx import AsyncClient

from logica.modules.users.models import Institution
from tests.integration.conftest import (
    attach_exercise,
    auth_headers,
    create_exercise,
    create_group,
    create_language,
    create_topic,
    enable_topic,
    join_group,
    register_and_login,
)


async def test_practice_lists_only_enabled_topic_exercises(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_enabled = await create_topic(client, teacher_access, language_id, name="Habilitado")
    topic_locked = await create_topic(client, teacher_access, language_id, name="Bloqueado")
    exercise_enabled = await create_exercise(
        client, teacher_access, language_id, title="Ej habilitado"
    )
    exercise_locked = await create_exercise(
        client, teacher_access, language_id, title="Ej bloqueado"
    )
    await attach_exercise(client, teacher_access, exercise_enabled["id"], topic_enabled)
    await attach_exercise(client, teacher_access, exercise_locked["id"], topic_locked)

    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_enabled)
    await join_group(client, student_access, group["invite_code"])

    resp = await client.get(
        "/practice", params={"group_id": group["id"]}, headers=auth_headers(student_access)
    )
    assert resp.status_code == 200
    titles = [e["title"] for e in resp.json()]
    assert titles == ["Ej habilitado"]
    assert "answer" not in resp.json()[0]["content"]


async def test_practice_gives_immediate_feedback_and_allows_unlimited_attempts(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(
        client, teacher_access, language_id, content={"statement": "2+2=4", "answer": True}
    )
    await attach_exercise(client, teacher_access, exercise["id"], topic_id)
    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_id)
    await join_group(client, student_access, group["invite_code"])

    for _ in range(3):
        resp = await client.post(
            f"/practice/{exercise['id']}/submit",
            json={"group_id": group["id"], "answer": {"value": False}},
            headers=auth_headers(student_access),
        )
        assert resp.status_code == 200
        assert resp.json()["correct"] is False

    correct = await client.post(
        f"/practice/{exercise['id']}/submit",
        json={"group_id": group["id"], "answer": {"value": True}},
        headers=auth_headers(student_access),
    )
    assert correct.json()["correct"] is True


async def test_practice_rejects_exercise_from_locked_topic(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(client, teacher_access, language_id)
    await attach_exercise(client, teacher_access, exercise["id"], topic_id)
    group = await create_group(client, teacher_access)
    await join_group(client, student_access, group["invite_code"])
    # Topic never enabled.

    resp = await client.post(
        f"/practice/{exercise['id']}/submit",
        json={"group_id": group["id"], "answer": {"value": True}},
        headers=auth_headers(student_access),
    )
    assert resp.status_code == 403
