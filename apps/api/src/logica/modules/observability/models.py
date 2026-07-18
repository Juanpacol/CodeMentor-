import uuid

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TimestampMixin, UUIDPkMixin
from logica.db import Base


class ErrorLog(UUIDPkMixin, TimestampMixin, Base):
    """Fase 13: incidentes técnicos (excepciones no controladas) capturados
    por el manejador global en `main.py`. No usa `TenantMixin` a propósito:
    `institution_id` debe ser nullable porque hay errores que ocurren antes
    de resolver el usuario autenticado (ej. un token inválido en sí mismo
    rompe algo antes de llegar a cualquier dependencia de auth)."""

    __tablename__ = "error_logs"

    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    path: Mapped[str] = mapped_column(String(300), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    exception_type: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    stacktrace: Mapped[str | None] = mapped_column(Text, nullable=True)


def truncate_message(message: str, *, limit: int = 500) -> str:
    return message if len(message) <= limit else message[: limit - 1] + "…"


def truncate_stacktrace(stacktrace: str, *, limit: int = 4000) -> str:
    return stacktrace if len(stacktrace) <= limit else stacktrace[-limit:]


__all__ = ["ErrorLog", "truncate_message", "truncate_stacktrace"]
