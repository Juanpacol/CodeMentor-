import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, Numeric, String
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
    # Versión de la plantilla (ai/harness/prompts/__init__.py) que generó esta
    # interacción — sin esto no hay forma de saber qué texto produjo cada
    # respuesta ya registrada tras cambiar un prompt (ítem 15).
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    response_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Costo ESTIMADO (ítem 14) — no facturación real. Numeric, no Float:
    # sumar miles de floats para una cifra con forma de dinero acumula
    # deriva. 0 para un hit de caché o un modelo sin precio conocido.
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    from_cache: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocked_by_guardrail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        # El dashboard de costo siempre filtra institución + rango de fechas
        # (ai/repository.py::summarize_usage) — TenantMixin solo indexa
        # institution_id por separado, no la combinación con created_at.
        Index("ix_ai_interactions_institution_created", "institution_id", "created_at"),
    )
