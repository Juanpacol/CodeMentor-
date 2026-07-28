"""Rúbrica de temas (Fase 17): el docente escribe la lista de temas que quiere y
la plataforma crea los temas, busca material, redacta una guía por tema y genera
ejercicios por cada guía.

Por qué una tabla de job aparte y no el patrón de `Guide` (la fila ES su propio
job): una corrida produce **muchas** filas de dominio —temas, guías, ejercicios—
así que no hay una sola fila que pueda hacer de poll target. Es el mismo motivo
de `reports/models.py::ReportJob`, donde el producto es un archivo.

Por qué no se revivieron `curriculum_plans`/`curriculum_plan_items` (las tablas
inertes de la Fase 15): su semántica es asignar temas a periodos académicos, no
orquestar generación. Encajar esta máquina de estados ahí saldría más caro que
dos tablas nuevas y dejaría un esquema que no explica ninguna de las dos cosas.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base
from logica.modules.content.models import TopicLevel


class RubricRunStatus(enum.StrEnum):
    """`partial` no es un adorno: con los límites del tier gratuito de Groq, que
    8 de 10 temas salgan es el resultado **común**, no la excepción. Colapsarlo a
    `done` le diría al docente que su temario está listo cuando le faltan dos
    guías; colapsarlo a `failed` le diría que no tiene nada cuando tiene ocho."""

    pending = "pending"
    running = "running"
    done = "done"
    partial = "partial"
    failed = "failed"
    # Distinto de `failed`: cancelar es una decisión del docente, no un problema
    # de la plataforma. Mezclarlos hacía que una corrida cancelada apareciera
    # como incidente y que el recálculo final del runner pudiera pisarla con
    # `partial`/`done` según cuántos temas alcanzaron a salir.
    cancelled = "cancelled"


class RubricItemStatus(enum.StrEnum):
    """Un estado por etapa de la máquina, para que el docente vea en qué va cada
    tema y no solo una barra global."""

    pending = "pending"
    acquiring = "acquiring"
    writing_guide = "writing_guide"
    writing_exercises = "writing_exercises"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class RubricRun(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Una corrida de rúbrica: la petición completa del docente y su estado."""

    __tablename__ = "rubric_runs"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    folder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guides_folders.id"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guide_templates.id"), nullable=False
    )
    language_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("languages.id"), nullable=False
    )
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # list[str] con los valores de ExerciseType. JSON y no tabla hija por el
    # mismo motivo que `GuideTemplate.sections`: nunca se consulta un tipo
    # suelto, siempre se lee la lista entera.
    exercise_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    acquire_content: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[RubricRunStatus] = mapped_column(
        Enum(RubricRunStatus, name="rubric_run_status"),
        nullable=False,
        default=RubricRunStatus.pending,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RubricItem(UUIDPkMixin, TimestampMixin, Base):
    """Un tema de la rúbrica y su progreso.

    Sin `TenantMixin`: es una fila hija y la tenencia se resuelve por el run, igual
    que `RagChunk` la resuelve por `RagDocument`. Duplicar `institution_id` acá
    sería una segunda fuente de verdad que puede desincronizarse.

    Existe como tabla y no se deriva el progreso de las guías porque durante
    `acquiring` todavía no hay `Guide`, y un tema que falla antes de crear nada
    sería sencillamente invisible para el docente que está mirando la pantalla.
    """

    __tablename__ = "rubric_items"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rubric_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_name: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[TopicLevel] = mapped_column(Enum(TopicLevel, name="topic_level"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # URLs que pegó el docente para este tema. NULL = solo Wikipedia/Wikibooks.
    extra_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    # Se llenan a medida que la máquina avanza; NULL significa "esa etapa no
    # llegó a producir nada", que es exactamente lo que hay que poder distinguir.
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    guide_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guides.id", ondelete="SET NULL"), nullable=True
    )
    sources_ingested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exercises_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[RubricItemStatus] = mapped_column(
        Enum(RubricItemStatus, name="rubric_item_status"),
        nullable=False,
        default=RubricItemStatus.pending,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # `error_message` es el texto amable; estos dos son el "ver detalle" que le
    # permite al docente saber si reintentar sirve de algo. Sin ellos, tres
    # causas muy distintas (clave de API vencida, cuota agotada, el modelo
    # devolviendo JSON inválido) se leían con la misma frase genérica.
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
