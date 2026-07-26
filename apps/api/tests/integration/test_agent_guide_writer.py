"""Tests del agente Creador de guías (Fase 16). Ejercitan `write_guide` directo
en vez de por HTTP porque el agente corre en el worker de arq, no en el request
path — las rutas se prueban en `test_guides_api.py`."""

import uuid

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis

from logica.ai.agents.guide_writer import write_guide
from logica.ai.harness import budget
from logica.ai.harness.router import CompletionResult
from logica.ai.rag.ingestion import ingest_document
from logica.config import get_settings
from logica.db import get_session_factory
from logica.modules.content.models import TopicLevel
from logica.modules.guides.models import (
    Guide,
    GuideOrigin,
    GuidesFolder,
    GuideStatus,
    GuideTemplate,
)
from logica.modules.users.models import Institution
from tests.integration.conftest import (
    auth_headers,
    create_group,
    create_language,
    create_topic,
    get_user_by_email,
    register_and_login,
)

_DIMENSIONS = 384

_SECTIONS = [
    {"heading": "Objetivos", "instructions": "Lista 3 objetivos."},
    {"heading": "Explicación", "instructions": "Explica el tema con un ejemplo."},
    {"heading": "Ejercicios", "instructions": "Propón 2 ejercicios."},
]


def _fake_embed_query(text: str) -> list[float]:
    """Vector constante: lo que se prueba acá no es la relevancia del retrieval,
    solo que el agente use lo que el retriever le devuelva."""
    vector = [0.0] * _DIMENSIONS
    vector[0] = 1.0
    return vector


@pytest.fixture(autouse=True)
def _patch_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("logica.ai.rag.retriever.embed_query", _fake_embed_query)
    monkeypatch.setattr(
        "logica.ai.rag.ingestion.embed_texts", lambda texts: [_fake_embed_query(t) for t in texts]
    )


def _section_response(heading: str) -> str:
    return (
        f'{{"heading": "{heading}", "body_md": "Cuerpo de la sección con suficiente '
        'longitud para pasar la validación del modelo de salida."}'
    )


class _Seeded:
    """Lo que necesita cada test: la guía en `generating` más el docente y el
    grupo para poder actuar sobre ellos por HTTP."""

    def __init__(
        self, guide_id: uuid.UUID, teacher_id: uuid.UUID, teacher_access: str, group_id: str
    ):
        self.guide_id = guide_id
        self.teacher_id = teacher_id
        self.teacher_access = teacher_access
        self.group_id = group_id


async def _seed_guide(
    client: AsyncClient,
    institution: Institution,
    *,
    sections: list[dict[str, str]] | None = None,
) -> _Seeded:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = await create_group(client, teacher_access)
    teacher = await get_user_by_email(f"doc@{domain}")

    session_factory = get_session_factory()
    async with session_factory() as db:
        folder = GuidesFolder(
            institution_id=institution.id,
            group_id=uuid.UUID(group["id"]),
            created_by_id=teacher.id,
            name="Guías 10-1",
            description=None,
        )
        template = GuideTemplate(
            institution_id=institution.id,
            created_by_id=teacher.id,
            name="Guía de laboratorio",
            sections=_SECTIONS if sections is None else sections,
            tone="cercano",
            target_level=TopicLevel.basico,
            version=1,
        )
        db.add_all([folder, template])
        await db.flush()
        guide = Guide(
            institution_id=institution.id,
            folder_id=folder.id,
            template_id=template.id,
            topic_id=uuid.UUID(topic_id),
            created_by_id=teacher.id,
            title="Guía de laboratorio — Ciclos",
            origin=GuideOrigin.ai,
            status=GuideStatus.generating,
        )
        db.add(guide)
        await db.commit()
        return _Seeded(guide.id, teacher.id, teacher_access, group["id"])


async def _run_write_guide(guide_id: uuid.UUID, redis: Redis) -> Guide:
    session_factory = get_session_factory()
    async with session_factory() as db:
        guide = await write_guide(db, redis, guide_id=guide_id)
        await db.commit()
        await db.refresh(guide)
        return guide


def _always(text: str) -> object:
    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(text=text, model="groq/fake", prompt_tokens=1, completion_tokens=1)

    return fake


