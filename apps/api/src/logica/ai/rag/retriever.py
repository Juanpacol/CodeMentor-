import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.rag.embedder import embed_query
from logica.ai.rag.models import RagChunk, RagDocument

# Reciprocal Rank Fusion constant (standard choice, not tuned per-dataset):
# combines two independently-ranked lists (vector similarity, full-text
# search) without needing to calibrate how to weigh a cosine distance
# against a ts_rank score, which live on unrelated scales.
_RRF_K = 60


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    content: str
    score: float


async def _vector_candidates(
    db: AsyncSession, institution_id: uuid.UUID, query_vector: list[float], limit: int
) -> list[tuple[uuid.UUID, uuid.UUID, str, str]]:
    stmt = (
        select(RagChunk.id, RagChunk.document_id, RagDocument.title, RagChunk.content)
        .join(RagDocument, RagDocument.id == RagChunk.document_id)
        .where(RagDocument.institution_id == institution_id)
        .order_by(RagChunk.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [tuple(row) for row in result.all()]


async def _fulltext_candidates(
    db: AsyncSession, institution_id: uuid.UUID, query_text: str, limit: int
) -> list[tuple[uuid.UUID, uuid.UUID, str, str]]:
    tsquery = func.plainto_tsquery("spanish", query_text)
    tsvector = func.to_tsvector("spanish", RagChunk.content)
    stmt = (
        select(RagChunk.id, RagChunk.document_id, RagDocument.title, RagChunk.content)
        .join(RagDocument, RagDocument.id == RagChunk.document_id)
        .where(RagDocument.institution_id == institution_id, tsvector.op("@@")(tsquery))
        .order_by(func.ts_rank(tsvector, tsquery).desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [tuple(row) for row in result.all()]


async def retrieve(
    db: AsyncSession, institution_id: uuid.UUID, query: str, top_k: int = 5
) -> list[RetrievedChunk]:
    """Hybrid retrieval: vector similarity (semantic match) fused with
    Postgres full-text search (exact keyword match — catches PSeInt keyword
    lookups like "Mientras" that a small embedding model may under-weigh)."""
    query_vector = embed_query(query)
    candidate_limit = top_k * 4

    vector_hits = await _vector_candidates(db, institution_id, query_vector, candidate_limit)
    fulltext_hits = await _fulltext_candidates(db, institution_id, query, candidate_limit)

    rrf_scores: dict[uuid.UUID, float] = {}
    chunk_data: dict[uuid.UUID, tuple[uuid.UUID, str, str]] = {}

    for rank, (chunk_id, document_id, title, content) in enumerate(vector_hits):
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
        chunk_data[chunk_id] = (document_id, title, content)

    for rank, (chunk_id, document_id, title, content) in enumerate(fulltext_hits):
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
        chunk_data[chunk_id] = (document_id, title, content)

    ranked = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
    return [
        RetrievedChunk(
            chunk_id=chunk_id,
            document_id=chunk_data[chunk_id][0],
            document_title=chunk_data[chunk_id][1],
            content=chunk_data[chunk_id][2],
            score=score,
        )
        for chunk_id, score in ranked
    ]
