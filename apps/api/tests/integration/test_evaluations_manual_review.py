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


async def test_argued_response_needs_manual_review_and_teacher_can_score_it(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(
        client,
        teacher_access,
        language_id,
        exercise_type="argued_response",
        content={"prompt": "Explica por qué usarías un ciclo Mientras en vez de Para"},
    )
    await attach_exercise(client, teacher_access, exercise["id"], topic_id)
    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_id)

    created = await client.post(
        "/evaluations",
        json={
            "group_id": group["id"],
            "title": "Argumentativa",
            "mode": "cumulative",
            "exercise_ids": [exercise["id"]],
        },
        headers=auth_headers(teacher_access),
    )
    evaluation_id = created.json()["id"]

    await join_group(client, student_access, group["invite_code"])
    take = await client.get(
        f"/evaluations/{evaluation_id}/take", headers=auth_headers(student_access)
    )
    evaluation_exercise_id = take.json()["exercises"][0]["evaluation_exercise_id"]

    await client.post(
        f"/evaluations/{evaluation_id}/answers",
        json={
            "evaluation_exercise_id": evaluation_exercise_id,
            "answer": {"text": "Porque no sabemos cuántas veces se repetirá de antemano."},
        },
        headers=auth_headers(student_access),
    )
    submit = await client.post(
        f"/evaluations/{evaluation_id}/submit", headers=auth_headers(student_access)
    )
    assert submit.json()["total_score"] == 0.0
    assert submit.json()["answers"][0]["needs_manual_review"] is True

    # Student cannot see the manual review queue.
    forbidden = await client.get(
        f"/evaluations/{evaluation_id}/manual-review", headers=auth_headers(student_access)
    )
    assert forbidden.status_code == 403

    queue = await client.get(
        f"/evaluations/{evaluation_id}/manual-review", headers=auth_headers(teacher_access)
    )
    assert queue.status_code == 200
    assert len(queue.json()) == 1
    answer_id = queue.json()[0]["answer_id"]

    reviewed = await client.post(
        f"/evaluations/{evaluation_id}/manual-review/{answer_id}",
        json={"score": 0.8},
        headers=auth_headers(teacher_access),
    )
    assert reviewed.status_code == 200

    # Queue is now empty and the student's total score reflects the review.
    empty_queue = await client.get(
        f"/evaluations/{evaluation_id}/manual-review", headers=auth_headers(teacher_access)
    )
    assert empty_queue.json() == []

    final_result = await client.get(
        f"/evaluations/{evaluation_id}/result", headers=auth_headers(student_access)
    )
    assert final_result.json()["total_score"] == 0.8
    assert final_result.json()["answers"][0]["manual_score"] == 0.8


async def test_empty_argued_response_does_not_need_review(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(
        client,
        teacher_access,
        language_id,
        exercise_type="argued_response",
        content={"prompt": "Explica"},
    )
    await attach_exercise(client, teacher_access, exercise["id"], topic_id)
    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_id)

    created = await client.post(
        "/evaluations",
        json={
            "group_id": group["id"],
            "title": "Argumentativa",
            "mode": "cumulative",
            "exercise_ids": [exercise["id"]],
        },
        headers=auth_headers(teacher_access),
    )
    evaluation_id = created.json()["id"]
    await join_group(client, student_access, group["invite_code"])
    take = await client.get(
        f"/evaluations/{evaluation_id}/take", headers=auth_headers(student_access)
    )
    evaluation_exercise_id = take.json()["exercises"][0]["evaluation_exercise_id"]
    await client.post(
        f"/evaluations/{evaluation_id}/answers",
        json={"evaluation_exercise_id": evaluation_exercise_id, "answer": {"text": "   "}},
        headers=auth_headers(student_access),
    )

    submit = await client.post(
        f"/evaluations/{evaluation_id}/submit", headers=auth_headers(student_access)
    )
    assert submit.json()["answers"][0]["needs_manual_review"] is False

    queue = await client.get(
        f"/evaluations/{evaluation_id}/manual-review", headers=auth_headers(teacher_access)
    )
    assert queue.json() == []
