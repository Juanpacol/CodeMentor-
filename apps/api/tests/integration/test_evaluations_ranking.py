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


async def test_ranking_reflects_submitted_scores_descending(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    winner_access, _ = await register_and_login(client, email=f"ganador@{domain}", role="student")
    loser_access, _ = await register_and_login(client, email=f"perdedor@{domain}", role="student")

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
            "title": "Competencia",
            "mode": "cumulative",
            "is_ranked": True,
            "exercise_ids": [exercise["id"]],
        },
        headers=auth_headers(teacher_access),
    )
    evaluation_id = created.json()["id"]

    await join_group(client, winner_access, group["invite_code"])
    await join_group(client, loser_access, group["invite_code"])

    for access, value in ((winner_access, True), (loser_access, False)):
        take = await client.get(f"/evaluations/{evaluation_id}/take", headers=auth_headers(access))
        eval_exercise_id = take.json()["exercises"][0]["evaluation_exercise_id"]
        await client.post(
            f"/evaluations/{evaluation_id}/answers",
            json={"evaluation_exercise_id": eval_exercise_id, "answer": {"value": value}},
            headers=auth_headers(access),
        )
        await client.post(f"/evaluations/{evaluation_id}/submit", headers=auth_headers(access))

    ranking = await client.get(
        f"/evaluations/{evaluation_id}/ranking", headers=auth_headers(teacher_access)
    )
    assert ranking.status_code == 200
    entries = ranking.json()
    assert len(entries) == 2
    assert entries[0]["total_score"] == 1.0
    assert entries[1]["total_score"] == 0.0
