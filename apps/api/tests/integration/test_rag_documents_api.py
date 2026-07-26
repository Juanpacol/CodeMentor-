import pytest
from httpx import AsyncClient
from sqlalchemy import select

from logica.ai.rag.ingestion import ingest_document
from logica.ai.rag.models import RagChunk, RagDocument
from logica.core.errors import ServiceUnavailableError
from logica.db import get_session_factory
from logica.modules.users.models import Institution
from tests.integration.conftest import (
    auth_headers,
    create_language,
    create_topic,
    register_and_login,
)

_DIMENSIONS = 384


def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
    return [[0.0] * _DIMENSIONS for _ in texts]


@pytest.fixture(autouse=True)
def _patch_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("logica.ai.rag.ingestion.embed_texts", _fake_embed_texts)


async def test_upload_document_creates_chunks(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    resp = await client.post(
        "/ai/rag/documents",
        files={"file": ("guia.md", b"# Guia\n\nContenido de prueba.", "text/markdown")},
        data={"title": "Guia de prueba"},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Guia de prueba"
    assert body["topic_id"] is None
    assert body["chunk_count"] >= 1

    session_factory = get_session_factory()
    async with session_factory() as db:
        chunks = (
            (await db.execute(select(RagChunk).where(RagChunk.document_id == body["id"])))
            .scalars()
            .all()
        )
    assert len(chunks) == body["chunk_count"]


async def test_upload_document_with_topic_and_rejects_bad_extension(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)

    resp = await client.post(
        "/ai/rag/documents",
        files={"file": ("guia.md", b"contenido", "text/markdown")},
        data={"title": "Guia con tema", "topic_id": topic_id},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["topic_id"] == topic_id

    rejected = await client.post(
        "/ai/rag/documents",
        files={"file": ("guia.pdf", b"contenido", "application/pdf")},
        data={"title": "PDF no permitido"},
        headers=auth_headers(teacher_access),
    )
    assert rejected.status_code == 422


async def test_list_documents_filters_by_topic(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)

    await client.post(
        "/ai/rag/documents",
        files={"file": ("a.md", b"contenido a", "text/markdown")},
        data={"title": "Con tema", "topic_id": topic_id},
        headers=auth_headers(teacher_access),
    )
    await client.post(
        "/ai/rag/documents",
        files={"file": ("b.md", b"contenido b", "text/markdown")},
        data={"title": "Sin tema"},
        headers=auth_headers(teacher_access),
    )

    all_docs = await client.get("/ai/rag/documents", headers=auth_headers(teacher_access))
    assert all_docs.status_code == 200
    assert len(all_docs.json()) == 2

    scoped = await client.get(
        "/ai/rag/documents", params={"topic_id": topic_id}, headers=auth_headers(teacher_access)
    )
    assert scoped.status_code == 200
    titles = {d["title"] for d in scoped.json()}
    assert titles == {"Con tema"}


async def test_delete_document_removes_chunks(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    created = await client.post(
        "/ai/rag/documents",
        files={"file": ("a.md", b"contenido a borrar", "text/markdown")},
        data={"title": "A borrar"},
        headers=auth_headers(teacher_access),
    )
    document_id = created.json()["id"]

    resp = await client.delete(
        f"/ai/rag/documents/{document_id}", headers=auth_headers(teacher_access)
    )
    assert resp.status_code == 204

    session_factory = get_session_factory()
    async with session_factory() as db:
        remaining_doc = await db.get(RagDocument, document_id)
        remaining_chunks = (
            (await db.execute(select(RagChunk).where(RagChunk.document_id == document_id)))
            .scalars()
            .all()
        )
    assert remaining_doc is None
    assert remaining_chunks == []


async def test_reupload_same_title_replaces_document_not_duplicates(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    first = await client.post(
        "/ai/rag/documents",
        files={"file": ("a.md", b"Version inicial del documento.", "text/markdown")},
        data={"title": "Guia reutilizable"},
        headers=auth_headers(teacher_access),
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]

    second = await client.post(
        "/ai/rag/documents",
        files={"file": ("a.md", b"Version actualizada, distinto contenido.", "text/markdown")},
        data={"title": "Guia reutilizable"},
        headers=auth_headers(teacher_access),
    )
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first_id

    session_factory = get_session_factory()
    async with session_factory() as db:
        documents = (
            (await db.execute(select(RagDocument).where(RagDocument.title == "Guia reutilizable")))
            .scalars()
            .all()
        )
        chunks = (
            (await db.execute(select(RagChunk).where(RagChunk.document_id == first_id)))
            .scalars()
            .all()
        )
    assert len(documents) == 1
    assert chunks
    assert all("actualizada" in c.content for c in chunks)


async def test_partial_chunk_failure_still_creates_document_with_surviving_chunks(
    institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _flaky_embed_texts(texts: list[str]) -> list[list[float]]:
        if any("ROMPER" in t for t in texts):
            raise RuntimeError("embedding backend failure")
        return [[0.0] * _DIMENSIONS for _ in texts]

    monkeypatch.setattr("logica.ai.rag.ingestion.embed_texts", _flaky_embed_texts)

    text = "Parrafo valido uno.\n\nROMPER este parrafo.\n\nParrafo valido dos."

    session_factory = get_session_factory()
    async with session_factory() as db:
        document = await ingest_document(
            db,
            institution_id=institution.id,
            title="Con chunk fallido",
            text=text,
            chunk_max_chars=10,
            chunk_overlap_chars=0,
        )
        await db.commit()
        document_id = document.id

    async with session_factory() as db:
        chunks = (
            (await db.execute(select(RagChunk).where(RagChunk.document_id == document_id)))
            .scalars()
            .all()
        )
    assert chunks
    assert all("ROMPER" not in c.content for c in chunks)


async def test_all_chunks_failing_returns_503(
    institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _always_fail_embed_texts(texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding backend down")

    monkeypatch.setattr("logica.ai.rag.ingestion.embed_texts", _always_fail_embed_texts)

    session_factory = get_session_factory()
    with pytest.raises(ServiceUnavailableError):
        async with session_factory() as db:
            await ingest_document(
                db,
                institution_id=institution.id,
                title="Todo falla",
                text="Contenido que nunca se va a embeber.",
            )
            # Sin commit: igual que el router, que solo comitea tras un
            # retorno exitoso — la sesión revierte al cerrarse.

    async with session_factory() as db:
        remaining = (
            (await db.execute(select(RagDocument).where(RagDocument.title == "Todo falla")))
            .scalars()
            .all()
        )
    assert remaining == []


async def test_student_forbidden_from_rag_document_endpoints(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    upload = await client.post(
        "/ai/rag/documents",
        files={"file": ("a.md", b"contenido", "text/markdown")},
        data={"title": "No permitido"},
        headers=auth_headers(student_access),
    )
    assert upload.status_code == 403

    listing = await client.get("/ai/rag/documents", headers=auth_headers(student_access))
    assert listing.status_code == 403


async def test_rag_document_isolated_between_institutions(
    client: AsyncClient, institution: Institution
) -> None:
    session_factory = get_session_factory()
    async with session_factory() as db:
        other_institution = Institution(name="Otro colegio", email_domains=["otro-colegio.edu.co"])
        db.add(other_institution)
        await db.commit()

    teacher_a_access, _ = await register_and_login(
        client, email=f"doc@{institution.email_domains[0]}", role="teacher"
    )
    teacher_b_access, _ = await register_and_login(
        client, email="doc@otro-colegio.edu.co", role="teacher"
    )

    created = await client.post(
        "/ai/rag/documents",
        files={"file": ("a.md", b"contenido colegio a", "text/markdown")},
        data={"title": "Material colegio A"},
        headers=auth_headers(teacher_a_access),
    )
    document_id = created.json()["id"]

    listing = await client.get("/ai/rag/documents", headers=auth_headers(teacher_b_access))
    assert listing.json() == []

    forbidden_delete = await client.delete(
        f"/ai/rag/documents/{document_id}", headers=auth_headers(teacher_b_access)
    )
    assert forbidden_delete.status_code == 404
