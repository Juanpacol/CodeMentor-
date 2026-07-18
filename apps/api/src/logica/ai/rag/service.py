import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.rag.ingestion import ingest_document
from logica.ai.rag.models import RagChunk, RagDocument
from logica.core.errors import NotFoundError, PermissionDeniedError
from logica.modules.content.repository import get_topic
from logica.modules.users.models import Role, User


def _ensure_teacher(user: User) -> None:
    if user.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError(
            "Solo un docente o administrador puede gestionar material de apoyo"
        )


async def create_rag_document(
    db: AsyncSession, user: User, *, title: str, text: str, topic_id: uuid.UUID | None
) -> RagDocument:
    _ensure_teacher(user)
    if topic_id is not None:
        topic = await get_topic(db, topic_id)
        if topic is None or topic.institution_id != user.institution_id:
            raise NotFoundError("Tema no encontrado")
    return await ingest_document(
        db, institution_id=user.institution_id, title=title, text=text, topic_id=topic_id
    )


async def list_rag_documents(
    db: AsyncSession, user: User, *, topic_id: uuid.UUID | None
) -> list[tuple[RagDocument, int]]:
    _ensure_teacher(user)
    stmt = (
        select(RagDocument, func.count(RagChunk.id))
        .outerjoin(RagChunk, RagChunk.document_id == RagDocument.id)
        .where(RagDocument.institution_id == user.institution_id)
        .group_by(RagDocument.id)
        .order_by(RagDocument.created_at.desc())
    )
    if topic_id is not None:
        stmt = stmt.where(RagDocument.topic_id == topic_id)
    result = await db.execute(stmt)
    return [(doc, count) for doc, count in result.all()]


async def delete_rag_document(db: AsyncSession, user: User, document_id: uuid.UUID) -> None:
    _ensure_teacher(user)
    document = await db.get(RagDocument, document_id)
    if document is None or document.institution_id != user.institution_id:
        raise NotFoundError("Documento no encontrado")
    await db.execute(delete(RagChunk).where(RagChunk.document_id == document_id))
    await db.delete(document)
