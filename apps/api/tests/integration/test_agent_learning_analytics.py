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


async def test_student_cannot_request_group_summary(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")
    group = await create_group(client, teacher_access)

    resp = await client.post(
        f"/ai/groups/{group['id']}/analytics/summary", headers=auth_headers(student_access)
    )
    assert resp.status_code == 403


async def test_summary_reflects_practice_activity(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
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

    for value in (True, False, True):
        await client.post(
            f"/practice/{exercise['id']}/submit",
            json={"group_id": group["id"], "answer": {"value": value}},
            headers=auth_headers(student_access),
        )

    captured_vars: dict = {}

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        captured_vars["prompt"] = messages[0]["content"]
        return CompletionResult(
            text="El grupo va bien en general; reforzar el tipo true_false.",
            model="groq/fake",
            prompt_tokens=1,
            completion_tokens=1,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    resp = await client.post(
        f"/ai/groups/{group['id']}/analytics/summary", headers=auth_headers(teacher_access)
    )
    assert resp.status_code == 200
    assert "reforzar" in resp.json()["summary"]
    assert '"total_submissions": 3' in captured_vars["prompt"]


async def test_learning_analytics_disabled_blocks_summary(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    group = await create_group(client, teacher_access)

    await client.put(
        f"/ai/groups/{group['id']}/agents/summarize_group",
        json={"enabled": False},
        headers=auth_headers(teacher_access),
    )

    called = False

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        nonlocal called
        called = True
        return CompletionResult(text="x", model="x", prompt_tokens=0, completion_tokens=0)

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    resp = await client.post(
        f"/ai/groups/{group['id']}/analytics/summary", headers=auth_headers(teacher_access)
    )
    assert resp.status_code == 403
    assert called is False
