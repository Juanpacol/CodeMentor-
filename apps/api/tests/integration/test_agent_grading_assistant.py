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


async def _setup_argued_evaluation(
    client: AsyncClient, teacher_access: str, student_access: str
) -> tuple[str, str, str]:
    """Returns (evaluation_id, answer_id, group_invite_code) with a submitted
    argued_response answer awaiting manual review."""
    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(
        client,
        teacher_access,
        language_id,
        exercise_type="argued_response",
        content={"prompt": "Explica por qué usarías un ciclo Mientras"},
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
    await client.post(f"/evaluations/{evaluation_id}/submit", headers=auth_headers(student_access))

    queue = await client.get(
        f"/evaluations/{evaluation_id}/manual-review", headers=auth_headers(teacher_access)
    )
    answer_id = queue.json()[0]["answer_id"]

    return evaluation_id, answer_id, group["id"]


async def test_suggestion_never_touches_score_directly(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    evaluation_id, answer_id, _group_id = await _setup_argued_evaluation(
        client, teacher_access, student_access
    )

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(
            text='{"suggested_score": 0.75, "justification": "Explica el criterio correctamente"}',
            model="groq/fake",
            prompt_tokens=1,
            completion_tokens=1,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    resp = await client.post(
        "/ai/grading/suggest",
        json={
            "evaluation_id": evaluation_id,
            "answer_id": answer_id,
            "rubric": "1 punto si explica correctamente por qué usar Mientras",
        },
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_suggested_score"] == 0.75

    # The student's actual result is unaffected until the teacher confirms.
    result = await client.get(
        f"/evaluations/{evaluation_id}/result", headers=auth_headers(student_access)
    )
    assert result.json()["total_score"] == 0.0
    assert result.json()["answers"][0]["manual_score"] is None


async def test_suggestion_appears_in_pending_approvals_until_confirmed(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    evaluation_id, answer_id, _group_id = await _setup_argued_evaluation(
        client, teacher_access, student_access
    )

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(
            text='{"suggested_score": 0.6, "justification": "Parcialmente correcto"}',
            model="groq/fake",
            prompt_tokens=1,
            completion_tokens=1,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    await client.post(
        "/ai/grading/suggest",
        json={"evaluation_id": evaluation_id, "answer_id": answer_id, "rubric": "rúbrica"},
        headers=auth_headers(teacher_access),
    )

    pending = await client.get("/ai/pending-approvals", headers=auth_headers(teacher_access))
    suggestions = pending.json()["grading_suggestions"]
    assert any(s["answer_id"] == answer_id for s in suggestions)

    confirmed = await client.post(
        f"/evaluations/{evaluation_id}/manual-review/{answer_id}",
        json={"score": 0.6},
        headers=auth_headers(teacher_access),
    )
    assert confirmed.status_code == 200

    pending_after = await client.get("/ai/pending-approvals", headers=auth_headers(teacher_access))
    suggestions_after = pending_after.json()["grading_suggestions"]
    assert all(s["answer_id"] != answer_id for s in suggestions_after)

    result = await client.get(
        f"/evaluations/{evaluation_id}/result", headers=auth_headers(student_access)
    )
    assert result.json()["total_score"] == 0.6


async def test_grading_assistant_disabled_blocks_suggestion(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    evaluation_id, answer_id, group_id = await _setup_argued_evaluation(
        client, teacher_access, student_access
    )

    await client.put(
        f"/ai/groups/{group_id}/agents/grading_suggestion",
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
        "/ai/grading/suggest",
        json={"evaluation_id": evaluation_id, "answer_id": answer_id, "rubric": "rúbrica"},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 403
    assert called is False
