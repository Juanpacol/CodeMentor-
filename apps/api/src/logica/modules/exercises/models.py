import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base


class ExerciseType(enum.StrEnum):
    """The seven exercise types from RF-10, plus `live_code` (§4.2 "reto de
    código en vivo") added in Fase 4 — RE-05 is explicitly designed so a new
    type is one class + one registry entry, and this is that showcase."""

    true_false = "true_false"
    multiple_choice = "multiple_choice"
    fill_code = "fill_code"
    find_error = "find_error"
    trace_variables = "trace_variables"
    order_lines = "order_lines"
    argued_response = "argued_response"
    live_code = "live_code"


class ExerciseOrigin(enum.StrEnum):
    teacher = "teacher"
    ai = "ai"


class ExerciseStatus(enum.StrEnum):
    draft = "draft"
    published = "published"


class Exercise(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Reusable across topics and academic periods (RF-08). `content` is a
    type-specific JSON payload (statement, options, expected answer, rubric,
    test cases...) validated by the Fase 3 grading engine, not here.
    `origin`/`status` exist from day one so Fase 6's AI generator (RF-32) has
    somewhere to land drafts without a schema change."""

    __tablename__ = "exercises"

    language_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("languages.id"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[ExerciseType] = mapped_column(
        Enum(ExerciseType, name="exercise_type"), nullable=False
    )
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    origin: Mapped[ExerciseOrigin] = mapped_column(
        Enum(ExerciseOrigin, name="exercise_origin"),
        nullable=False,
        default=ExerciseOrigin.teacher,
    )
    status: Mapped[ExerciseStatus] = mapped_column(
        Enum(ExerciseStatus, name="exercise_status"),
        nullable=False,
        default=ExerciseStatus.published,
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)


class TopicExercise(UUIDPkMixin, TimestampMixin, Base):
    """Many-to-many link so an exercise can be reused across several topics."""

    __tablename__ = "topic_exercises"
    __table_args__ = (UniqueConstraint("topic_id", "exercise_id", name="uq_topic_exercise"),)

    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False, index=True
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercises.id"), nullable=False, index=True
    )
