from httpx import AsyncClient

from logica.modules.users.models import Institution
from tests.integration.conftest import (
    auth_headers,
    create_language,
    create_topic,
    register_and_login,
)


async def test_student_cannot_create_exercise(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)

    resp = await client.post(
        "/exercises",
        json={
            "language_id": language_id,
            "title": "Ejercicio",
            "type": "true_false",
            "content": {"statement": "2+2=4", "answer": True},
        },
        headers=auth_headers(student_access),
    )
    assert resp.status_code == 403


async def test_create_exercise_and_attach_to_topic(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)

    created = await client.post(
        "/exercises",
        json={
            "language_id": language_id,
            "title": "Selecciona la opción correcta",
            "type": "multiple_choice",
            "content": {"options": ["a", "b", "c"], "answer_index": 1},
        },
        headers=auth_headers(teacher_access),
    )
    assert created.status_code == 201
    exercise = created.json()
    assert exercise["origin"] == "teacher"
    assert exercise["status"] == "published"
    assert exercise["version"] == 1

    attach = await client.post(
        f"/exercises/{exercise['id']}/topics/{topic_id}", headers=auth_headers(teacher_access)
    )
    assert attach.status_code == 201

    duplicate = await client.post(
        f"/exercises/{exercise['id']}/topics/{topic_id}", headers=auth_headers(teacher_access)
    )
    assert duplicate.status_code == 409

    listed = await client.get(
        "/exercises", params={"topic_id": topic_id}, headers=auth_headers(teacher_access)
    )
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == exercise["id"]


async def test_update_exercise_increments_version(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    language_id = await create_language(client, teacher_access)

    created = await client.post(
        "/exercises",
        json={
            "language_id": language_id,
            "title": "V/F",
            "type": "true_false",
            "content": {"statement": "PSeInt usa 'Mientras'", "answer": True},
        },
        headers=auth_headers(teacher_access),
    )
    exercise_id = created.json()["id"]

    updated = await client.patch(
        f"/exercises/{exercise_id}",
        json={"content": {"statement": "PSeInt usa 'Mientras'", "answer": False}},
        headers=auth_headers(teacher_access),
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    draft = await client.patch(
        f"/exercises/{exercise_id}",
        json={"status": "draft"},
        headers=auth_headers(teacher_access),
    )
    assert draft.json()["status"] == "draft"
    assert draft.json()["version"] == 2


async def test_editing_published_exercise_snapshots_previous_version(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    language_id = await create_language(client, teacher_access)

    created = await client.post(
        "/exercises",
        json={
            "language_id": language_id,
            "title": "Original",
            "type": "true_false",
            "content": {"statement": "2+2=4", "answer": True},
        },
        headers=auth_headers(teacher_access),
    )
    exercise_id = created.json()["id"]

    await client.patch(
        f"/exercises/{exercise_id}",
        json={"title": "Editado"},
        headers=auth_headers(teacher_access),
    )

    versions = await client.get(
        f"/exercises/{exercise_id}/versions", headers=auth_headers(teacher_access)
    )
    assert versions.status_code == 200
    body = versions.json()
    assert len(body) == 1
    assert body[0]["title"] == "Original"
    assert body[0]["version"] == 1


async def test_restore_exercise_version_reverts_content_and_stays_reversible(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    language_id = await create_language(client, teacher_access)

    created = await client.post(
        "/exercises",
        json={
            "language_id": language_id,
            "title": "Original",
            "type": "true_false",
            "content": {"statement": "2+2=4", "answer": True},
        },
        headers=auth_headers(teacher_access),
    )
    exercise_id = created.json()["id"]

    await client.patch(
        f"/exercises/{exercise_id}",
        json={"title": "Editado"},
        headers=auth_headers(teacher_access),
    )

    versions = await client.get(
        f"/exercises/{exercise_id}/versions", headers=auth_headers(teacher_access)
    )
    version_id = versions.json()[0]["id"]

    restored = await client.post(
        f"/exercises/{exercise_id}/versions/{version_id}/restore",
        headers=auth_headers(teacher_access),
    )
    assert restored.status_code == 200
    assert restored.json()["title"] == "Original"
    assert restored.json()["version"] == 3

    versions_after = await client.get(
        f"/exercises/{exercise_id}/versions", headers=auth_headers(teacher_access)
    )
    assert len(versions_after.json()) == 2
