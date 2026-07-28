"""Ejercicios generados a partir de una guía (Fase 17).

El camino independiente de la rúbrica: un docente que ya tiene una guía pide
ejercicios para ella. Lo que se protege es el aislamiento por ítem —que un tipo
que el modelo no sepa producir no se lleve los otros— y los dos ejes de
organización del dashboard (`guide_id` y `topic_exercises`).
"""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from logica.ai.agents.exercise_generator import generate_exercises_for_guide
from logica.ai.harness.router import CompletionResult
from logica.core.arq_dep import get_arq_pool
from logica.db import get_session_factory
from logica.modules.content.models import TopicLevel
from logica.modules.exercises.models import Exercise, ExerciseOrigin, ExerciseStatus, TopicExercise
from logica.modules.guides.models import (
    Guide,
    GuideOrigin,
    GuidesFolder,
    GuideStatus,
    GuideTemplate,
)
from logica.modules.users.models import Institution, User
from tests.integration.conftest import (
    auth_headers,
    create_group,
    create_language,
    create_topic,
    get_user_by_email,
    register_and_login,
)

_GUIDE_MD = (
    "## Cuándo usar Mientras\n\n"
    "Se usa cuando no se sabe de antemano cuántas repeticiones hacen falta. "
    "La condición se evalúa antes de cada vuelta."
)


class _FakeArqPool:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, name: str, *args: Any) -> None:
        self.jobs.append((name, args))


async def _setup(client: AsyncClient, institution: Institution) -> dict[str, Any]:
    domain = institution.email_domains[0]
    access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    teacher = await get_user_by_email(f"doc@{domain}")
    language_id = await create_language(client, access)
    group = await create_group(client, access)
    topic_id = await create_topic(client, access, language_id, name="Ciclos mientras")

    session_factory = get_session_factory()
    async with session_factory() as db:
        template = GuideTemplate(
            institution_id=institution.id,
            created_by_id=teacher.id,
            name="Guía de laboratorio",
            sections=[{"heading": "Objetivos", "instructions": "Lista 3 objetivos."}],
            tone="cercano",
            target_level=TopicLevel.basico,
            version=1,
        )
        folder = GuidesFolder(
            institution_id=institution.id,
            group_id=uuid.UUID(group["id"]),
            created_by_id=teacher.id,
            name="Guías 10-A",
        )
        db.add_all([template, folder])
        await db.flush()
        guide = Guide(
            institution_id=institution.id,
            folder_id=folder.id,
            template_id=template.id,
            topic_id=uuid.UUID(topic_id),
            created_by_id=teacher.id,
            title="Ciclos mientras",
            content_md=_GUIDE_MD,
            origin=GuideOrigin.ai,
            status=GuideStatus.draft,
        )
        db.add(guide)
        await db.commit()
        guide_id = guide.id

    return {"access": access, "teacher_id": teacher.id, "guide_id": guide_id, "group": group}


async def _run(ctx: dict[str, Any], redis_client: Any, types: list[str]) -> list[Exercise]:
    session_factory = get_session_factory()
    async with session_factory() as db:
        teacher = await db.get(User, ctx["teacher_id"])
        assert teacher is not None
        from logica.modules.exercises.models import ExerciseType

        created = await generate_exercises_for_guide(
            db,
            redis_client,
            teacher,
            guide_id=ctx["guide_id"],
            exercise_types=[ExerciseType(t) for t in types],
        )
        await db.commit()
        return created


async def test_encola_el_job_y_responde_202(client: AsyncClient, institution: Institution) -> None:
    ctx = await _setup(client, institution)
    pool = _FakeArqPool()
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_arq_pool] = lambda: pool
    try:
        response = await client.post(
            f"/ai/guides/{ctx['guide_id']}/exercises",
            json={"exercise_types": ["true_false", "multiple_choice"]},
            headers=auth_headers(ctx["access"]),
        )
    finally:
        app.dependency_overrides.pop(get_arq_pool, None)

    assert response.status_code == 202
    assert pool.jobs == [
        (
            "generate_exercises_for_guide_job",
            (str(ctx["guide_id"]), ["true_false", "multiple_choice"]),
        )
    ]


async def test_un_docente_ajeno_recibe_403_sin_encolar(
    client: AsyncClient, institution: Institution
) -> None:
    # Validar el acceso en el endpoint y no solo en el worker: si no, el docente
    # ajeno recibe un 202 y el job muere en silencio en el worker.
    ctx = await _setup(client, institution)
    domain = institution.email_domains[0]
    otro, _ = await register_and_login(client, email=f"otra@{domain}", role="teacher")

    pool = _FakeArqPool()
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_arq_pool] = lambda: pool
    try:
        response = await client.post(
            f"/ai/guides/{ctx['guide_id']}/exercises",
            json={"exercise_types": ["true_false"]},
            headers=auth_headers(otro),
        )
    finally:
        app.dependency_overrides.pop(get_arq_pool, None)

    assert response.status_code == 403
    assert pool.jobs == []


async def test_los_ejercicios_quedan_ligados_a_la_guia_y_al_tema(
    client: AsyncClient,
    institution: Institution,
    redis_client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        # El prompt v2 debe llevar el texto de la guía: es lo que hace que el
        # ejercicio evalúe lo que la guía explicó y no el tema en general.
        assert "no se sabe de antemano" in messages[-1]["content"]
        return CompletionResult(
            text='{"title": "Cuerpo del Mientras", "content": {"statement": "¿Siempre corre?", '
            '"answer": false}}',
            model="groq/fake",
            prompt_tokens=1,
            completion_tokens=1,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)
    ctx = await _setup(client, institution)
    created = await _run(ctx, redis_client, ["true_false"])

    assert len(created) == 1
    session_factory = get_session_factory()
    async with session_factory() as db:
        exercises = (await db.execute(select(Exercise))).scalars().all()
        links = (await db.execute(select(TopicExercise))).scalars().all()

    assert len(exercises) == 1
    assert exercises[0].guide_id == ctx["guide_id"]
    assert exercises[0].origin == ExerciseOrigin.ai
    # §9.2: borrador, nunca publicado por la plataforma.
    assert exercises[0].status == ExerciseStatus.draft
    # Y sigue apareciendo al filtrar el banco por tema.
    assert len(links) == 1


async def test_un_tipo_que_falla_no_se_lleva_los_demas(
    client: AsyncClient,
    institution: Institution,
    redis_client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        # Se discrimina por tipo y no por número de llamada: `complete_structured`
        # reintenta hasta 2 veces, así que fallar solo la primera llamada dejaría
        # que el reintento acierte y el tipo "roto" también se crearía.
        if 'de tipo "multiple_choice"' in messages[-1]["content"]:
            # JSON irreparable en los 3 intentos: levanta StructuredOutputError
            # para ESTE tipo solamente.
            return CompletionResult(
                text="no es json", model="groq/fake", prompt_tokens=1, completion_tokens=1
            )
        return CompletionResult(
            text='{"title": "Cuerpo del Mientras", "content": {"statement": "¿Siempre corre?", '
            '"answer": false}}',
            model="groq/fake",
            prompt_tokens=1,
            completion_tokens=1,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)
    ctx = await _setup(client, institution)
    created = await _run(ctx, redis_client, ["multiple_choice", "true_false"])

    # Dos de tres sirven y cero no: el primer tipo se pierde, el segundo entra.
    assert len(created) == 1
    assert created[0].type.value == "true_false"
