import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.ai.rag.embedder import EMBEDDING_DIMENSIONS
from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base


class RagDocument(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """A source document ingested for the Tutor's grounding material (§9.3
    "recuperar contexto"): PSeInt reference sheets, teacher notes, etc."""

    __tablename__ = "rag_documents"
    __table_args__ = (
        UniqueConstraint("institution_id", "title", name="uq_rag_document_institution_title"),
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="teacher_material")
    # Fase 14: alcance opcional por tema — nullable porque material general
    # de la institución (sin tema específico) sigue siendo válido. La
    # recuperación (retriever.py) incluye tanto los documentos del tema como
    # los que no tienen tema asignado, nunca solo los del tema (para no
    # dejar sin resultados a un tema que aún no tiene material propio).
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Fase 17: procedencia del material traído de la web por `acquire.py`. NULL
    # para lo que subió un docente a mano. No es metadato decorativo: la licencia
    # CC BY-SA de Wikimedia exige atribución, y sin la URL el docente no tiene
    # cómo verificar de dónde salió lo que el modelo usó para redactar la guía.
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RagChunk(UUIDPkMixin, TimestampMixin, Base):
    """One embedded chunk of a RagDocument. No institution_id of its own —
    always queried joined through `document_id`, so tenancy is enforced via
    RagDocument.institution_id rather than duplicated here."""

    __tablename__ = "rag_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rag_documents.id"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
