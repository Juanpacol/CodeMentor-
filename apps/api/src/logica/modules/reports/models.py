import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base


class ReportFormat(enum.StrEnum):
    xlsx = "xlsx"
    pdf = "pdf"


class ReportStatus(enum.StrEnum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class ReportJob(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """RF-16: an export runs as a background arq job (RE-03, never blocking
    the request/response cycle) — this row is the poll target the API
    returns immediately, updated by the worker as it progresses."""

    __tablename__ = "report_jobs"

    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    period_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_periods.id"), nullable=True
    )
    format: Mapped[ReportFormat] = mapped_column(
        Enum(ReportFormat, name="report_format"), nullable=False
    )
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status"), nullable=False, default=ReportStatus.pending
    )
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
