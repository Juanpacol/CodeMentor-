import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base


class NotificationKind(enum.StrEnum):
    """Ítem 5 (notificaciones inteligentes): reglas deterministas, sin
    juicio de un LLM — mismo precedente que `progress.service.get_lagging_students`."""

    assignment_due = "assignment_due"
    badge_earned = "badge_earned"
    streak_at_risk = "streak_at_risk"


class Notification(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Se generan de forma perezosa (`sync_notifications_for_student`) cada
    vez que el estudiante pide `GET /notifications`, no por un job/cola
    aparte — mismo patrón que `progress.service.ensure_default_badges`."""

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    kind: Mapped[NotificationKind] = mapped_column(
        Enum(NotificationKind, name="notification_kind"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    related_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
