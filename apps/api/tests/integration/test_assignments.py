"""Tests de asignaciones con fecha límite.

Lo que se protege es el contrato del panel del estudiante:

1. "Cumplida" se DERIVA de sus envíos correctos, no se guarda — así que resolver
   el ejercicio tiene que mover el estado sin ningún endpoint extra.
2. El invariante tema-XOR-ejercicio se rechaza con 422 explicativo, no con el
   error de integridad crudo de Postgres.
3. Multi-tenencia y autorización: un docente ajeno no asigna sobre este grupo, y
   un estudiante solo ve lo de los grupos donde está matriculado.
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from logica.modules.users.models import Institution
from tests.integration.conftest import (
    auth_headers,
    create_exercise,
    create_group,
    create_language,
    create_topic,
    enable_topic,
    join_group,
    register_and_login,
)


async def _setup(client: AsyncClient, institution: Institution) -> dict[str, str]:
    domain = institution.email_domains[0]
    teacher, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    language_id = await create_language(client, teacher)
    topic_id = await create_topic(client, teacher, language_id)
    group = await create_group(client, teacher)
    await join_group(client, student, group["invite_code"])
    exercise = await create_exercise(client, teacher, language_id)

    # Practicar exige que el ejercicio cuelgue de un tema habilitado para el
    # grupo; sin esto `/practice/{id}/submit` responde 403 y la asignación nunca
    # podría cumplirse.
    attached = await client.post(
        f"/exercises/{exercise['id']}/topics/{topic_id}",
        headers=auth_headers(teacher),
    )
    assert attached.status_code == 201, attached.text
    await enable_topic(client, teacher, group["id"], topic_id)

    return {
        "teacher": teacher,
        "student": student,
        "group_id": group["id"],
        "topic_id": topic_id,
        "exercise_id": exercise["id"],
        "language_id": language_id,
    }


async def test_asignar_un_ejercicio_aparece_como_pendiente_del_estudiante(
    client: AsyncClient, institution: Institution
) -> None:
    ctx = await _setup(client, institution)
    vence = (datetime.now(UTC) + timedelta(days=3)).isoformat()

    created = await client.post(
        f"/groups/{ctx['group_id']}/assignments",
        json={"title": "Taller de ciclos", "exercise_id": ctx["exercise_id"], "due_at": vence},
        headers=auth_headers(ctx["teacher"]),
    )
    assert created.status_code == 201, created.text

    mine = await client.get("/assignments/me", headers=auth_headers(ctx["student"]))
    assert mine.status_code == 200, mine.text
    body = mine.json()
    assert len(body) == 1
    assert body[0]["title"] == "Taller de ciclos"
    assert body[0]["group_name"] == "10-1"
    assert body[0]["done"] is False
    assert body[0]["total_exercises"] == 1
    assert body[0]["solved_exercises"] == 0


async def test_resolver_bien_el_ejercicio_marca_la_asignacion_cumplida(
    client: AsyncClient, institution: Institution
) -> None:
    """El estado se deriva de los envíos: sin esto habría que mantener una
    columna `done` sincronizada con cada envío de práctica."""
    ctx = await _setup(client, institution)
    await client.post(
        f"/groups/{ctx['group_id']}/assignments",
        json={"title": "Taller de ciclos", "exercise_id": ctx["exercise_id"]},
        headers=auth_headers(ctx["teacher"]),
    )

    resuelto = await client.post(
        f"/practice/{ctx['exercise_id']}/submit",
        json={"group_id": ctx["group_id"], "answer": {"value": True}},
        headers=auth_headers(ctx["student"]),
    )
    assert resuelto.status_code == 200, resuelto.text
    assert resuelto.json()["correct"] is True, resuelto.text

    body = (await client.get("/assignments/me", headers=auth_headers(ctx["student"]))).json()
    assert body[0]["done"] is True
    assert body[0]["solved_exercises"] == 1


async def test_un_tema_sin_ejercicios_no_cuenta_como_cumplido(
    client: AsyncClient, institution: Institution
) -> None:
    """Decir "cumplida" porque no hay nada que resolver le esconde al estudiante
    que el docente asignó algo que todavía no tiene contenido."""
    ctx = await _setup(client, institution)
    # Un tema aparte: el del setup ya tiene un ejercicio asociado.
    vacio = await create_topic(
        client, ctx["teacher"], ctx["language_id"], name="Recursión", order_index=2
    )
    await client.post(
        f"/groups/{ctx['group_id']}/assignments",
        json={"title": "Tema de recursión", "topic_id": vacio},
        headers=auth_headers(ctx["teacher"]),
    )

    body = (await client.get("/assignments/me", headers=auth_headers(ctx["student"]))).json()
    assert len(body) == 1
    assert body[0]["total_exercises"] == 0
    assert body[0]["done"] is False


async def test_rechaza_asignar_tema_y_ejercicio_a_la_vez(
    client: AsyncClient, institution: Institution
) -> None:
    ctx = await _setup(client, institution)
    resp = await client.post(
        f"/groups/{ctx['group_id']}/assignments",
        json={
            "title": "Ambos",
            "topic_id": ctx["topic_id"],
            "exercise_id": ctx["exercise_id"],
        },
        headers=auth_headers(ctx["teacher"]),
    )
    assert resp.status_code == 422

    ninguno = await client.post(
        f"/groups/{ctx['group_id']}/assignments",
        json={"title": "Ninguno"},
        headers=auth_headers(ctx["teacher"]),
    )
    assert ninguno.status_code == 422


async def test_un_docente_ajeno_no_puede_asignar_sobre_este_grupo(
    client: AsyncClient, institution: Institution
) -> None:
    ctx = await _setup(client, institution)
    domain = institution.email_domains[0]
    otro, _ = await register_and_login(client, email=f"otro@{domain}", role="teacher")

    resp = await client.post(
        f"/groups/{ctx['group_id']}/assignments",
        json={"title": "Intruso", "exercise_id": ctx["exercise_id"]},
        headers=auth_headers(otro),
    )
    assert resp.status_code == 403


async def test_el_estudiante_solo_ve_asignaciones_de_sus_grupos(
    client: AsyncClient, institution: Institution
) -> None:
    ctx = await _setup(client, institution)
    # Un segundo grupo del mismo docente, donde el estudiante NO está matriculado.
    otro_grupo = await create_group(client, ctx["teacher"], name="11-2")
    await client.post(
        f"/groups/{otro_grupo['id']}/assignments",
        json={"title": "De otro curso", "exercise_id": ctx["exercise_id"]},
        headers=auth_headers(ctx["teacher"]),
    )

    body = (await client.get("/assignments/me", headers=auth_headers(ctx["student"]))).json()
    assert body == []


async def test_asignar_un_examen_se_cumple_al_presentarlo(
    client: AsyncClient, institution: Institution
) -> None:
    ctx = await _setup(client, institution)
    evaluation = await client.post(
        "/evaluations",
        json={
            "group_id": ctx["group_id"],
            "title": "Parcial 1",
            "mode": "cumulative",
            "is_ranked": False,
            "exercise_ids": [ctx["exercise_id"]],
        },
        headers=auth_headers(ctx["teacher"]),
    )
    assert evaluation.status_code == 201, evaluation.text
    evaluation_id = evaluation.json()["id"]

    created = await client.post(
        f"/groups/{ctx['group_id']}/assignments",
        json={"title": "Presenta el parcial", "evaluation_id": evaluation_id},
        headers=auth_headers(ctx["teacher"]),
    )
    assert created.status_code == 201, created.text

    before = (await client.get("/assignments/me", headers=auth_headers(ctx["student"]))).json()
    assert before[0]["done"] is False

    take = await client.get(
        f"/evaluations/{evaluation_id}/take", headers=auth_headers(ctx["student"])
    )
    evaluation_exercise_id = take.json()["exercises"][0]["evaluation_exercise_id"]
    await client.post(
        f"/evaluations/{evaluation_id}/answers",
        json={"evaluation_exercise_id": evaluation_exercise_id, "answer": {"value": True}},
        headers=auth_headers(ctx["student"]),
    )
    submitted = await client.post(
        f"/evaluations/{evaluation_id}/submit", headers=auth_headers(ctx["student"])
    )
    assert submitted.status_code == 200, submitted.text

    after = (await client.get("/assignments/me", headers=auth_headers(ctx["student"]))).json()
    assert after[0]["done"] is True
    assert after[0]["evaluation_id"] == evaluation_id


async def test_asignar_un_taller_nunca_se_marca_cumplido_todavia(
    client: AsyncClient, institution: Institution
) -> None:
    """No hay señal de "lo leyó" en la plataforma — ver el docstring del
    modelo. Esto documenta el límite actual, no un objetivo."""
    ctx = await _setup(client, institution)

    folder = await client.post(
        f"/groups/{ctx['group_id']}/guide-folders",
        json={"name": "Guías 10-1"},
        headers=auth_headers(ctx["teacher"]),
    )
    template = await client.post(
        "/guide-templates",
        json={
            "name": "Guía de laboratorio",
            "sections": [{"heading": "Objetivos", "instructions": "Lista 3 objetivos."}],
            "tone": "cercano",
            "target_level": "basico",
        },
        headers=auth_headers(ctx["teacher"]),
    )
    guide = await client.post(
        "/ai/guides/generate",
        json={
            "folder_id": folder.json()["id"],
            "template_id": template.json()["id"],
            "topic_id": ctx["topic_id"],
        },
        headers=auth_headers(ctx["teacher"]),
    )
    assert guide.status_code == 202, guide.text
    guide_id = guide.json()["id"]

    created = await client.post(
        f"/groups/{ctx['group_id']}/assignments",
        json={"title": "Lee la guía", "guide_id": guide_id},
        headers=auth_headers(ctx["teacher"]),
    )
    assert created.status_code == 201, created.text

    body = (await client.get("/assignments/me", headers=auth_headers(ctx["student"]))).json()
    assert body[0]["done"] is False
    assert body[0]["guide_id"] == guide_id
    assert body[0]["total_exercises"] == 0


async def test_quitar_la_fecha_limite_es_posible(
    client: AsyncClient, institution: Institution
) -> None:
    """`due_at=None` en el PATCH tiene que borrar la fecha, no ignorarse: si no,
    una fecha puesta por error sería imposible de deshacer."""
    ctx = await _setup(client, institution)
    vence = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    created = (
        await client.post(
            f"/groups/{ctx['group_id']}/assignments",
            json={"title": "Con fecha", "exercise_id": ctx["exercise_id"], "due_at": vence},
            headers=auth_headers(ctx["teacher"]),
        )
    ).json()
    assert created["due_at"] is not None

    updated = await client.patch(
        f"/assignments/{created['id']}",
        json={"due_at": None},
        headers=auth_headers(ctx["teacher"]),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["due_at"] is None