async def test_guide_is_drafted_never_published(
    client: AsyncClient,
    institution: Institution,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = await _seed_guide(client, institution)
    monkeypatch.setattr(
        "logica.ai.harness.harness.router_complete", _always(_section_response("Objetivos"))
    )

    guide = await _run_write_guide(seeded.guide_id, redis_client)

    # §9.2: nunca `published` por su cuenta — el docente publica explícitamente.
    assert guide.status == GuideStatus.draft
    assert guide.origin == GuideOrigin.ai
    assert guide.prompt_version == 1
    # Un `##` por sección de la plantilla, ensamblado en Python.
    assert guide.content_md.count("## ") == len(_SECTIONS)


async def test_one_failing_section_does_not_lose_the_others(
    client: AsyncClient,
    institution: Institution,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aislamiento por sección: la 2da agota sus reintentos con JSON inválido y la
    guía se entrega igual con las otras 2. Es el `except LogicaError` del bucle lo
    que aísla, no un SAVEPOINT — `StructuredOutputError` se levanta en Python tras
    escribir bien en `ai_interactions`, así que la transacción nunca se envenena."""
    seeded = await _seed_guide(client, institution)

    calls = 0

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        nonlocal calls
        calls += 1
        # La 2da sección devuelve JSON inválido en todos sus reintentos
        # (`complete_structured` intenta 3 veces: llamadas 2, 3 y 4).
        text = "no soy json" if 2 <= calls <= 4 else _section_response("Sección")
        return CompletionResult(text=text, model="groq/fake", prompt_tokens=1, completion_tokens=1)

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    guide = await _run_write_guide(seeded.guide_id, redis_client)

    assert guide.status == GuideStatus.draft
    assert guide.content_md.count("## ") == len(_SECTIONS) - 1
    assert guide.error_message is None


async def test_all_sections_failing_marks_guide_failed(
    client: AsyncClient,
    institution: Institution,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = await _seed_guide(client, institution)
    monkeypatch.setattr("logica.ai.harness.harness.router_complete", _always("tampoco soy json"))

    guide = await _run_write_guide(seeded.guide_id, redis_client)

    assert guide.status == GuideStatus.failed
    assert guide.error_message is not None
    assert guide.content_md == ""


async def test_exhausted_budget_reports_its_own_reason(
    client: AsyncClient,
    institution: Institution,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un fallo global (cupo agotado) no debe disfrazarse de "el modelo no pudo
    redactar": el docente necesita saber que el motivo es el límite diario."""
    seeded = await _seed_guide(client, institution)
    await budget.record_usage(
        redis_client, str(seeded.teacher_id), get_settings().ai_daily_token_budget_per_teacher
    )

    called = False

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        nonlocal called
        called = True
        return CompletionResult(text="{}", model="x", prompt_tokens=0, completion_tokens=0)

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    guide = await _run_write_guide(seeded.guide_id, redis_client)

    assert guide.status == GuideStatus.failed
    assert "límite diario" in (guide.error_message or "")
    # Se corta en la primera sección en vez de reintentar las 3 sin posibilidad.
    assert called is False


async def test_teacher_budget_is_larger_than_student_budget(
    client: AsyncClient,
    institution: Institution,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin el tope por rol (Fase 16), una guía de varias secciones agotaría el cupo
    de estudiante y ninguna guía llegaría a generarse."""
    seeded = await _seed_guide(client, institution)
    await budget.record_usage(
        redis_client, str(seeded.teacher_id), get_settings().ai_daily_token_budget_per_student
    )
    monkeypatch.setattr(
        "logica.ai.harness.harness.router_complete", _always(_section_response("Objetivos"))
    )

    guide = await _run_write_guide(seeded.guide_id, redis_client)

    assert guide.status == GuideStatus.draft


async def test_disabled_agent_blocks_generation(
    client: AsyncClient,
    institution: Institution,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = await _seed_guide(client, institution)
    await client.put(
        f"/ai/groups/{seeded.group_id}/agents/guide_generation",
        json={"enabled": False},
        headers=auth_headers(seeded.teacher_access),
    )

    called = False

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        nonlocal called
        called = True
        return CompletionResult(text="{}", model="x", prompt_tokens=0, completion_tokens=0)

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    guide = await _run_write_guide(seeded.guide_id, redis_client)

    assert guide.status == GuideStatus.failed
    assert called is False


async def test_sources_cite_the_course_material(
    client: AsyncClient,
    institution: Institution,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Guide.sources` es lo que le permite al docente verificar de dónde salió el
    contenido — por eso el agente usa `retriever.retrieve()` y no el skill
    `retrieve_context()`, que descarta los títulos."""
    seeded = await _seed_guide(client, institution)

    session_factory = get_session_factory()
    async with session_factory() as db:
        await ingest_document(
            db,
            institution_id=institution.id,
            title="Apuntes de ciclos",
            text="El ciclo Mientras evalúa su condición antes de ejecutar el bloque.",
        )
        await db.commit()

    monkeypatch.setattr(
        "logica.ai.harness.harness.router_complete", _always(_section_response("Objetivos"))
    )

    guide = await _run_write_guide(seeded.guide_id, redis_client)

    assert guide.status == GuideStatus.draft
    assert guide.sources == ["Apuntes de ciclos"]
