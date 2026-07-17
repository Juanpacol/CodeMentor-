import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base


class AgentName(enum.StrEnum):
    """The 5 agents from §9.2. Values double as the harness `task` name each
    one drives (ai/harness/router.TASK_TIERS), so there is exactly one
    vocabulary for "which agent/task is this", not two that can drift."""

    tutor = "progressive_hint"
    exercise_generator = "exercise_generation"
    grading_assistant = "grading_suggestion"
    learning_analytics = "summarize_group"
    code_integrity = "code_integrity"


class AgentConfig(UUIDPkMixin, TimestampMixin, Base):
    """Per-group on/off switch for each agent (RF-30). Absence of a row for
    a (group_id, agent_name) pair means "enabled" — the default — so a group
    only needs a row once a teacher actually disables something, rather
    than seeding 5 rows for every group at creation time."""

    __tablename__ = "agent_configs"
    __table_args__ = (UniqueConstraint("group_id", "agent_name", name="uq_agent_config_group"),)

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    agent_name: Mapped[AgentName] = mapped_column(
        Enum(AgentName, name="agent_name"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TutorMessageRole(enum.StrEnum):
    student = "student"
    tutor = "tutor"


class TutorMessage(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Persisted Tutor chat history (§9.6, RF-35): visible to the student
    and consultable by the teacher, always clearly labeled as AI — never
    presented as a message from the human teacher."""

    __tablename__ = "tutor_messages"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercises.id"), nullable=False, index=True
    )
    role: Mapped[TutorMessageRole] = mapped_column(
        Enum(TutorMessageRole, name="tutor_message_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)


class CodeIntegrityAlert(UUIDPkMixin, TimestampMixin, Base):
    """An informational flag (§9.2: "el resultado es una alerta, nunca una
    sanción automática") for a teacher to look into — never auto-applied to
    a grade or student record."""

    __tablename__ = "code_integrity_alerts"

    evaluation_answer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_answers.id"), nullable=False, index=True
    )
    suspicious: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
