from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from logica.db import get_session_factory
from logica.modules.evaluations.models import EvaluationAttempt
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


async def _setup_single_exercise_evaluation(
    client: AsyncClient,
    teacher_access: str,
    duration_minutes: int | None = None,
    is_ranked: bool = False,
) -> tuple[str, str]:
    """Returns (group_id, evaluation_id) with one enabled true_false exercise."""
    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(
        client, teacher_access, language_id, content={"statement": "2+2=4", "answer": True}
    )
    await attach_exercise(client, teacher_access, exercise["id"], topic_id)
    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_id)

    created = await client.post(
        "/evaluations",
        json={
            "group_id": group["id"],
            "title": "Quiz",
            "mode": "cumulative",
            "duration_minutes": duration_minutes,
            "is_ranked": is_ranked,
            "exercise_ids": [exercise["id"]],
        },
        headers=auth_headers(teacher_access),
    )
    assert created.status_code == 201, created.text
    return group["id"], created.json()["id"]


async def test_list_group_evaluations_visible_to_teacher_and_student(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    group_id, evaluation_id = await _setup_single_exercise_evaluation(client, teacher_access)
    group = (await client.get("/groups/mine", headers=auth_headers(teacher_access))).json()[0]
    await join_group(client, student_access, group["invite_code"])

    for access in (teacher_access, student_access):
        resp = await client.get(f"/groups/{group_id}/evaluations", headers=auth_headers(access))
        assert resp.status_code == 200, resp.text
        evaluations = resp.json()
        assert len(evaluations) == 1
        assert evaluations[0]["id"] == evaluation_id
        assert evaluations[0]["title"] == "Quiz"


async def test_list_group_evaluations_forbidden_for_non_member(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    outsider_access, _ = await register_and_login(
        client, email=f"outsider@{domain}", role="student"
    )

    group_id, _ = await _setup_single_exercise_evaluation(client, teacher_access)

    resp = await client.get(
        f"/groups/{group_id}/evaluations", headers=auth_headers(outsider_access)
    )
    assert resp.status_code == 403


async def test_take_evaluation_hides_answer_key(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    group_id, evaluation_id = await _setup_single_exercise_evaluation(client, teacher_access)
    group = (await client.get("/groups/mine", headers=auth_headers(teacher_access))).json()[0]
    await join_group(client, student_access, group["invite_code"])

    take = await client.get(
        f"/evaluations/{evaluation_id}/take", headers=auth_headers(student_access)
    )
    assert take.status_code == 200
    body = take.json()
    assert len(body["exercises"]) == 1
    assert "answer" not in body["exercises"][0]["content"]
    assert body["exercises"][0]["content"]["statement"] == "2+2=4"


async def test_full_attempt_flow_correct_answer(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    _, evaluation_id = await _setup_single_exercise_evaluation(client, teacher_access)
    group = (await client.get("/groups/mine", headers=auth_headers(teacher_access))).json()[0]
    await join_group(client, student_access, group["invite_code"])

    take = await client.get(
        f"/evaluations/{evaluation_id}/take", headers=auth_headers(student_access)
    )
    evaluation_exercise_id = take.json()["exercises"][0]["evaluation_exercise_id"]

    answer_resp = await client.post(
        f"/evaluations/{evaluation_id}/answers",
        json={"evaluation_exercise_id": evaluation_exercise_id, "answer": {"value": True}},
        headers=auth_headers(student_access),
    )
    assert answer_resp.status_code == 201
    assert "score" not in answer_resp.json()  # no leaking correctness mid-evaluation

    submit_resp = await client.post(
        f"/evaluations/{evaluation_id}/submit", headers=auth_headers(student_access)
    )
    assert submit_resp.status_code == 200
    result = submit_resp.json()
    assert result["status"] == "submitted"
    assert result["total_score"] == 1.0
    assert result["max_score"] == 1.0
    assert result["answers"][0]["correct"] is True

    # GET result matches, and is idempotent to fetch repeatedly.
    get_result = await client.get(
        f"/evaluations/{evaluation_id}/result", headers=auth_headers(student_access)
    )
    assert get_result.json() == result


async def test_double_submit_is_idempotent(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    _, evaluation_id = await _setup_single_exercise_evaluation(client, teacher_access)
    group = (await client.get("/groups/mine", headers=auth_headers(teacher_access))).json()[0]
    await join_group(client, student_access, group["invite_code"])

    take = await client.get(
        f"/evaluations/{evaluation_id}/take", headers=auth_headers(student_access)
    )
    evaluation_exercise_id = take.json()["exercises"][0]["evaluation_exercise_id"]
    await client.post(
        f"/evaluations/{evaluation_id}/answers",
        json={"evaluation_exercise_id": evaluation_exercise_id, "answer": {"value": True}},
        headers=auth_headers(student_access),
    )

    first = await client.post(
        f"/evaluations/{evaluation_id}/submit", headers=auth_headers(student_access)
    )
    second = await client.post(
        f"/evaluations/{evaluation_id}/submit", headers=auth_headers(student_access)
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


async def test_empty_answer_scores_zero(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    _, evaluation_id = await _setup_single_exercise_evaluation(client, teacher_access)
    group = (await client.get("/groups/mine", headers=auth_headers(teacher_access))).json()[0]
    await join_group(client, student_access, group["invite_code"])

    await client.get(f"/evaluations/{evaluation_id}/take", headers=auth_headers(student_access))
    # Student never answers anything, just finalizes (§8.2 respuesta vacía).
    submit_resp = await client.post(
        f"/evaluations/{evaluation_id}/submit", headers=auth_headers(student_access)
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["total_score"] == 0.0


async def test_late_answer_submission_rejected(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    _, evaluation_id = await _setup_single_exercise_evaluation(
        client, teacher_access, duration_minutes=10
    )
    group = (await client.get("/groups/mine", headers=auth_headers(teacher_access))).json()[0]
    await join_group(client, student_access, group["invite_code"])

    take = await client.get(
        f"/evaluations/{evaluation_id}/take", headers=auth_headers(student_access)
    )
    evaluation_exercise_id = take.json()["exercises"][0]["evaluation_exercise_id"]

    # Simulate time passing well beyond the 10-minute window + tolerance.
    session_factory = get_session_factory()
    async with session_factory() as db:
        result = await db.execute(
            select(EvaluationAttempt).where(EvaluationAttempt.evaluation_id == evaluation_id)
        )
        attempt = result.scalar_one()
        attempt.started_at = datetime.now(UTC) - timedelta(minutes=30)
        await db.commit()

    late_answer = await client.post(
        f"/evaluations/{evaluation_id}/answers",
        json={"evaluation_exercise_id": evaluation_exercise_id, "answer": {"value": True}},
        headers=auth_headers(student_access),
    )
    assert late_answer.status_code == 409

    submit_resp = await client.post(
        f"/evaluations/{evaluation_id}/submit", headers=auth_headers(student_access)
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "expired"
    assert submit_resp.json()["total_score"] == 0.0
