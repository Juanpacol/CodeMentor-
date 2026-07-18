import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.rag.chunking import chunk_text
from logica.ai.rag.embedder import embed_texts
from logica.ai.rag.models import RagChunk, RagDocument


async def ingest_document(
    db: AsyncSession,
    *,
    institution_id: uuid.UUID,
    title: str,
    text: str,
    source_type: str = "teacher_material",
    topic_id: uuid.UUID | None = None,
    chunk_max_chars: int = 800,
    chunk_overlap_chars: int = 100,
) -> RagDocument:
    """Chunks, embeds and stores a document. Used both by the CLI
    (scripts/ingest_rag.py) and by `POST /ai/rag/documents` (Fase 14) — the
    reusable core so neither duplicates chunk/embed logic. `chunk_max_chars`/
    `chunk_overlap_chars` are exposed mainly so tests can force multiple,
    predictable chunks out of a short fixture document."""
    document = RagDocument(
        institution_id=institution_id, title=title, source_type=source_type, topic_id=topic_id
    )
    db.add(document)
    await db.flush()

    chunks = chunk_text(text, max_chars=chunk_max_chars, overlap_chars=chunk_overlap_chars)
    if not chunks:
        return document

    vectors = embed_texts([c.text for c in chunks])
    for chunk, vector in zip(chunks, vectors, strict=True):
        db.add(
            RagChunk(
                document_id=document.id,
                chunk_index=chunk.index,
                content=chunk.text,
                embedding=vector,
            )
        )

    await db.flush()
    return document
