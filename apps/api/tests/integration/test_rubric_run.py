"""Tests de la corrida de rúbrica (Fase 17).

Lo que se protege acá es el contrato de la automatización, no la calidad del
texto (eso es `test_agent_guide_writer.py` y las evals):

1. §9.2 — la plataforma NUNCA publica contenido de IA sola. Una rúbrica que
   dejara guías publicadas sería la regresión más grave posible de esta fase.
2. El fallo parcial es el caso común bajo el tier gratuito de Groq, no una
   excepción: 8 de 10 temas debe reportarse como `partial`, no como éxito.
3. Que un fallo de una etapa no barra con las anteriores (el tema sin material
   igual recibe su guía).
"""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from logica.ai.harness.router import CompletionResult
from logica.core.arq_dep import get_arq_pool
from logica.core.errors import ConflictError
from logica.db import get_session_factory
from logica.modules.content.models import (
    Topic,
    TopicGroupState,
    TopicGroupStateValue,
    TopicLevel,
)
from logica.modules.exercises.models import Exercise, ExerciseStatus, TopicExercise
from logica.modules.guides.models import Guide, GuideStatus, GuideTemplate
from logica.modules.rubrics.models import RubricItemStatus, RubricRunStatus
from logica.modules.rubrics.runner import run_rubric
from logica.modules.users.models import Institution
from tests.integration.conftest import (
    auth_headers,
    create_group,
    create_language,
    get_user_by_email,
    register_and_login,
)

_GUIDE_JSON = (
    '{"heading": "Objetivos", "body_md": "Al terminar esta guía reconocerás una '
    'estructura condicional y sabrás escribirla en pseudocódigo sin ayuda."}'
)
_EXERCISE_JSON = (
    '{"title": "Condicional simple", "content": {"statement": "¿Un Si-Entonces '
    'siempre necesita SiNo?", "answer": false}}'
)

_WIKI_EXTRACT = (
    "Una estructura condicional permite ejecutar instrucciones distintas según una "
    "condición lógica. Es una de las tres estructuras de control básicas.\n\n"
    "En pseudocódigo se escribe Si-Entonces-SiNo-FinSi. Las estructuras "
    "condicionales pueden anidarse para representar decisiones compuestas, aunque "
    "un anidamiento profundo suele indicar que conviene reescribir la lógica.\n\n"
    "La selección múltiple es útil cuando se compara una variable contra muchos "
    "valores posibles distintos."
)


class _FakeArqPool:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, name: str, *args: Any) -> None:
        self.jobs.append((name, args))


