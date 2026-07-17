from datetime import date, timedelta

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


async def _submit_practice(
    client: AsyncClient, student_access: str, exercise_id: str, group_id: str, *, value: bool
) -> None:
    resp = await client.post(
        f"/practice/{exercise_id}/submit",
        json={"group_id": group_id, "answer": {"value": value}},
        headers=auth_headers(student_access),
    )
    assert resp.status_code == 200, resp.text


async def test_progress_starts_empty(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    resp = await client.get("/progress/me", headers=auth_headers(student_access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["points"] == 0
    assert body["badges"] == []
    assert body["mastery_by_topic"] == []
    assert body["mastery_by_language"] == []


async def test_correct_practice_awards_points_and_topic_language_badges(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = await create_group(client, teacher_access)
    await join_group(client, student_access, group["invite_code"])
    await enable_topic(client, teacher_access, group["id"], topic_id)

    # 5 correct submissions across 5 distinct exercises on the same topic —
    # crosses both the topic-mastery and language-mastery thresholds (§80%
    # accuracy, >=5 submissions) at once.
    for i in range(5):
        exercise = await create_exercise(
            client, teacher_access, language_id, title=f"Ejercicio {i}"
        )
        await attach_exercise(client, teacher_access, exercise["id"], topic_id)
        await _submit_practice(client, student_access, exercise["id"], group["id"], value=True)

    resp = await client.get("/progress/me", headers=auth_headers(student_access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["points"] == 5

    badge_slugs = {b["slug"] for b in body["badges"]}
    assert "dominando-tema" in badge_slugs
    assert "dominando-lenguaje" in badge_slugs
    assert "racha-de-aciertos" in badge_slugs

    topic_mastery = body["mastery_by_topic"]
    assert len(topic_mastery) == 1
    assert topic_mastery[0]["submissions"] == 5
    assert topic_mastery[0]["accuracy"] == 1.0

    language_mastery = body["mastery_by_language"]
    assert len(language_mastery) == 1
    assert language_mastery[0]["accuracy"] == 1.0


async def test_incorrect_practice_never_awards_mastery_badge(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = await create_group(client, teacher_access)
    await join_group(client, student_access, group["invite_code"])
    await enable_topic(client, teacher_access, group["id"], topic_id)

    for i in range(5):
        exercise = await create_exercise(
            client, teacher_access, language_id, title=f"Ejercicio {i}"
        )
        await attach_exercise(client, teacher_access, exercise["id"], topic_id)
        await _submit_practice(client, student_access, exercise["id"], group["id"], value=False)

    resp = await client.get("/progress/me", headers=auth_headers(student_access))
    body = resp.json()
    assert body["points"] == 0
    assert body["badges"] == []


async def test_badge_is_not_awarded_twice(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = await create_group(client, teacher_access)
    await join_group(client, student_access, group["invite_code"])
    await enable_topic(client, teacher_access, group["id"], topic_id)

    exercises = []
    for i in range(6):
        exercise = await create_exercise(
            client, teacher_access, language_id, title=f"Ejercicio {i}"
        )
        await attach_exercise(client, teacher_access, exercise["id"], topic_id)
        exercises.append(exercise)
        await _submit_practice(client, student_access, exercise["id"], group["id"], value=True)

    resp = await client.get("/progress/me", headers=auth_headers(student_access))
    badge_slugs = [b["slug"] for b in resp.json()["badges"]]
    assert badge_slugs.count("dominando-tema") == 1
    assert badge_slugs.count("racha-de-aciertos") == 1


async def test_lagging_students_flags_low_accuracy(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = await create_group(client, teacher_access)
    await join_group(client, student_access, group["invite_code"])
    await enable_topic(client, teacher_access, group["id"], topic_id)

    for i in range(4):
        exercise = await create_exercise(
            client, teacher_access, language_id, title=f"Ejercicio {i}"
        )
        await attach_exercise(client, teacher_access, exercise["id"], topic_id)
        await _submit_practice(client, student_access, exercise["id"], group["id"], value=False)

    resp = await client.get(
        f"/groups/{group['id']}/progress/lagging", headers=auth_headers(teacher_access)
    )
    assert resp.status_code == 200
    lagging = resp.json()
    assert len(lagging) == 1
    assert lagging[0]["reason"].startswith("Precisión")


async def test_lagging_students_forbidden_for_students(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")
    group = await create_group(client, teacher_access)
    await join_group(client, student_access, group["invite_code"])

    resp = await client.get(
        f"/groups/{group['id']}/progress/lagging", headers=auth_headers(student_access)
    )
    assert resp.status_code == 403


async def test_academic_period_create_and_list(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    today = date.today()
    resp = await client.post(
        "/academic-periods",
        json={
            "name": "Periodo 1 - 2026",
            "start_date": str(today - timedelta(days=30)),
            "end_date": str(today + timedelta(days=30)),
        },
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 201, resp.text
    period = resp.json()
    assert period["name"] == "Periodo 1 - 2026"

    listed = await client.get("/academic-periods", headers=auth_headers(student_access))
    assert listed.status_code == 200
    assert any(p["id"] == period["id"] for p in listed.json())


async def test_academic_period_create_forbidden_for_students(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    resp = await client.post(
        "/academic-periods",
        json={"name": "Periodo X", "start_date": "2026-01-01", "end_date": "2026-06-30"},
        headers=auth_headers(student_access),
    )
    assert resp.status_code == 403
