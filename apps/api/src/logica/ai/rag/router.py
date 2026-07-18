import uuid

from fastapi import APIRouter, Depends, Form, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.rag import service
from logica.ai.rag.models import RagChunk
from logica.ai.rag.schemas import RagDocumentOut
from logica.core.errors import ValidationDomainError
from logica.core.security import get_current_user
from logica.db import get_db
from logica.modules.users.models import User

router = APIRouter(prefix="/ai/rag", tags=["rag"])

_ALLOWED_EXTENSIONS = (".md", ".txt")


@router.post("/documents", response_model=RagDocumentOut, status_code=201)
async def upload_rag_document(
    file: UploadFile,
    title: str = Form(...),
    topic_id: uuid.UUID | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RagDocumentOut:
    filename = file.filename or ""
    if not filename.lower().endswith(_ALLOWED_EXTENSIONS):
        raise ValidationDomainError("Solo se aceptan archivos .md o .txt")

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationDomainError("El archivo debe estar codificado en UTF-8") from exc

    document = await service.create_rag_document(
        db, user, title=title, text=text, topic_id=topic_id
    )
    chunk_count = (
        await db.execute(select(func.count(RagChunk.id)).where(RagChunk.document_id == document.id))
    ).scalar_one()
    await db.commit()
    return RagDocumentOut(
        id=document.id,
        title=document.title,
        source_type=document.source_type,
        topic_id=document.topic_id,
        chunk_count=chunk_count,
        created_at=document.created_at,
    )


@router.get("/documents", response_model=list[RagDocumentOut])
async def list_rag_documents(
    topic_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RagDocumentOut]:
    rows = await service.list_rag_documents(db, user, topic_id=topic_id)
    return [
        RagDocumentOut(
            id=doc.id,
            title=doc.title,
            source_type=doc.source_type,
            topic_id=doc.topic_id,
            chunk_count=count,
            created_at=doc.created_at,
        )
        for doc, count in rows
    ]


@router.delete("/documents/{document_id}", status_code=204)
async def delete_rag_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_rag_document(db, user, document_id)
    await db.commit()
