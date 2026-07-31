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


async def test_practice_filters_by_topic_status_and_mastery(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_a = await create_topic(client, teacher_access, language_id, name="Tema A")
    topic_b = await create_topic(client, teacher_access, language_id, name="Tema B")
    exercise_a = await create_exercise(client, teacher_access, language_id, title="Ej A")
    exercise_b = await create_exercise(client, teacher_access, language_id, title="Ej B")
    await attach_exercise(client, teacher_access, exercise_a["id"], topic_a)
    await attach_exercise(client, teacher_access, exercise_b["id"], topic_b)

    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_a)
    await enable_topic(client, teacher_access, group["id"], topic_b)
    await join_group(client, student_access, group["invite_code"])

    # Solve exercise_a correctly so it shows up as "done".
    submit = await client.post(
        f"/practice/{exercise_a['id']}/submit",
        json={"group_id": group["id"], "answer": {"value": True}},
        headers=auth_headers(student_access),
    )
    assert submit.status_code == 200

    by_topic = await client.get(
        "/practice",
        params={"group_id": group["id"], "topic_id": topic_b},
        headers=auth_headers(student_access),
    )
    assert [e["title"] for e in by_topic.json()] == ["Ej B"]

    done = await client.get(
        "/practice",
        params={"group_id": group["id"], "status": "done"},
        headers=auth_headers(student_access),
    )
    assert [e["title"] for e in done.json()] == ["Ej A"]
    assert done.json()[0]["done"] is True

    pending = await client.get(
        "/practice",
        params={"group_id": group["id"], "status": "pending"},
        headers=auth_headers(student_access),
    )
    assert [e["title"] for e in pending.json()] == ["Ej B"]

    # No solved exercise in topic B yet → "new" mastery.
    new_mastery = await client.get(
        "/practice",
        params={"group_id": group["id"], "mastery": "new"},
        headers=auth_headers(student_access),
    )
    assert [e["title"] for e in new_mastery.json()] == ["Ej B"]


async def test_practice_history_lists_submissions_most_recent_first(
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

    await client.post(
        f"/practice/{exercise['id']}/submit",
        json={"group_id": group["id"], "answer": {"value": False}},
        headers=auth_headers(student_access),
    )
    await client.post(
        f"/practice/{exercise['id']}/submit",
        json={"group_id": group["id"], "answer": {"value": True}},
        headers=auth_headers(student_access),
    )

    resp = await client.get(
        f"/practice/{exercise['id']}/history", headers=auth_headers(student_access)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["correct"] is True
    assert body[1]["correct"] is False
