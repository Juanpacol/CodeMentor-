import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base


class TopicLevel(enum.StrEnum):
    basico = "basico"
    intermedio = "intermedio"
    avanzado = "avanzado"


class TopicGroupStateValue(enum.StrEnum):
    locked = "locked"
    enabled = "enabled"
    evaluated = "evaluated"


class Language(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Configurable list of programming languages (RF-25) — not hardcoded, so
    adding C/C++/Java/PHP later is a data change, not a code change (RE-06)."""

    __tablename__ = "languages"
    __table_args__ = (
        UniqueConstraint("institution_id", "slug", name="uq_language_institution_slug"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    syntax_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Topic(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """A curriculum unit (RF-07). `order_index` drives the suggested sequence
    (RF-19); `version` lets Fase 3 attempts pin the content they were graded
    against (RE-07) without a full history table."""

    __tablename__ = "topics"

    language_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("languages.id"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[TopicLevel] = mapped_column(Enum(TopicLevel, name="topic_level"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class TopicGroupState(UUIDPkMixin, TimestampMixin, Base):
    """Per-group visibility/enablement of a topic (RF-18, RF-22-24): the
    platform never advances content on its own — a teacher always flips this."""

    __tablename__ = "topic_group_states"
    __table_args__ = (UniqueConstraint("topic_id", "group_id", name="uq_topic_group"),)

    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False, index=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    state: Mapped[TopicGroupStateValue] = mapped_column(
        Enum(TopicGroupStateValue, name="topic_group_state_value"),
        nullable=False,
        default=TopicGroupStateValue.locked,
    )
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_enable_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
