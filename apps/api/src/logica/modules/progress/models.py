import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base


class BadgeCriteria(enum.StrEnum):
    """RF-29: qué condición otorga la insignia. `topic_mastery`/
    `language_mastery` son plantillas genéricas por institución — el tema o
    lenguaje concreto que la ganó queda en `StudentBadge.topic_id`/
    `language_id`, no en el catálogo (evita una fila de `Badge` por cada
    tema)."""

    topic_mastery = "topic_mastery"
    language_mastery = "language_mastery"
    practice_streak = "practice_streak"


class Badge(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Catálogo de insignias por institución (RF-29). Se asegura de forma
    perezosa (`progress.service.ensure_default_badges`) la primera vez que se
    evalúan insignias para una institución, en vez de sembrarse en una
    migración de datos."""

    __tablename__ = "badges"
    __table_args__ = (UniqueConstraint("institution_id", "slug", name="uq_badge_institution_slug"),)

    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    criteria: Mapped[BadgeCriteria] = mapped_column(
        Enum(BadgeCriteria, name="badge_criteria"), nullable=False
    )
    threshold: Mapped[float] = mapped_column(Float, nullable=False)


class StudentBadge(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Una instancia ganada de una insignia (RF-29). `language_id`/`topic_id`
    quedan NULL para insignias sin alcance (por ejemplo `practice_streak`)."""

    __tablename__ = "student_badges"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "badge_id",
            "language_id",
            "topic_id",
            name="uq_student_badge_scope",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    badge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("badges.id"), nullable=False, index=True
    )
    language_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("languages.id"), nullable=True
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True
    )
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AcademicPeriod(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """RF-17: un rango de fechas con nombre (por ejemplo "Periodo 1 - 2026")
    que el docente crea explícitamente y que los reportes/el progreso pueden
    usar para filtrar por fecha — no altera ninguna tabla existente, solo
    acota una consulta por `created_at`/`submitted_at` entre sus fechas."""

    __tablename__ = "academic_periods"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
