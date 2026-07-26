"""Tests de las rutas de guías (Fase 16): permisos, versionado de plantillas y
el ciclo borrador → publicada. La generación en sí se prueba en
`test_agent_guide_writer.py` — acá el `enqueue_job` de arq se sustituye, porque
lo que importa es el contrato HTTP, no que el worker corra."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from logica.core.arq_dep import get_arq_pool
from logica.main import create_app
from logica.modules.users.models import Institution
from tests.integration.conftest import (
    auth_headers,
    create_group,
    create_language,
    create_topic,
    join_group,
    register_and_login,
)

_SECTIONS = [
    {"heading": "Objetivos", "instructions": "Lista 3 objetivos de aprendizaje."},
    {"heading": "Explicación", "instructions": "Explica el tema con un ejemplo."},
]


class _FakeArqPool:
    """Registra los encolados en vez de encolarlos: `POST /ai/guides/generate`
    devuelve 202 y el worker es otro proceso, así que en un test HTTP lo único
    verificable es que se encoló el job correcto."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, name: str, *args: Any) -> None:
        self.jobs.append((name, args))


@pytest.fixture
def arq_pool() -> _FakeArqPool:
    return _FakeArqPool()


@pytest.fixture
async def client(arq_pool: _FakeArqPool) -> Any:
    """Sobrescribe `client` del conftest para inyectar el pool falso — mismo
    patrón de `dependency_overrides` que usa FastAPI para dependencias externas."""
    from httpx import ASGITransport

    app = create_app()
    app.dependency_overrides[get_arq_pool] = lambda: arq_pool
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as ac,
    ):
        yield ac


async def _teacher_with_group(client: AsyncClient, institution: Institution) -> tuple[str, dict]:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    group = await create_group(client, teacher_access)
    return teacher_access, group


