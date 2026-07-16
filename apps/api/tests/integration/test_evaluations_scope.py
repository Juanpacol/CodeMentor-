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
    register_and_login,
)


async def test_student_cannot_create_evaluation(
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

    resp = await client.post(
        "/evaluations",
        json={
            "group_id": group["id"],
            "title": "Quiz",
            "mode": "cumulative",
            "exercise_ids": [exercise["id"]],
        },
        headers=auth_headers(student_access),
    )
    assert resp.status_code == 403


async def test_fixed_mode_requires_up_to_topic(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(client, teacher_access, language_id)
    await attach_exercise(client, teacher_access, exercise["id"], topic_id)
    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_id)

    resp = await client.post(
        "/evaluations",
        json={
            "group_id": group["id"],
            "title": "Quiz",
            "mode": "fixed",
            "exercise_ids": [exercise["id"]],
        },
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 422


async def test_cannot_include_exercise_from_disabled_topic(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(client, teacher_access, language_id)
    await attach_exercise(client, teacher_access, exercise["id"], topic_id)
    group = await create_group(client, teacher_access)
    # Topic never enabled for this group.

    resp = await client.post(
        "/evaluations",
        json={
            "group_id": group["id"],
            "title": "Quiz",
            "mode": "cumulative",
            "exercise_ids": [exercise["id"]],
        },
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 422


async def test_fixed_mode_excludes_exercises_beyond_up_to_topic(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_1 = await create_topic(
        client, teacher_access, language_id, name="Unidad 1", order_index=1
    )
    topic_2 = await create_topic(
        client, teacher_access, language_id, name="Unidad 2", order_index=2
    )

    exercise_1 = await create_exercise(client, teacher_access, language_id, title="Ej unidad 1")
    exercise_2 = await create_exercise(client, teacher_access, language_id, title="Ej unidad 2")
    await attach_exercise(client, teacher_access, exercise_1["id"], topic_1)
    await attach_exercise(client, teacher_access, exercise_2["id"], topic_2)

    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_1)
    await enable_topic(client, teacher_access, group["id"], topic_2)

    # Evaluation only reaches unidad 1: exercise_2 must be rejected.
    resp = await client.post(
        "/evaluations",
        json={
            "group_id": group["id"],
            "title": "Parcial 1",
            "mode": "fixed",
            "up_to_topic_id": topic_1,
            "exercise_ids": [exercise_2["id"]],
        },
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 422

    # But exercise_1 is fine.
    ok = await client.post(
        "/evaluations",
        json={
            "group_id": group["id"],
            "title": "Parcial 1",
            "mode": "fixed",
            "up_to_topic_id": topic_1,
            "exercise_ids": [exercise_1["id"]],
        },
        headers=auth_headers(teacher_access),
    )
    assert ok.status_code == 201


async def test_cumulative_mode_includes_all_enabled_topics(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_1 = await create_topic(
        client, teacher_access, language_id, name="Unidad 1", order_index=1
    )
    topic_2 = await create_topic(
        client, teacher_access, language_id, name="Unidad 2", order_index=2
    )
    exercise_1 = await create_exercise(client, teacher_access, language_id, title="Ej 1")
    exercise_2 = await create_exercise(client, teacher_access, language_id, title="Ej 2")
    await attach_exercise(client, teacher_access, exercise_1["id"], topic_1)
    await attach_exercise(client, teacher_access, exercise_2["id"], topic_2)

    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_1)
    await enable_topic(client, teacher_access, group["id"], topic_2)

    resp = await client.post(
        "/evaluations",
        json={
            "group_id": group["id"],
            "title": "Acumulativa",
            "mode": "cumulative",
            "exercise_ids": [exercise_1["id"], exercise_2["id"]],
        },
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 201
