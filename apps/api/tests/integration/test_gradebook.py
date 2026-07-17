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


async def _submit_true_false(client: AsyncClient, access: str, evaluation_id: str) -> None:
    take = await client.get(f"/evaluations/{evaluation_id}/take", headers=auth_headers(access))
    evaluation_exercise_id = take.json()["exercises"][0]["evaluation_exercise_id"]
    await client.post(
        f"/evaluations/{evaluation_id}/answers",
        json={"evaluation_exercise_id": evaluation_exercise_id, "answer": {"value": True}},
        headers=auth_headers(access),
    )
    resp = await client.post(f"/evaluations/{evaluation_id}/submit", headers=auth_headers(access))
    assert resp.status_code == 200, resp.text


async def _setup_group_with_two_evaluations(
    client: AsyncClient, teacher_access: str
) -> tuple[str, str, str]:
    """Returns (group_id, evaluation_id_1, evaluation_id_2), each with one
    enabled true_false exercise worth 1 point."""
    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(
        client, teacher_access, language_id, content={"statement": "2+2=4", "answer": True}
    )
    await attach_exercise(client, teacher_access, exercise["id"], topic_id)
    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_id)

    evaluation_ids = []
    for title in ("Quiz 1", "Quiz 2"):
        created = await client.post(
            "/evaluations",
            json={
                "group_id": group["id"],
                "title": title,
                "mode": "cumulative",
                "is_ranked": False,
                "exercise_ids": [exercise["id"]],
            },
            headers=auth_headers(teacher_access),
        )
        assert created.status_code == 201, created.text
        evaluation_ids.append(created.json()["id"])

    return group["id"], evaluation_ids[0], evaluation_ids[1]


async def test_gradebook_returns_matrix(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_a_access, _ = await register_and_login(
        client, email=f"esta@{domain}", full_name="Estudiante A", role="student"
    )
    student_b_access, _ = await register_and_login(
        client, email=f"estb@{domain}", full_name="Estudiante B", role="student"
    )

    group_id, eval1_id, eval2_id = await _setup_group_with_two_evaluations(client, teacher_access)
    group = (await client.get("/groups/mine", headers=auth_headers(teacher_access))).json()[0]
    await join_group(client, student_a_access, group["invite_code"])
    await join_group(client, student_b_access, group["invite_code"])

    # Estudiante A presenta ambas evaluaciones; Estudiante B solo la primera.
    await _submit_true_false(client, student_a_access, eval1_id)
    await _submit_true_false(client, student_a_access, eval2_id)
    await _submit_true_false(client, student_b_access, eval1_id)

    resp = await client.get(f"/groups/{group_id}/gradebook", headers=auth_headers(teacher_access))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert {e["title"] for e in body["evaluations"]} == {"Quiz 1", "Quiz 2"}

    by_name = {s["full_name"]: s for s in body["students"]}
    assert by_name["Estudiante A"]["evaluations_submitted"] == 2
    assert by_name["Estudiante A"]["avg_evaluation_score"] == 1.0
    assert {s["evaluation_id"]: s["total_score"] for s in by_name["Estudiante A"]["scores"]} == {
        eval1_id: 1.0,
        eval2_id: 1.0,
    }

    assert by_name["Estudiante B"]["evaluations_submitted"] == 1
    assert by_name["Estudiante B"]["avg_evaluation_score"] == 1.0
    assert [s["evaluation_id"] for s in by_name["Estudiante B"]["scores"]] == [eval1_id]


async def test_gradebook_requires_teacher(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    group_id, _, _ = await _setup_group_with_two_evaluations(client, teacher_access)
    group = (await client.get("/groups/mine", headers=auth_headers(teacher_access))).json()[0]
    await join_group(client, student_access, group["invite_code"])

    resp = await client.get(f"/groups/{group_id}/gradebook", headers=auth_headers(student_access))
    assert resp.status_code == 403


async def test_gradebook_foreign_group_forbidden(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    outsider_access, _ = await register_and_login(
        client, email=f"outsider@{domain}", role="teacher"
    )

    group_id, _, _ = await _setup_group_with_two_evaluations(client, teacher_access)

    resp = await client.get(f"/groups/{group_id}/gradebook", headers=auth_headers(outsider_access))
    assert resp.status_code == 403