def _stub_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un solo fake para las dos tareas: el harness real corre entero (plantilla,
    guardrails, presupuesto, parseo estructurado, fila de auditoría) sin gastar
    un token."""

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        text = _EXERCISE_JSON if task == "exercise_generation" else _GUIDE_JSON
        return CompletionResult(
            text=text, model="groq/fake", prompt_tokens=10, completion_tokens=20
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)


def _stub_acquisition(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_json(url: str) -> dict[str, Any]:
        if "list=search" in url:
            return {"query": {"search": [{"pageid": 11}]}}
        return {
            "query": {
                "pages": {"11": {"title": "Estructura condicional", "extract": _WIKI_EXTRACT}}
            }
        }

    monkeypatch.setattr("logica.ai.rag.acquire._fetch_json", fake_fetch_json)
    monkeypatch.setattr("logica.ai.rag.acquire._POLITENESS_DELAY_SECONDS", 0)
    # El embebido real descargaría un modelo de sentence-transformers.
    monkeypatch.setattr("logica.ai.rag.ingestion.embed_texts", lambda texts: [[0.1] * 384])
    monkeypatch.setattr("logica.modules.rubrics.runner.ITEM_DELAY_SECONDS", 0)


async def _setup(client: AsyncClient, institution: Institution) -> dict[str, Any]:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    teacher = await get_user_by_email(f"doc@{domain}")
    language_id = await create_language(client, teacher_access)
    group = await create_group(client, teacher_access)

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
        db.add(template)
        await db.commit()
        template_id = str(template.id)

    return {
        "access": teacher_access,
        "teacher_id": teacher.id,
        "language_id": language_id,
        "group_id": group["id"],
        "template_id": template_id,
    }


def _payload(ctx: dict[str, Any], topics: list[str], **overrides: Any) -> dict[str, Any]:
    return {
        "name": "Temario primer periodo",
        "language_id": ctx["language_id"],
        "template_id": ctx["template_id"],
        "folder_name": "Guías 10-A",
        "items": [{"topic_name": name, "level": "basico", "extra_urls": []} for name in topics],
        "exercise_types": ["true_false"],
        "acquire_content": True,
        **overrides,
    }


async def _post_run(
    client: AsyncClient, ctx: dict[str, Any], topics: list[str], **overrides: Any
) -> tuple[dict[str, Any], _FakeArqPool]:
    pool = _FakeArqPool()
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_arq_pool] = lambda: pool
    try:
        response = await client.post(
            f"/groups/{ctx['group_id']}/rubric-runs",
            json=_payload(ctx, topics, **overrides),
            headers=auth_headers(ctx["access"]),
        )
    finally:
        app.dependency_overrides.pop(get_arq_pool, None)
    return response.json() | {"_status": response.status_code}, pool


async def _execute(run_id: str, redis_client: Any) -> None:
    session_factory = get_session_factory()
    async with session_factory() as db:
        await run_rubric(db, redis_client, run_id=uuid.UUID(run_id))


async def test_encola_la_corrida_y_responde_202(
    client: AsyncClient, institution: Institution
) -> None:
    ctx = await _setup(client, institution)
    run, pool = await _post_run(client, ctx, ["Estructuras condicionales"])

    assert run["_status"] == 202
    assert run["status"] == "pending"
    assert pool.jobs == [("run_rubric_job", (run["id"],))]


async def test_rechaza_mas_temas_que_el_tope(client: AsyncClient, institution: Institution) -> None:
    # El tope existe por la cuota diaria de tokens del docente: sin él una
    # rúbrica de 30 temas se queda a medias y consume el cupo del día.
    ctx = await _setup(client, institution)
    run, _ = await _post_run(client, ctx, [f"Tema {i}" for i in range(16)])
    assert run["_status"] == 409


async def test_genera_temario_guias_y_ejercicios_como_borrador(
    client: AsyncClient,
    institution: Institution,
    redis_client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_model(monkeypatch)
    _stub_acquisition(monkeypatch)
    ctx = await _setup(client, institution)
    run, _ = await _post_run(client, ctx, ["Estructuras condicionales", "Ciclos mientras"])

    await _execute(run["id"], redis_client)

    session_factory = get_session_factory()
    async with session_factory() as db:
        topics = (await db.execute(select(Topic))).scalars().all()
        states = (await db.execute(select(TopicGroupState))).scalars().all()
        guides = (await db.execute(select(Guide))).scalars().all()
        exercises = (await db.execute(select(Exercise))).scalars().all()
        links = (await db.execute(select(TopicExercise))).scalars().all()

    assert {t.name for t in topics} == {"Estructuras condicionales", "Ciclos mientras"}
    # Los temas quedan habilitados para el grupo: el docente pidió el temario, no
    # una lista de temas bloqueados que tendría que activar uno por uno.
    assert [s.state for s in states] == [TopicGroupStateValue.enabled] * 2

    # §9.2: NADA publicado. Esta es la aserción que no puede caerse nunca.
    assert len(guides) == 2
    assert all(g.status == GuideStatus.draft for g in guides)
    assert all(g.published_at is None for g in guides)
    assert all(e.status == ExerciseStatus.draft for e in exercises)

    # Cada ejercicio sabe de qué guía salió y sigue apareciendo al filtrar por
    # tema, que son los dos ejes de organización del dashboard.
    assert len(exercises) == 2
    assert all(e.guide_id is not None for e in exercises)
    assert len(links) == 2


async def test_reporta_el_progreso_por_tema(
    client: AsyncClient,
    institution: Institution,
    redis_client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_model(monkeypatch)
    _stub_acquisition(monkeypatch)
    ctx = await _setup(client, institution)
    run, _ = await _post_run(client, ctx, ["Estructuras condicionales"])

    await _execute(run["id"], redis_client)

    detail = await client.get(f"/rubric-runs/{run['id']}", headers=auth_headers(ctx["access"]))
    body = detail.json()
    assert body["run"]["status"] == RubricRunStatus.done.value
    item = body["items"][0]
    assert item["status"] == RubricItemStatus.done.value
    # Dos fuentes con el mismo título de artículo (Wikipedia y Wikibooks) son dos
    # documentos, no uno: el origen entra en el título justo para que el segundo
    # no reemplace al primero y el conteo diga la verdad.
    assert item["sources_ingested"] == 2
    assert item["exercises_created"] == 1
    assert item["topic_id"] and item["guide_id"]


async def test_sin_material_la_guia_igual_se_genera(
    client: AsyncClient,
    institution: Institution,
    redis_client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Que Wikipedia esté caída no puede tumbar el tema: `guide_writer` degrada
    # bien con el RAG vacío y una guía algo más genérica vale más que ninguna.
    _stub_model(monkeypatch)
    _stub_acquisition(monkeypatch)

    async def caido(url: str) -> dict[str, Any]:
        raise ValueError("wikipedia no responde")

    monkeypatch.setattr("logica.ai.rag.acquire._fetch_json", caido)

    ctx = await _setup(client, institution)
    run, _ = await _post_run(client, ctx, ["Estructuras condicionales"])
    await _execute(run["id"], redis_client)

    body = (
        await client.get(f"/rubric-runs/{run['id']}", headers=auth_headers(ctx["access"]))
    ).json()
    assert body["run"]["status"] == RubricRunStatus.done.value
    assert body["items"][0]["status"] == RubricItemStatus.done.value
    assert body["items"][0]["sources_ingested"] == 0


async def test_presupuesto_agotado_a_mitad_deja_la_corrida_parcial(
    client: AsyncClient,
    institution: Institution,
    redis_client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # El resultado común bajo el tier gratuito. `done` mentiría diciendo que el
    # temario está completo; `failed` mentiría diciendo que no hay nada.
    _stub_model(monkeypatch)
    _stub_acquisition(monkeypatch)
    ctx = await _setup(client, institution)
    run, _ = await _post_run(client, ctx, ["Tema uno", "Tema dos", "Tema tres"])

    llamadas = {"n": 0}
    real = __import__("logica.modules.rubrics.runner", fromlist=["check_budget"]).check_budget

    async def budget_que_se_agota(redis: Any, user_id: str, role: Any) -> None:
        llamadas["n"] += 1
        if llamadas["n"] > 1:
            raise ConflictError("Alcanzaste el límite diario de uso de IA")
        await real(redis, user_id, role)

    monkeypatch.setattr("logica.modules.rubrics.runner.check_budget", budget_que_se_agota)

    await _execute(run["id"], redis_client)

    body = (
        await client.get(f"/rubric-runs/{run['id']}", headers=auth_headers(ctx["access"]))
    ).json()
    assert body["run"]["status"] == RubricRunStatus.partial.value
    assert "límite diario" in (body["run"]["error_message"] or "")

    estados = [item["status"] for item in body["items"]]
    # El primero alcanzó a completarse; el segundo es donde se cortó; el tercero
    # ni se intentó — y eso se ve, en vez de quedar como un `done` mentiroso.
    assert estados[0] == RubricItemStatus.done.value
    assert estados[1] == RubricItemStatus.failed.value
    assert estados[2] == RubricItemStatus.pending.value


async def test_cancelar_detiene_la_corrida_dentro_del_tema_en_curso(
    client: AsyncClient,
    institution: Institution,
    redis_client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Antes la señal solo se miraba ENTRE temas, y como un tema son ~7 llamadas
    al modelo, cancelar tardaba minutos en notarse y parecía no funcionar. Este
    test cancela desde dentro del primer tema: si el corte solo ocurriera entre
    temas, el primero terminaría `done` y el segundo se procesaría igual."""
    _stub_model(monkeypatch)
    _stub_acquisition(monkeypatch)
    ctx = await _setup(client, institution)
    run, _ = await _post_run(client, ctx, ["Tema uno", "Tema dos"])

    # Cancelar en mitad del primer tema: en cuanto empieza a redactarse la guía.
    real_write = __import__("logica.modules.rubrics.runner", fromlist=["write_guide"]).write_guide

    async def cancelar_y_seguir(*args: Any, **kwargs: Any) -> Any:
        await client.post(f"/rubric-runs/{run['id']}/cancel", headers=auth_headers(ctx["access"]))
        return await real_write(*args, **kwargs)

    monkeypatch.setattr("logica.modules.rubrics.runner.write_guide", cancelar_y_seguir)

    await _execute(run["id"], redis_client)

    body = (
        await client.get(f"/rubric-runs/{run['id']}", headers=auth_headers(ctx["access"]))
    ).json()
    # `cancelled` y no `failed`: cancelar es una decisión del docente, no un
    # incidente de la plataforma.
    assert body["run"]["status"] == RubricRunStatus.cancelled.value

    estados = [item["status"] for item in body["items"]]
    assert estados[0] == RubricItemStatus.cancelled.value
    # El segundo ni se intentó: el corte fue dentro del primero, no después.
    assert estados[1] == RubricItemStatus.pending.value


async def test_un_docente_ajeno_no_ve_la_corrida(
    client: AsyncClient, institution: Institution
) -> None:
    ctx = await _setup(client, institution)
    run, _ = await _post_run(client, ctx, ["Estructuras condicionales"])

    domain = institution.email_domains[0]
    otro_access, _ = await register_and_login(client, email=f"otra@{domain}", role="teacher")
    response = await client.get(f"/rubric-runs/{run['id']}", headers=auth_headers(otro_access))
    assert response.status_code == 403
