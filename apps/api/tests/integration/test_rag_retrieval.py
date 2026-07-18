import uuid

import pytest
from httpx import AsyncClient

from logica.ai.rag.ingestion import ingest_document
from logica.ai.skills.retrieve_context import retrieve_context
from logica.db import get_session_factory
from logica.modules.users.models import Institution
from tests.integration.conftest import create_language, create_topic, register_and_login

# Deterministic fixture vectors (§ "fixture de embeddings pre-computados para
# no cargar el modelo en CI"): one-hot-ish vectors keyed by which keyword the
# text mentions, so cosine similarity is trivially predictable without ever
# loading sentence-transformers in the test suite.
_DIMENSIONS = 384


def _vector_for(text: str) -> list[float]:
    vector = [0.0] * _DIMENSIONS
    if "mientras" in text.lower():
        vector[0] = 1.0
    elif "para" in text.lower():
        vector[1] = 1.0
    else:
        vector[2] = 1.0
    return vector


def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
    return [_vector_for(t) for t in texts]


def _fake_embed_query(text: str) -> list[float]:
    return _vector_for(text)


@pytest.fixture(autouse=True)
def _patch_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("logica.ai.rag.ingestion.embed_texts", _fake_embed_texts)
    monkeypatch.setattr("logica.ai.rag.retriever.embed_query", _fake_embed_query)


_COURSE_MATERIAL = (
    "El ciclo Mientras se usa cuando no sabemos de antemano cuántas veces se "
    "repetirá una acción; la condición se evalúa antes de cada repetición.\n\n"
    "El ciclo Para se usa cuando conocemos de antemano el número exacto de "
    "repeticiones que necesitamos hacer."
)


async def test_ingest_and_retrieve_correct_chunk_for_keyword_query(
    institution: Institution,
) -> None:
    session_factory = get_session_factory()
    async with session_factory() as db:
        # chunk_max_chars=160 keeps each paragraph (~106-146 chars) as its
        # own chunk without a mid-paragraph hard split; overlap_chars=0
        # keeps the two chunks free of cross-contamination so the fixture
        # embeddings below stay unambiguous.
        await ingest_document(
            db,
            institution_id=institution.id,
            title="Referencia PSeInt",
            text=_COURSE_MATERIAL,
            chunk_max_chars=160,
            chunk_overlap_chars=0,
        )
        await db.commit()

    async with session_factory() as db:
        context = await retrieve_context(db, institution.id, "¿Cuándo debo usar Mientras?", top_k=1)

    assert "[Fuente: Referencia PSeInt]" in context
    assert "Mientras" in context
    assert "Para" not in context


async def test_retrieve_context_empty_when_no_documents(institution: Institution) -> None:
    session_factory = get_session_factory()
    async with session_factory() as db:
        context = await retrieve_context(db, institution.id, "cualquier consulta")
    assert context == ""


async def test_retrieval_is_scoped_to_institution(institution: Institution) -> None:
    session_factory = get_session_factory()

    async with session_factory() as db:
        other_institution = Institution(name="Otro colegio", email_domains=["otro-colegio.edu.co"])
        db.add(other_institution)
        await db.commit()
        await db.refresh(other_institution)

    async with session_factory() as db:
        await ingest_document(
            db,
            institution_id=other_institution.id,
            title="Material de otro colegio",
            text=_COURSE_MATERIAL,
        )
        await db.commit()

    async with session_factory() as db:
        context = await retrieve_context(db, institution.id, "Mientras", top_k=5)

    assert context == ""


async def test_topic_scoped_retrieval_includes_topic_and_general_material(
    client: AsyncClient, institution: Institution
) -> None:
    """Fase 14: pasar topic_id no deja fuera el material general (sin tema
    asignado), pero sí excluye el material de OTRO tema — confirma la
    semántica de `_scope_to_topic` (topic_id == X OR topic_id IS NULL)."""
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    language_id = await create_language(client, teacher_access)
    topic_a_id = await create_topic(client, teacher_access, language_id, name="Ciclos")
    topic_b_id = await create_topic(client, teacher_access, language_id, name="Funciones")

    session_factory = get_session_factory()
    async with session_factory() as db:
        await ingest_document(
            db,
            institution_id=institution.id,
            title="Material de Ciclos",
            text=_COURSE_MATERIAL,
            topic_id=uuid.UUID(topic_a_id),
        )
        await ingest_document(
            db,
            institution_id=institution.id,
            title="Material de Funciones",
            text=_COURSE_MATERIAL,
            topic_id=uuid.UUID(topic_b_id),
        )
        await ingest_document(
            db,
            institution_id=institution.id,
            title="Material general",
            text=_COURSE_MATERIAL,
        )
        await db.commit()

    async with session_factory() as db:
        context = await retrieve_context(
            db, institution.id, "Mientras", top_k=5, topic_id=uuid.UUID(topic_a_id)
        )

    assert "[Fuente: Material de Ciclos]" in context
    assert "[Fuente: Material general]" in context
    assert "[Fuente: Material de Funciones]" not in context
