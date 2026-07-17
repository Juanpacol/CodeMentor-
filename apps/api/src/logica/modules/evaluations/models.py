import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base


class EvaluationMode(enum.StrEnum):
    fixed = "fixed"
    cumulative = "cumulative"


class AttemptStatus(enum.StrEnum):
    in_progress = "in_progress"
    submitted = "submitted"
    expired = "expired"


class Evaluation(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """RF-20/21: the teacher always states explicitly how far the evaluation
    reaches — either a fixed topic (`up_to_topic_id`, everything up to and
    including it) or `cumulative` (everything enabled for the group so far).
    Either way, exercise eligibility is validated server-side at creation
    (see evaluations/service.py) — never left to client-supplied trust."""

    __tablename__ = "evaluations"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    mode: Mapped[EvaluationMode] = mapped_column(
        Enum(EvaluationMode, name="evaluation_mode"), nullable=False
    )
    up_to_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True
    )
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_ranked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class EvaluationExercise(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_exercises"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "exercise_id", name="uq_evaluation_exercise"),
    )

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id"), nullable=False, index=True
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercises.id"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # RE-07: pins the exercise version this evaluation was built against, for
    # traceability — grading itself is computed once at submission time and
    # persisted (see EvaluationAnswer), so a later content edit never
    # retroactively changes an already-submitted grade.
    exercise_version_at_attach: Mapped[int] = mapped_column(Integer, nullable=False)


class EvaluationAttempt(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_attempts"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "student_id", name="uq_evaluation_attempt_student"),
    )

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[AttemptStatus] = mapped_column(
        Enum(AttemptStatus, name="attempt_status"),
        nullable=False,
        default=AttemptStatus.in_progress,
    )
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)


class EvaluationAnswer(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "evaluation_exercise_id", name="uq_answer_attempt_exercise"),
    )

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_attempts.id"), nullable=False, index=True
    )
    evaluation_exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_exercises.id"), nullable=False, index=True
    )
    answer: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    needs_manual_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    manual_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # RF-33: the Grading Assistant's suggestion, kept strictly separate from
    # `manual_score` — a teacher must explicitly confirm (or overrule) it via
    # the existing manual-review endpoint before it ever affects a grade.
    ai_suggested_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_suggested_justification: Mapped[str | None] = mapped_column(Text, nullable=True)


class PracticeSubmission(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Free practice (RF-09): unlimited, untimed, immediate feedback — no
    Attempt/timer wrapper, just one row per submission."""

    __tablename__ = "practice_submissions"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercises.id"), nullable=False, index=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    answer: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    needs_manual_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
