"""Asignaciones con fecha límite.

Por qué una tabla y no una columna `due_at` en algo existente: no había ningún
concepto de "el docente le pidió esto a este grupo para esta fecha".
`TopicGroupState` tiene `scheduled_enable_at`, que es cuándo se **abre** un tema,
no cuándo vence; y `Evaluation` mide un momento puntual, no una tarea pendiente.
Sin esta tabla, "lo que me falta" solo podía inferirse como "todo ejercicio de un
tema habilitado que no he resuelto", que no distingue lo que el docente
realmente pidió del catálogo entero.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base


class Assignment(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Lo que un docente le pide a un grupo, con fecha de entrega.

    Apunta a exactamente uno de cuatro destinos — tema, ejercicio, evaluación
    (examen) o guía (taller) — nunca a más de uno: son las granularidades que
    el docente usa para pedir algo, y un `CheckConstraint` las mantiene
    excluyentes en vez de dejar que una fila con varias signifique lo que cada
    consulta quiera.

    Sin `ON DELETE CASCADE` hacia ninguno de los cuatro: borrar el objetivo no
    debería borrar en silencio el registro de que fue asignado.
    """

    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint(
            "(topic_id IS NOT NULL)::int + (exercise_id IS NOT NULL)::int + "
            "(evaluation_id IS NOT NULL)::int + (guide_id IS NOT NULL)::int = 1",
            name="ck_assignment_exactly_one_target",
        ),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True
    )
    exercise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercises.id"), nullable=True
    )
    # Examen: la asignación apunta a la evaluación en sí, no a sus ejercicios
    # sueltos — "cumplida" se resuelve contra si ya la presentó.
    evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id"), nullable=True
    )
    # Taller: una guía de clase. No hay señal de "la leyó" en la plataforma
    # todavía, así que "cumplida" queda siempre en falso para este destino —
    # ver `service.py::list_my_assignments`.
    guide_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guides.id"), nullable=True
    )
    # Nullable: "para cuando puedas" es una asignación válida, y forzar una
    # fecha inventada haría que el dashboard mostrara vencimientos falsos.
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