async def _folder(
    client: AsyncClient, teacher_access: str, group_id: str, name: str = "Guías 10-1"
) -> str:
    resp = await client.post(
        f"/groups/{group_id}/guide-folders",
        json={"name": name},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 201, resp.text
    folder_id: str = resp.json()["id"]
    return folder_id


async def _template(
    client: AsyncClient, teacher_access: str, name: str = "Guía de laboratorio"
) -> dict:
    resp = await client.post(
        "/guide-templates",
        json={
            "name": name,
            "sections": _SECTIONS,
            "tone": "cercano",
            "target_level": "basico",
        },
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 201, resp.text
    template: dict = resp.json()
    return template


async def test_student_cannot_create_folder_or_template(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, group = await _teacher_with_group(client, institution)
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    folder_resp = await client.post(
        f"/groups/{group['id']}/guide-folders",
        json={"name": "Mis guías"},
        headers=auth_headers(student_access),
    )
    assert folder_resp.status_code == 403

    template_resp = await client.post(
        "/guide-templates",
        json={"name": "X", "sections": _SECTIONS, "tone": "cercano", "target_level": "basico"},
        headers=auth_headers(student_access),
    )
    assert template_resp.status_code == 403


async def test_duplicate_folder_name_in_same_group_conflicts(
    client: AsyncClient, institution: Institution
) -> None:
    teacher_access, group = await _teacher_with_group(client, institution)
    await _folder(client, teacher_access, group["id"])

    resp = await client.post(
        f"/groups/{group['id']}/guide-folders",
        json={"name": "Guías 10-1"},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 409


async def test_saving_template_with_same_name_creates_new_version(
    client: AsyncClient, institution: Institution
) -> None:
    """Una plantilla publicada nunca se muta: guardar con el mismo nombre agrega
    la versión N+1, para que las guías viejas sigan explicándose contra la
    plantilla exacta que las produjo."""
    teacher_access, _ = await _teacher_with_group(client, institution)

    first = await _template(client, teacher_access)
    second = await _template(client, teacher_access)

    assert first["version"] == 1
    assert second["version"] == 2
    assert first["id"] != second["id"]

    listed = await client.get("/guide-templates", headers=auth_headers(teacher_access))
    assert {t["version"] for t in listed.json()} == {1, 2}


async def test_template_requires_at_least_one_section(
    client: AsyncClient, institution: Institution
) -> None:
    teacher_access, _ = await _teacher_with_group(client, institution)

    resp = await client.post(
        "/guide-templates",
        json={"name": "Vacía", "sections": [], "tone": "cercano", "target_level": "basico"},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 422


async def test_generate_returns_202_and_enqueues_the_job(
    client: AsyncClient, institution: Institution, arq_pool: _FakeArqPool
) -> None:
    teacher_access, group = await _teacher_with_group(client, institution)
    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    folder_id = await _folder(client, teacher_access, group["id"])
    template = await _template(client, teacher_access)

    resp = await client.post(
        "/ai/guides/generate",
        json={"folder_id": folder_id, "template_id": template["id"], "topic_id": topic_id},
        headers=auth_headers(teacher_access),
    )

    # 202, no 201: la guía existe pero todavía no tiene contenido.
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "generating"
    assert body["origin"] == "ai"
    assert body["content_md"] == ""
    assert body["title"] == "Guía de laboratorio — Estructuras condicionales"

    assert arq_pool.jobs == [("generate_guide_job", (body["id"],))]


async def test_student_never_sees_drafts_only_published(
    client: AsyncClient, institution: Institution, arq_pool: _FakeArqPool
) -> None:
    """El corazón de §9.2 en esta fase: mientras la guía no esté publicada por un
    docente, para el estudiante no existe."""
    domain = institution.email_domains[0]
    teacher_access, group = await _teacher_with_group(client, institution)
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")
    await join_group(client, student_access, group["invite_code"])

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    folder_id = await _folder(client, teacher_access, group["id"])
    template = await _template(client, teacher_access)

    created = await client.post(
        "/ai/guides/generate",
        json={"folder_id": folder_id, "template_id": template["id"], "topic_id": topic_id},
        headers=auth_headers(teacher_access),
    )
    guide_id = created.json()["id"]

    # En `generating` no se puede publicar ni editar.
    assert (
        await client.post(f"/guides/{guide_id}/publish", headers=auth_headers(teacher_access))
    ).status_code == 409
    assert (
        await client.patch(
            f"/guides/{guide_id}",
            json={"content_md": "hola"},
            headers=auth_headers(teacher_access),
        )
    ).status_code == 409

    student_view = await client.get(
        f"/groups/{group['id']}/guides", headers=auth_headers(student_access)
    )
    assert student_view.json() == []

    # El docente completa el contenido a mano (simula lo que hace el worker) y publica.
    await _force_draft(client, teacher_access, guide_id)
    published = await client.post(
        f"/guides/{guide_id}/publish", headers=auth_headers(teacher_access)
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["published_at"] is not None

    student_after = await client.get(
        f"/groups/{group['id']}/guides", headers=auth_headers(student_access)
    )
    assert [g["id"] for g in student_after.json()] == [guide_id]


async def _force_draft(client: AsyncClient, teacher_access: str, guide_id: str) -> None:
    """Lleva la guía de `generating` a `draft` con contenido, sin pasar por el
    worker — el equivalente a que el agente haya terminado."""
    from logica.db import get_session_factory
    from logica.modules.guides.models import Guide, GuideStatus

    session_factory = get_session_factory()
    async with session_factory() as db:
        guide = await db.get(Guide, uuid.UUID(guide_id))
        assert guide is not None
        guide.status = GuideStatus.draft
        guide.content_md = "## Objetivos\n\nContenido de prueba."
        await db.commit()


async def test_cannot_publish_a_guide_without_content(
    client: AsyncClient, institution: Institution, arq_pool: _FakeArqPool
) -> None:
    teacher_access, group = await _teacher_with_group(client, institution)
    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    folder_id = await _folder(client, teacher_access, group["id"])
    template = await _template(client, teacher_access)

    created = await client.post(
        "/ai/guides/generate",
        json={"folder_id": folder_id, "template_id": template["id"], "topic_id": topic_id},
        headers=auth_headers(teacher_access),
    )
    guide_id = created.json()["id"]

    from logica.db import get_session_factory
    from logica.modules.guides.models import Guide, GuideStatus

    session_factory = get_session_factory()
    async with session_factory() as db:
        guide = await db.get(Guide, uuid.UUID(guide_id))
        assert guide is not None
        guide.status = GuideStatus.draft  # draft pero con content_md vacío
        await db.commit()

    resp = await client.post(f"/guides/{guide_id}/publish", headers=auth_headers(teacher_access))
    assert resp.status_code == 422


async def test_teacher_of_another_group_cannot_read_the_guide(
    client: AsyncClient, institution: Institution, arq_pool: _FakeArqPool
) -> None:
    domain = institution.email_domains[0]
    teacher_access, group = await _teacher_with_group(client, institution)
    other_access, _ = await register_and_login(client, email=f"otro@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    folder_id = await _folder(client, teacher_access, group["id"])
    template = await _template(client, teacher_access)

    created = await client.post(
        "/ai/guides/generate",
        json={"folder_id": folder_id, "template_id": template["id"], "topic_id": topic_id},
        headers=auth_headers(teacher_access),
    )
    guide_id = created.json()["id"]

    resp = await client.get(f"/guides/{guide_id}", headers=auth_headers(other_access))
    assert resp.status_code == 403

    folder_resp = await client.get(
        f"/guide-folders/{folder_id}/guides", headers=auth_headers(other_access)
    )
    assert folder_resp.status_code == 403


async def test_ai_draft_guides_appear_in_pending_approvals(
    client: AsyncClient, institution: Institution, arq_pool: _FakeArqPool
) -> None:
    """Fase 16 entra en la cola de aprobación que ya existe (§9.6), no en una
    pestaña aparte."""
    teacher_access, group = await _teacher_with_group(client, institution)
    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    folder_id = await _folder(client, teacher_access, group["id"])
    template = await _template(client, teacher_access)

    created = await client.post(
        "/ai/guides/generate",
        json={"folder_id": folder_id, "template_id": template["id"], "topic_id": topic_id},
        headers=auth_headers(teacher_access),
    )
    guide_id = created.json()["id"]

    # En `generating` todavía no es un pendiente: no hay nada que revisar.
    pending = await client.get("/ai/pending-approvals", headers=auth_headers(teacher_access))
    assert pending.json()["guides"] == []

    await _force_draft(client, teacher_access, guide_id)

    pending_draft = await client.get("/ai/pending-approvals", headers=auth_headers(teacher_access))
    assert [g["id"] for g in pending_draft.json()["guides"]] == [guide_id]

    await client.post(f"/guides/{guide_id}/publish", headers=auth_headers(teacher_access))

    pending_after = await client.get("/ai/pending-approvals", headers=auth_headers(teacher_access))
    assert pending_after.json()["guides"] == []
