import pytest
from httpx import AsyncClient

from logica.ai.harness.router import CompletionResult
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


async def _setup_live_code_evaluation(
    client: AsyncClient, teacher_access: str, student_access: str
) -> tuple[str, str]:
    """Returns (evaluation_id, answer_id) for a submitted live_code answer."""
    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(
        client,
        teacher_access,
        language_id,
        exercise_type="live_code",
        content={
            "language": "python",
            "version": "3.10.0",
            "starter_code": "print(2 + 2)",
            "test_cases": [{"stdin": "", "expected_stdout": "4"}],
        },
    )
    await attach_exercise(client, teacher_access, exercise["id"], topic_id)
    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_id)

    created = await client.post(
        "/evaluations",
        json={
            "group_id": group["id"],
            "title": "Reto en vivo",
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
        json={"evaluation_exercise_id": evaluation_exercise_id, "answer": {"code": "print(2 + 2)"}},
        headers=auth_headers(student_access),
    )
    await client.post(f"/evaluations/{evaluation_id}/submit", headers=auth_headers(student_access))

    answers = await client.get(
        f"/evaluations/{evaluation_id}/answers", headers=auth_headers(teacher_access)
    )
    answer_id = answers.json()[0]["answer_id"]
    return evaluation_id, answer_id


async def test_integrity_check_creates_alert(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    evaluation_id, answer_id = await _setup_live_code_evaluation(
        client, teacher_access, student_access
    )

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(
            text=(
                '{"suspicious": false, "reasoning": "El código es simple y coherente con el reto"}'
            ),
            model="groq/fake",
            prompt_tokens=1,
            completion_tokens=1,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    resp = await client.post(
        "/ai/integrity/check",
        json={"evaluation_id": evaluation_id, "answer_id": answer_id},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 200
    assert resp.json()["suspicious"] is False

    alerts = await client.get(
        f"/ai/evaluations/{evaluation_id}/integrity-alerts", headers=auth_headers(teacher_access)
    )
    assert len(alerts.json()) == 1
    assert alerts.json()[0]["evaluation_answer_id"] == answer_id


async def test_integrity_check_rejects_non_live_code_exercise(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(client, teacher_access, language_id)  # true_false by default
    await attach_exercise(client, teacher_access, exercise["id"], topic_id)
    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_id)

    created = await client.post(
        "/evaluations",
        json={
            "group_id": group["id"],
            "title": "Quiz",
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
        json={"evaluation_exercise_id": evaluation_exercise_id, "answer": {"value": True}},
        headers=auth_headers(student_access),
    )
    await client.post(f"/evaluations/{evaluation_id}/submit", headers=auth_headers(student_access))

    answers = await client.get(
        f"/evaluations/{evaluation_id}/answers", headers=auth_headers(teacher_access)
    )
    answer_id = answers.json()[0]["answer_id"]

    resp = await client.post(
        "/ai/integrity/check",
        json={"evaluation_id": evaluation_id, "answer_id": answer_id},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 422


async def test_integrity_disabled_for_group_blocks_check(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    evaluation_id, answer_id = await _setup_live_code_evaluation(
        client, teacher_access, student_access
    )

    groups = await client.get("/groups/mine", headers=auth_headers(teacher_access))
    group_id = groups.json()[0]["id"]
    await client.put(
        f"/ai/groups/{group_id}/agents/code_integrity",
        json={"enabled": False},
        headers=auth_headers(teacher_access),
    )

    called = False

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        nonlocal called
        called = True
        return CompletionResult(text="{}", model="x", prompt_tokens=0, completion_tokens=0)

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    resp = await client.post(
        "/ai/integrity/check",
        json={"evaluation_id": evaluation_id, "answer_id": answer_id},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 403
    assert called is False
