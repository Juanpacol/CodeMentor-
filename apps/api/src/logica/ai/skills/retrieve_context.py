"""Skill "recuperar contexto" (§9.3): the first of the catalogued skills —
a small, independently-testable capability with a clear input/output that
agents (Fase 6) consume as a tool, without duplicating retrieval logic.
Formats hits as a single citation-annotated block ready to interpolate into
a prompt template (e.g. exercise_generation.j2's `reference_context`)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.rag.retriever import retrieve


async def retrieve_context(
    db: AsyncSession,
    institution_id: uuid.UUID,
    query: str,
    top_k: int = 3,
    topic_id: uuid.UUID | None = None,
) -> str:
    hits = await retrieve(db, institution_id, query, top_k=top_k, topic_id=topic_id)
    if not hits:
        return ""

    return "\n\n".join(f"[Fuente: {hit.document_title}]\n{hit.content}" for hit in hits)
