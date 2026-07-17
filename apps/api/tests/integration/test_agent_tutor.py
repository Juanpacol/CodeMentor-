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


async def _fake_router_complete(text: str) -> CompletionResult:
    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(text=text, model="groq/fake", prompt_tokens=5, completion_tokens=5)

    return fake


async def _setup_group_with_exercise(client: AsyncClient, teacher_access: str) -> tuple[dict, str]:
    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    exercise = await create_exercise(
        client, teacher_access, language_id, content={"statement": "¿Qué hace un ciclo Mientras?"}
    )
    await attach_exercise(client, teacher_access, exercise["id"], topic_id)
    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_id)
    return group, exercise["id"]


async def test_student_gets_hint_and_history_is_persisted(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    group, exercise_id = await _setup_group_with_exercise(client, teacher_access)
    await join_group(client, student_access, group["invite_code"])

    fake = await _fake_router_complete("Piensa en qué se repite dentro del ciclo.")
    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    resp = await client.post(
        "/ai/tutor/hint",
        json={
            "group_id": group["id"],
            "exercise_id": exercise_id,
            "attempt_number": 1,
            "student_answer": "no tengo idea",
        },
        headers=auth_headers(student_access),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "tutor"
    assert body["content"] == "Piensa en qué se repite dentro del ciclo."

    history = await client.get(
        "/ai/tutor/history",
        params={"group_id": group["id"], "exercise_id": exercise_id},
        headers=auth_headers(student_access),
    )
    assert history.status_code == 200
    roles = [m["role"] for m in history.json()]
    assert roles == ["student", "tutor"]


async def test_tutor_never_reveals_full_solution(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    group, exercise_id = await _setup_group_with_exercise(client, teacher_access)
    await join_group(client, student_access, group["invite_code"])

    fake = await _fake_router_complete("La respuesta correcta es usar un ciclo Mientras.")
    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    resp = await client.post(
        "/ai/tutor/hint",
        json={
            "group_id": group["id"],
            "exercise_id": exercise_id,
            "attempt_number": 1,
            "student_answer": "dame la respuesta",
        },
        headers=auth_headers(student_access),
    )
    # OutputBlockedByGuardrailError is a ValidationDomainError (422), not a
    # PermissionDeniedError (403) — the model answered, but the harness's
    # output guardrail rejected the full-solution leak (RF-31).
    assert resp.status_code == 422


async def test_tutor_disabled_for_group_blocks_hint(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    group, exercise_id = await _setup_group_with_exercise(client, teacher_access)
    await join_group(client, student_access, group["invite_code"])

    await client.put(
        f"/ai/groups/{group['id']}/agents/progressive_hint",
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
        "/ai/tutor/hint",
        json={
            "group_id": group["id"],
            "exercise_id": exercise_id,
            "attempt_number": 1,
            "student_answer": "ayuda",
        },
        headers=auth_headers(student_access),
    )
    assert resp.status_code == 403
    assert called is False


async def test_student_cannot_see_another_students_history(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_a, _ = await register_and_login(client, email=f"est-a@{domain}", role="student")
    student_b, _ = await register_and_login(client, email=f"est-b@{domain}", role="student")

    group, exercise_id = await _setup_group_with_exercise(client, teacher_access)
    await join_group(client, student_a, group["invite_code"])
    await join_group(client, student_b, group["invite_code"])

    fake = await _fake_router_complete("pista")
    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    await client.post(
        "/ai/tutor/hint",
        json={
            "group_id": group["id"],
            "exercise_id": exercise_id,
            "attempt_number": 1,
            "student_answer": "ayuda",
        },
        headers=auth_headers(student_a),
    )

    resp = await client.get(
        "/ai/tutor/history",
        params={"group_id": group["id"], "exercise_id": exercise_id},
        headers=auth_headers(student_b),
    )
    assert resp.json() == []


async def test_teacher_can_view_specific_students_history(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    group, exercise_id = await _setup_group_with_exercise(client, teacher_access)
    await join_group(client, student_access, group["invite_code"])

    fake = await _fake_router_complete("pista")
    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    await client.post(
        "/ai/tutor/hint",
        json={
            "group_id": group["id"],
            "exercise_id": exercise_id,
            "attempt_number": 1,
            "student_answer": "ayuda",
        },
        headers=auth_headers(student_access),
    )

    from tests.integration.conftest import get_user_by_email

    student = await get_user_by_email(f"est@{domain}")

    resp = await client.get(
        "/ai/tutor/history",
        params={"group_id": group["id"], "exercise_id": exercise_id, "student_id": str(student.id)},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2
