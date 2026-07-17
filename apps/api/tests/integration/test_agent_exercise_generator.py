import pytest
from httpx import AsyncClient

from logica.ai.harness.router import CompletionResult
from logica.modules.users.models import Institution
from tests.integration.conftest import (
    auth_headers,
    create_group,
    create_language,
    create_topic,
    register_and_login,
)


async def test_student_cannot_generate_exercise(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = await create_group(client, teacher_access)

    resp = await client.post(
        "/ai/exercises/generate",
        json={"group_id": group["id"], "topic_id": topic_id, "exercise_type": "true_false"},
        headers=auth_headers(student_access),
    )
    assert resp.status_code == 403


async def test_generated_exercise_is_draft_and_ai_origin(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = await create_group(client, teacher_access)

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(
            text='{"title": "Verdadero o falso sobre ciclos", '
            '"content": {"statement": "Un ciclo Mientras evalúa antes", "answer": true}}',
            model="groq/fake",
            prompt_tokens=10,
            completion_tokens=10,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    resp = await client.post(
        "/ai/exercises/generate",
        json={"group_id": group["id"], "topic_id": topic_id, "exercise_type": "true_false"},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    assert body["origin"] == "ai"
    assert body["title"] == "Verdadero o falso sobre ciclos"
    assert body["content"]["answer"] is True


async def test_generator_disabled_for_group_blocks_generation(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = await create_group(client, teacher_access)

    await client.put(
        f"/ai/groups/{group['id']}/agents/exercise_generation",
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
        "/ai/exercises/generate",
        json={"group_id": group["id"], "topic_id": topic_id, "exercise_type": "true_false"},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 403
    assert called is False


async def test_generated_draft_becomes_visible_only_after_teacher_publishes(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = await create_group(client, teacher_access)

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(
            text='{"title": "Generado", "content": {"statement": "x", "answer": true}}',
            model="groq/fake",
            prompt_tokens=1,
            completion_tokens=1,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    created = await client.post(
        "/ai/exercises/generate",
        json={"group_id": group["id"], "topic_id": topic_id, "exercise_type": "true_false"},
        headers=auth_headers(teacher_access),
    )
    exercise_id = created.json()["id"]

    pending = await client.get("/ai/pending-approvals", headers=auth_headers(teacher_access))
    assert any(e["id"] == exercise_id for e in pending.json()["exercises"])

    published = await client.patch(
        f"/exercises/{exercise_id}",
        json={"status": "published"},
        headers=auth_headers(teacher_access),
    )
    assert published.json()["status"] == "published"

    pending_after = await client.get("/ai/pending-approvals", headers=auth_headers(teacher_access))
    assert all(e["id"] != exercise_id for e in pending_after.json()["exercises"])
