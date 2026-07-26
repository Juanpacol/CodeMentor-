"""Tests del cron de autogeneración de guías (Fase 16).

Lo importante acá no es que el contenido salga bien (eso es
`test_agent_guide_writer.py`) sino que el cron **no genere de más**: solo sobre
carpetas donde el docente eligió una plantilla, respetando el interruptor del
agente, sin duplicar, y con el tope por corrida."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

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
from logica.workers import settings as worker_settings
from tests.integration.conftest import (
    auth_headers,
    create_group,
    create_language,
    create_topic,
    enable_topic,
    get_user_by_email,
    register_and_login,
)


class _FakeArqPool:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, name: str, *args: Any) -> None:
        self.jobs.append((name, args))


async def _run_cron(arq_pool: _FakeArqPool) -> int:
    """arq expone el pool en `ctx["redis"]`, que es lo que el job usa para
    encolar la redacción de cada guía creada."""
    return await worker_settings.generate_guides_for_enabled_topics_job({"redis": arq_pool})


async def _setup(
    client: AsyncClient,
    institution: Institution,
    *,
    auto_generate: bool,
    topic_names: list[str] | None = None,
) -> dict[str, Any]:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    teacher = await get_user_by_email(f"doc@{domain}")
    language_id = await create_language(client, teacher_access)
    group = await create_group(client, teacher_access)

    topic_ids = []
    for index, name in enumerate(topic_names or ["Ciclos"]):
        topic_ids.append(
            await create_topic(client, teacher_access, language_id, name=name, order_index=index)
        )

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
        await db.flush()
        folder = GuidesFolder(
            institution_id=institution.id,
            group_id=uuid.UUID(group["id"]),
            created_by_id=teacher.id,
            name="Guías 10-1",
            description=None,
            auto_generate_template_id=template.id if auto_generate else None,
        )
        db.add(folder)
        await db.commit()
        folder_id = folder.id

    return {
        "teacher_access": teacher_access,
        "group": group,
        "topic_ids": topic_ids,
        "folder_id": folder_id,
    }


async def _guides_count(institution: Institution) -> int:
    from sqlalchemy import func, select

    session_factory = get_session_factory()
    async with session_factory() as db:
        result = await db.execute(
            select(func.count()).select_from(Guide).where(Guide.institution_id == institution.id)
        )
        return int(result.scalar_one())


async def test_enabling_a_topic_autogenerates_a_draft(
    client: AsyncClient, institution: Institution
) -> None:
    ctx = await _setup(client, institution, auto_generate=True)
    await enable_topic(client, ctx["teacher_access"], ctx["group"]["id"], ctx["topic_ids"][0])

    arq_pool = _FakeArqPool()
    created = await _run_cron(arq_pool)

    assert created == 1
    assert len(arq_pool.jobs) == 1
    assert arq_pool.jobs[0][0] == "generate_guide_job"

    session_factory = get_session_factory()
    async with session_factory() as db:
        guide = await db.get(Guide, uuid.UUID(arq_pool.jobs[0][1][0]))
        assert guide is not None
        # Nace como borrador de IA: el cron nunca publica (§9.2).
        assert guide.status == GuideStatus.generating
        assert guide.origin == GuideOrigin.ai
        assert guide.topic_id == uuid.UUID(ctx["topic_ids"][0])


async def test_folder_without_opt_in_is_ignored(
    client: AsyncClient, institution: Institution
) -> None:
    """Sin `auto_generate_template_id` el cron no toca la carpeta: la
    automatización nunca se activa sola sobre contenido que el docente maneja a
    mano."""
    ctx = await _setup(client, institution, auto_generate=False)
    await enable_topic(client, ctx["teacher_access"], ctx["group"]["id"], ctx["topic_ids"][0])

    created = await _run_cron(_FakeArqPool())

    assert created == 0
    assert await _guides_count(institution) == 0


async def test_locked_topic_is_not_generated(client: AsyncClient, institution: Institution) -> None:
    """El tema existe pero el docente no lo habilitó — la plataforma no adelanta
    contenido por su cuenta."""
    await _setup(client, institution, auto_generate=True)

    created = await _run_cron(_FakeArqPool())

    assert created == 0
    assert await _guides_count(institution) == 0


async def test_disabled_agent_blocks_the_cron(
    client: AsyncClient, institution: Institution
) -> None:
    ctx = await _setup(client, institution, auto_generate=True)
    await enable_topic(client, ctx["teacher_access"], ctx["group"]["id"], ctx["topic_ids"][0])

    await client.put(
        f"/ai/groups/{ctx['group']['id']}/agents/guide_generation",
        json={"enabled": False},
        headers=auth_headers(ctx["teacher_access"]),
    )

    created = await _run_cron(_FakeArqPool())

    # El cron no puede saltarse el interruptor que el docente apagó.
    assert created == 0
    assert await _guides_count(institution) == 0


async def test_second_run_does_not_duplicate(client: AsyncClient, institution: Institution) -> None:
    ctx = await _setup(client, institution, auto_generate=True)
    await enable_topic(client, ctx["teacher_access"], ctx["group"]["id"], ctx["topic_ids"][0])

    assert await _run_cron(_FakeArqPool()) == 1
    assert await _run_cron(_FakeArqPool()) == 0
    assert await _guides_count(institution) == 1


async def test_archived_guide_is_not_regenerated(
    client: AsyncClient, institution: Institution
) -> None:
    """Archivar es una decisión del docente: regenerarla sería desobedecerlo."""
    ctx = await _setup(client, institution, auto_generate=True)
    await enable_topic(client, ctx["teacher_access"], ctx["group"]["id"], ctx["topic_ids"][0])
    await _run_cron(_FakeArqPool())

    session_factory = get_session_factory()
    async with session_factory() as db:
        from sqlalchemy import select

        guide = (
            await db.execute(select(Guide).where(Guide.institution_id == institution.id))
        ).scalar_one()
        guide.status = GuideStatus.archived
        await db.commit()

    assert await _run_cron(_FakeArqPool()) == 0
    assert await _guides_count(institution) == 1


async def test_failed_guide_is_retried(client: AsyncClient, institution: Institution) -> None:
    """`failed` cuenta como inexistente: si el intento anterior murió, la corrida
    siguiente lo reintenta."""
    ctx = await _setup(client, institution, auto_generate=True)
    await enable_topic(client, ctx["teacher_access"], ctx["group"]["id"], ctx["topic_ids"][0])
    await _run_cron(_FakeArqPool())

    session_factory = get_session_factory()
    async with session_factory() as db:
        from sqlalchemy import select

        guide = (
            await db.execute(select(Guide).where(Guide.institution_id == institution.id))
        ).scalar_one()
        guide.status = GuideStatus.failed
        await db.commit()

    assert await _run_cron(_FakeArqPool()) == 1
    assert await _guides_count(institution) == 2


async def test_run_is_capped_and_reports_the_remainder(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El tope protege la cuota del tier gratuito de Groq; lo que no entra se
    genera en la corrida siguiente, no se pierde."""
    monkeypatch.setattr(worker_settings, "GUIDES_PER_CRON_RUN", 2)

    ctx = await _setup(
        client, institution, auto_generate=True, topic_names=["Ciclos", "Variables", "Funciones"]
    )
    for topic_id in ctx["topic_ids"]:
        await enable_topic(client, ctx["teacher_access"], ctx["group"]["id"], topic_id)

    assert await _run_cron(_FakeArqPool()) == 2
    # La 3ra queda pendiente y entra en la corrida siguiente.
    assert await _run_cron(_FakeArqPool()) == 1
    assert await _guides_count(institution) == 3
