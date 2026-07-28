from datetime import UTC, datetime, timedelta

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


async def test_notifications_start_empty(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    resp = await client.get("/notifications", headers=auth_headers(student_access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["unread_count"] == 0


async def test_notification_generated_for_assignment_due_tomorrow(
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
    await enable_topic(client, teacher_access, group["id"], topic_id)
    await join_group(client, student_access, group["invite_code"])

    due_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    create_resp = await client.post(
        f"/groups/{group['id']}/assignments",
        json={"title": "Tarea urgente", "topic_id": topic_id, "due_at": due_at},
        headers=auth_headers(teacher_access),
    )
    assert create_resp.status_code == 201, create_resp.text

    resp = await client.get("/notifications", headers=auth_headers(student_access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["unread_count"] == 1
    assert body["items"][0]["kind"] == "assignment_due"
    assert "Tarea urgente" in body["items"][0]["title"]

    # Repeating the request must not duplicate the notification (dedupe).
    again = await client.get("/notifications", headers=auth_headers(student_access))
    assert again.json()["unread_count"] == 1


async def test_mark_notification_read_and_read_all(
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
    await enable_topic(client, teacher_access, group["id"], topic_id)
    await join_group(client, student_access, group["invite_code"])

    due_at = datetime.now(UTC).isoformat()
    await client.post(
        f"/groups/{group['id']}/assignments",
        json={"title": "Tarea de hoy", "topic_id": topic_id, "due_at": due_at},
        headers=auth_headers(teacher_access),
    )

    listed = await client.get("/notifications", headers=auth_headers(student_access))
    notification_id = listed.json()["items"][0]["id"]

    read_resp = await client.post(
        f"/notifications/{notification_id}/read", headers=auth_headers(student_access)
    )
    assert read_resp.status_code == 200
    assert read_resp.json()["read_at"] is not None

    after_read = await client.get("/notifications", headers=auth_headers(student_access))
    assert after_read.json()["unread_count"] == 0

    read_all = await client.post("/notifications/read-all", headers=auth_headers(student_access))
    assert read_all.status_code == 204


async def test_notification_scoped_to_owner(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_a, _ = await register_and_login(client, email=f"a@{domain}", role="student")
    student_b, _ = await register_and_login(client, email=f"b@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(client, teacher_access, language_id)
    await attach_exercise(client, teacher_access, exercise["id"], topic_id)
    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_id)
    await join_group(client, student_a, group["invite_code"])

    due_at = datetime.now(UTC).isoformat()
    await client.post(
        f"/groups/{group['id']}/assignments",
        json={"title": "Solo para A", "topic_id": topic_id, "due_at": due_at},
        headers=auth_headers(teacher_access),
    )

    listed_a = await client.get("/notifications", headers=auth_headers(student_a))
    notification_id = listed_a.json()["items"][0]["id"]

    forbidden = await client.post(
        f"/notifications/{notification_id}/read", headers=auth_headers(student_b)
    )
    assert forbidden.status_code == 404
