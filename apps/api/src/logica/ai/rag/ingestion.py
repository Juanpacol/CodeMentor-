import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.rag.chunking import chunk_text
from logica.ai.rag.embedder import embed_texts
from logica.ai.rag.models import RagChunk, RagDocument
from logica.core.errors import ConflictError, ServiceUnavailableError

logger = structlog.get_logger()


async def ingest_document(
    db: AsyncSession,
    *,
    institution_id: uuid.UUID,
    title: str,
    text: str,
    source_type: str = "teacher_material",
    topic_id: uuid.UUID | None = None,
    source_url: str | None = None,
    chunk_max_chars: int = 800,
    chunk_overlap_chars: int = 100,
) -> RagDocument:
    """Chunks, embeds and stores a document. Used both by the CLI
    (scripts/ingest_rag.py) and by `POST /ai/rag/documents` (Fase 14) — the
    reusable core so neither duplicates chunk/embed logic. `chunk_max_chars`/
    `chunk_overlap_chars` are exposed mainly so tests can force multiple,
    predictable chunks out of a short fixture document.

    Identity is `(institution_id, title)`: re-ingesting the same title
    replaces the existing document's chunks instead of creating a duplicate.
    Re-uploading under a different `topic_id` moves the document rather than
    duplicating it — title is the document's identity, not (title, topic)."""
    existing = await db.execute(
        select(RagDocument).where(
            RagDocument.institution_id == institution_id, RagDocument.title == title
        )
    )
    document = existing.scalar_one_or_none()
    is_reingest = document is not None
    # Fase 17: `source_url` solo se pisa cuando la reingesta trae uno, para que
    # volver a subir a mano un documento que antes vino de la web no borre en
    # silencio su atribución.
    fetched_at = datetime.now(UTC) if source_url else None
    if document is not None:
        document.source_type = source_type
        document.topic_id = topic_id
        if source_url:
            document.source_url = source_url
            document.fetched_at = fetched_at
        await db.execute(delete(RagChunk).where(RagChunk.document_id == document.id))
        logger.info("rag_document_reingest_detected", document_id=str(document.id), title=title)
    else:
        document = RagDocument(
            institution_id=institution_id,
            title=title,
            source_type=source_type,
            topic_id=topic_id,
            source_url=source_url,
            fetched_at=fetched_at,
        )
        db.add(document)

    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Ya existe un documento con este título; vuelve a intentar el envío."
        ) from exc

    chunks = chunk_text(text, max_chars=chunk_max_chars, overlap_chars=chunk_overlap_chars)
    if not chunks:
        logger.info(
            "rag_document_ingested",
            document_id=str(document.id),
            title=title,
            is_reingest=is_reingest,
            chunk_count=0,
            failed_chunk_count=0,
        )
        return document

    embedded = 0
    failed = 0
    for chunk in chunks:
        try:
            vector = embed_texts([chunk.text])[0]
        except Exception as exc:
            failed += 1
            logger.warning(
                "rag_chunk_embedding_failed",
                document_id=str(document.id),
                chunk_index=chunk.index,
                error=str(exc),
            )
            continue
        db.add(
            RagChunk(
                document_id=document.id,
                chunk_index=chunk.index,
                content=chunk.text,
                embedding=vector,
            )
        )
        embedded += 1

    if failed and embedded == 0:
        logger.error(
            "rag_ingestion_failed",
            document_id=str(document.id),
            title=title,
            chunk_count=len(chunks),
        )
        raise ServiceUnavailableError(
            "El servicio de embeddings no está disponible; intenta de nuevo más tarde."
        )

    await db.flush()
    logger.info(
        "rag_document_ingested",
        document_id=str(document.id),
        title=title,
        is_reingest=is_reingest,
        chunk_count=embedded,
        failed_chunk_count=failed,
    )
    return document
