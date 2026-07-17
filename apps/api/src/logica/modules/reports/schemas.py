import uuid
from datetime import datetime

from pydantic import BaseModel

from logica.modules.reports.models import ReportFormat, ReportStatus


class ReportRequest(BaseModel):
    format: ReportFormat
    period_id: uuid.UUID | None = None


class ReportJobOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    format: ReportFormat
    status: ReportStatus
    error_message: str | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}
