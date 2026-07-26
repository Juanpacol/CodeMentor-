import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base


class AgentName(enum.StrEnum):
    """The agents from §9.2 plus el creador de guías (Fase 16). Values double as
    the harness `task` name each one drives (ai/harness/router.TASK_TIERS), so
    there is exactly one vocabulary for "which agent/task is this", not two that
    can drift.

    Ese invariante lo verifica `tests/unit/test_agent_registry.py`: agregar un
    miembro acá obliga a agregar su tier y su plantilla de prompt en el mismo
    commit. No es burocracia — `curriculum_planner` vivió en este enum sin
    plantilla ni tier, así que aparecía en `GET /ai/groups/{id}/agents` como un
    agente activo que el docente podía apagar y que, si algo lo hubiera invocado,
    habría muerto con `TemplateNotFound` en runtime."""

    tutor = "progressive_hint"
    exercise_generator = "exercise_generation"
    grading_assistant = "grading_suggestion"
    learning_analytics = "summarize_group"
    code_integrity = "code_integrity"
    guide_writer = "guide_generation"


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
    # Títulos de RagDocument usados para fundamentar esta pista (solo en
    # mensajes role=tutor) — permite al estudiante/docente verificar de qué
    # material salió, en vez de confiar ciegamente en el LLM.
    sources: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)


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


class CurriculumPlanOrigin(enum.StrEnum):
    ai = "ai"
    manual = "manual"


class CurriculumPlanStatus(enum.StrEnum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"
    superseded = "superseded"


class CurriculumPlanKind(enum.StrEnum):
    initial = "initial"
    replan = "replan"


class CurriculumPlan(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Fase 15: una propuesta (siempre `origin=ai, status=draft` al crearse)
    de cómo repartir los temas de un grupo entre periodos académicos. Nunca
    se aplica sola — un docente la aprueba, edita o rechaza explícitamente,
    igual que el resto de agentes de IA de la plataforma (§9.2)."""

    __tablename__ = "curriculum_plans"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    language_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("languages.id"), nullable=False
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    origin: Mapped[CurriculumPlanOrigin] = mapped_column(
        Enum(CurriculumPlanOrigin, name="curriculum_plan_origin"), nullable=False
    )
    status: Mapped[CurriculumPlanStatus] = mapped_column(
        Enum(CurriculumPlanStatus, name="curriculum_plan_status"),
        nullable=False,
        default=CurriculumPlanStatus.draft,
    )
    kind: Mapped[CurriculumPlanKind] = mapped_column(
        Enum(CurriculumPlanKind, name="curriculum_plan_kind"), nullable=False
    )
    source_syllabus: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CurriculumPlanItem(UUIDPkMixin, TimestampMixin, Base):
    """Un tema asignado (o no) a un periodo dentro de un `CurriculumPlan`.
    `period_id = NULL` significa "no alcanza" — el scheduler simbólico
    (curriculum_scheduler.py) lo deja así en vez de inventar una fecha."""

    __tablename__ = "curriculum_plan_items"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False
    )
    period_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_periods.id"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
