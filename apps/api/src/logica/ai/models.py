import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base


class AiInteraction(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Auditable trail for every AI harness call (RF-34): who requested it,
    which task/model answered, what it cost, and — for tasks that produce
    content requiring approval (Fase 6: exercise_generation, grading
    suggestions) — whether a teacher approved it. `approved` stays NULL for
    tasks with no approval step (e.g. a hint), which is not the same as
    `false` (explicitly rejected)."""

    __tablename__ = "ai_interactions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    task: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    response_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    from_cache: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocked_by_guardrail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
